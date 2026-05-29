"""
Fine-tune a multilingual transformer for conflict detection, severity, and type classification.

Usage:
    python src/train.py [options]

Options:
    --data PATH     Annotated CSV  (default: data/annotations/annotation_FINAL.csv)
    --model NAME    HuggingFace model ID (default: google/muril-base-cased)
    --task          conflict | severity | type | both  (default: both)
    --epochs INT    Training epochs (default: 5)
    --batch INT     Per-device batch size (default: 8)
    --lr FLOAT      Learning rate (default: 2e-5)
    --max-len INT   Max token length (default: 256)
    --output DIR    Checkpoint directory (default: models/)
    --seed INT      Random seed (default: 42)

Swap to the full dataset by passing --data path/to/your/bigger_annotated.csv.
Everything else stays the same.

Models saved:
    models/conflict/  — binary conflict classifier
    models/severity/  — 4-class severity classifier (0=none,1=mild,2=moderate,3=severe)
    models/type/      — 4-class type classifier (0=personal,1=political,2=sexual,3=threat)
"""

import argparse
import csv
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import torch
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
    set_seed,
)

sys.path.insert(0, str(Path(__file__).parent.parent))
from evaluation.metrics import (
    print_conflict_report,
    print_severity_report,
    print_type_report,
)

REPO_ROOT   = Path(__file__).parent.parent
DEFAULT_DATA = REPO_ROOT / "data" / "annotations" / "annotation_FINAL.csv"
DEFAULT_OUT  = REPO_ROOT / "models"

SEP = "─" * 65

# ── dataset ───────────────────────────────────────────────────────────────────

def load_csv(path: Path) -> list[dict]:
    rows = []
    skipped_severity = 0
    with path.open(encoding="utf-8-sig") as f:
        for i, row in enumerate(csv.DictReader(f), 2):
            lc = row.get("label_conflict", "").strip()
            ls = row.get("label_severity", "").strip()
            lt = row.get("label_type", "").strip()
            if lc == "":
                continue
            lc_int = int(lc)
            # Guard: conflict=1 but severity blank → skip with warning (not silently 0)
            if lc_int == 1 and ls == "":
                skipped_severity += 1
                continue
            # Severity already 0-indexed in splits (0=mild,1=moderate,2=severe)
            ls_int = int(ls) if ls != "" else 0
            # Type: single-label 0-indexed (0=personal,1=political,2=sexual,3=threat)
            lt_int = int(lt) if lt != "" else 0
            rows.append({
                "text":           row["thread_text"].replace("\n", " "),
                "label_conflict": lc_int,
                "label_severity": ls_int,
                "label_type":     lt_int,
            })
    if skipped_severity:
        print(f"[WARN] Skipped {skipped_severity} rows with conflict=1 but blank severity.")
    return rows


class ThreadDataset(Dataset):
    def __init__(self, rows: list[dict], tokenizer, max_len: int, label_col: str):
        self.labels    = [r[label_col] for r in rows]
        self.encodings = tokenizer(
            [r["text"] for r in rows],
            truncation=True,
            padding="max_length",
            max_length=max_len,
            return_tensors="pt",
        )

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {k: v[idx] for k, v in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


# ── weighted trainer (handles class imbalance via weighted cross-entropy) ────

class WeightedTrainer(Trainer):
    def __init__(self, *args, class_weights: torch.Tensor | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        loss_fct = torch.nn.CrossEntropyLoss(
            weight=self.class_weights.to(logits.device) if self.class_weights is not None else None
        )
        loss = loss_fct(logits, labels)
        return (loss, outputs) if return_outputs else loss


# ── metrics passed to Trainer ────────────────────────────────────────────────

def make_compute_metrics(task: str):
    from sklearn.metrics import f1_score, accuracy_score
    import numpy as np

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds    = np.argmax(logits, axis=-1)
        f1_macro = f1_score(labels, preds, average="macro", zero_division=0)
        acc      = accuracy_score(labels, preds)
        result   = {"f1_macro": f1_macro, "accuracy": acc}
        if task == "severity":
            result["mae"] = float(np.mean(np.abs(labels - preds)))
        return result

    return compute_metrics


# ── train one task ────────────────────────────────────────────────────────────

def train_task(
    task: str,
    rows: list[dict],
    model_name: str,
    output_dir: Path,
    epochs: int,
    batch: int,
    lr: float,
    max_len: int,
    seed: int,
):
    label_col  = f"label_{task}"
    # conflict: 2 classes (0=none, 1=conflict)
    # severity: 3 classes (0=mild, 1=moderate, 2=severe)  — 0-indexed, no spurious class 0
    # type:     4 classes (0=personal, 1=political, 2=sexual, 3=threat) — single-label 0-indexed
    num_labels = 2 if task == "conflict" else (3 if task == "severity" else 4)

    # severity/type only make sense on conflict=1 rows
    if task == "conflict":
        task_rows = rows
    elif task == "severity":
        task_rows = [r for r in rows if r["label_conflict"] == 1]
    else:  # type: single-label, skip rows with blank type
        task_rows = [r for r in rows if r["label_conflict"] == 1 and r["label_type"] != ""]

    print(f"\n{SEP}")
    print(f"  Task: {task.upper()}  |  {len(task_rows)} samples  |  {num_labels} classes")
    print(SEP)

    MIN_SAMPLES = 20
    if len(task_rows) < MIN_SAMPLES:
        print(f"  [SKIP] Only {len(task_rows)} samples for task '{task}' — need {MIN_SAMPLES}+.")
        print(f"         Complete annotation first, then re-run training.")
        return None

    # Stratified split: 70 / 15 / 15
    # Stratification requires each class to have ≥2 samples; fall back to random if not.
    labels_all = [r[label_col] for r in task_rows]
    from collections import Counter
    use_stratify = all(c >= 2 for c in Counter(labels_all).values())
    train_rows, temp_rows = train_test_split(
        task_rows, test_size=0.30, random_state=seed,
        stratify=labels_all if use_stratify else None,
    )
    temp_labels = [r[label_col] for r in temp_rows]
    use_stratify2 = all(c >= 2 for c in Counter(temp_labels).values())
    val_rows, test_rows = train_test_split(
        temp_rows, test_size=0.50, random_state=seed,
        stratify=temp_labels if use_stratify2 else None,
    )

    print(f"  Split — train:{len(train_rows)}  val:{len(val_rows)}  test:{len(test_rows)}")

    # Compute class weights from training split only (all tasks now single-label)
    train_labels_arr = np.array([r[label_col] for r in train_rows])
    classes = np.unique(train_labels_arr)
    weights = compute_class_weight("balanced", classes=classes, y=train_labels_arr)
    class_weights = torch.tensor(weights, dtype=torch.float)
    weight_str = "  ".join(f"class {c}→{w:.3f}" for c, w in zip(classes, weights))
    print(f"  Class weights: {weight_str}")

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    train_ds = ThreadDataset(train_rows, tokenizer, max_len, label_col)
    val_ds   = ThreadDataset(val_rows,   tokenizer, max_len, label_col)
    test_ds  = ThreadDataset(test_rows,  tokenizer, max_len, label_col)

    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=num_labels,
    )

    task_out = output_dir / task
    task_out.mkdir(parents=True, exist_ok=True)

    args = TrainingArguments(
        output_dir              = str(task_out),
        num_train_epochs        = epochs,
        per_device_train_batch_size = batch,
        per_device_eval_batch_size  = batch,
        learning_rate           = lr,
        warmup_ratio            = 0.1,
        weight_decay            = 0.01,
        eval_strategy           = "epoch",
        save_strategy           = "epoch",
        load_best_model_at_end  = True,
        metric_for_best_model   = "f1_macro",
        greater_is_better       = True,
        logging_steps           = 10,
        seed                    = seed,
        report_to               = "none",
        fp16                    = torch.cuda.is_available(),
    )

    trainer = WeightedTrainer(
        model            = model,
        args             = args,
        train_dataset    = train_ds,
        eval_dataset     = val_ds,
        compute_metrics  = make_compute_metrics(task),
        callbacks        = [EarlyStoppingCallback(early_stopping_patience=2)],
        class_weights    = class_weights,
    )

    print(f"\n  Training on {'GPU' if torch.cuda.is_available() else 'CPU'}...")
    trainer.train()

    # ── Test set evaluation ───────────────────────────────────────────────
    print(f"\n  Test set evaluation:")
    preds_out = trainer.predict(test_ds)

    y_pred = np.argmax(preds_out.predictions, axis=-1).tolist()
    y_true = [r[label_col] for r in test_rows]
    if task == "conflict":
        print_conflict_report(y_true, y_pred)
    elif task == "severity":
        print_severity_report(y_true, y_pred)
    else:
        print_type_report(y_true, y_pred)

    # ── Save model + tokenizer ────────────────────────────────────────────
    best_dir = task_out / "best"
    trainer.save_model(str(best_dir))
    tokenizer.save_pretrained(str(best_dir))
    print(f"  Model saved → {best_dir}")

    return best_dir


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MalayalamCyberCon training")
    parser.add_argument("--data",    default=str(DEFAULT_DATA), help="Annotated CSV path")
    parser.add_argument("--model",   default="google/muril-base-cased", help="HuggingFace model ID")
    parser.add_argument("--task",    default="both", choices=["conflict", "severity", "type", "both"])
    parser.add_argument("--epochs",  type=int,   default=5)
    parser.add_argument("--batch",   type=int,   default=8)
    parser.add_argument("--lr",      type=float, default=2e-5)
    parser.add_argument("--max-len", type=int,   default=256)
    parser.add_argument("--output",  default=str(DEFAULT_OUT))
    parser.add_argument("--seed",    type=int,   default=42)
    args = parser.parse_args()

    set_seed(args.seed)
    data_path  = Path(args.data)
    output_dir = Path(args.output)

    if not data_path.exists():
        print(f"[ERROR] Data file not found: {data_path}")
        print("        Run scripts/adjudicate.py first, or pass --data <path>")
        sys.exit(1)

    rows = load_csv(data_path)
    print(f"\nLoaded {len(rows)} labeled threads from {data_path.name}")

    tasks = ["conflict", "severity", "type"] if args.task == "both" else [args.task]

    for task in tasks:
        train_task(
            task       = task,
            rows       = rows,
            model_name = args.model,
            output_dir = output_dir,
            epochs     = args.epochs,
            batch      = args.batch,
            lr         = args.lr,
            max_len    = args.__dict__["max_len"],
            seed       = args.seed,
        )

    print(f"\n{SEP}")
    print(f"  Training complete. Models saved to: {output_dir}")
    print(f"  To run inference: python src/predict.py --text \"your thread here\"")
    print(SEP)


if __name__ == "__main__":
    main()
