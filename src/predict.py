"""
Inference script — predict conflict, severity, and type for a comment thread.

Usage:
    # Single thread
    python src/predict.py --text "[1] poda mandan [2★] ninte taste level ariyam"

    # Batch prediction from JSONL
    python src/predict.py --csv data/raw_threads.jsonl --output results.csv

Output per thread:
    conflict       : 0 (none) | 1 (conflict present)
    severity       : none | mild | moderate | severe
    type           : personal | political | sexual/gendered | threat  (multi-label)
    confidence     : probability of each prediction
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

REPO_ROOT        = Path(__file__).parent.parent
DEFAULT_CONFLICT = REPO_ROOT / "models" / "conflict" / "best"
DEFAULT_SEVERITY = REPO_ROOT / "models" / "severity" / "best"
DEFAULT_TYPE     = REPO_ROOT / "models" / "type"     / "best"

SEVERITY_LABELS = {0: "mild", 1: "moderate", 2: "severe"}   # 0-indexed
TYPE_LABELS     = ["personal", "political", "sexual/gendered", "threat"]  # 0-indexed single-label


# ── model loading ─────────────────────────────────────────────────────────────

def load_model(model_dir: Path):
    if not model_dir.exists():
        print(f"[WARN] Model not found: {model_dir} — skipping.")
        return None, None
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model     = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    model.eval()
    return tokenizer, model


# ── inference ─────────────────────────────────────────────────────────────────

def predict_one(text: str, tokenizer, model, max_len: int = 256) -> tuple[int, float]:
    """Single-label prediction. Returns (label, confidence)."""
    inputs = tokenizer(
        text, truncation=True, padding="max_length",
        max_length=max_len, return_tensors="pt",
    )
    with torch.no_grad():
        logits = model(**inputs).logits
    probs = torch.softmax(logits, dim=-1)[0]
    pred  = int(probs.argmax())
    conf  = float(probs[pred])
    return pred, conf


def predict_type(text: str, tokenizer, model, max_len: int = 256) -> tuple[str, float]:
    """Single-label type prediction. Returns (type_name, confidence)."""
    pred, conf = predict_one(text, tokenizer, model, max_len)
    return TYPE_LABELS[pred], conf


def predict_thread(
    text: str,
    conflict_tok,  conflict_model,
    severity_tok,  severity_model,
    type_tok,      type_model,
    max_len: int = 256,
) -> dict:
    # Step 1 — conflict
    conflict, conf_c = predict_one(text, conflict_tok, conflict_model, max_len)

    if conflict == 0:
        return {
            "conflict":            0,
            "conflict_confidence": round(conf_c, 4),
            "severity":            0,
            "severity_label":      "none",
            "severity_confidence": 1.0,
            "types":               [],
            "type_probs":          [0.0] * 4,
        }

    # Step 2 — severity (only if conflict=1)
    severity, conf_s = predict_one(text, severity_tok, severity_model, max_len)

    # Step 3 — type (only if conflict=1, and model is available)
    if type_tok is not None:
        type_label, conf_t = predict_type(text, type_tok, type_model, max_len)
    else:
        type_label, conf_t = "unknown", 0.0

    return {
        "conflict":            1,
        "conflict_confidence": round(conf_c, 4),
        "severity":            severity,
        "severity_label":      SEVERITY_LABELS.get(severity, "unknown"),
        "severity_confidence": round(conf_s, 4),
        "type":                type_label,
        "type_confidence":     round(conf_t, 4),
    }


# ── display ───────────────────────────────────────────────────────────────────

SEP = "─" * 60

def print_result(text: str, result: dict):
    print(SEP)
    print(f"  Text     : {text[:120].replace(chr(10), ' ')}...")
    print(f"  Conflict : {result['conflict']}  ({result['conflict_confidence']:.1%} confidence)")
    if result["conflict"] == 1:
        print(f"  Severity : {result['severity']} — {result['severity_label']}  ({result['severity_confidence']:.1%} confidence)")
        print(f"  Type     : {result['type']}  ({result['type_confidence']:.1%} confidence)")
    else:
        print(f"  Severity : none")
        print(f"  Type     : —")
    print(SEP)


# ── batch from JSONL ──────────────────────────────────────────────────────────

def predict_jsonl(
    jsonl_path: Path,
    conflict_tok, conflict_model,
    severity_tok, severity_model,
    type_tok,     type_model,
    output_path: Path,
    max_len: int,
):
    threads = []
    for line in jsonl_path.open(encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                threads.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    print(f"Predicting on {len(threads)} threads...")

    fields = [
        "thread_id", "video_id",
        "conflict", "conflict_confidence",
        "severity", "severity_label", "severity_confidence",
        "type", "type_confidence",
    ]

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, t in enumerate(threads, 1):
            text   = " ".join(t.get("messages", []))
            result = predict_thread(
                text,
                conflict_tok, conflict_model,
                severity_tok, severity_model,
                type_tok,     type_model,
                max_len,
            )
            writer.writerow({
                "thread_id":           t.get("thread_id", ""),
                "video_id":            t.get("video_id", ""),
                "conflict":            result["conflict"],
                "conflict_confidence": result["conflict_confidence"],
                "severity":            result["severity"],
                "severity_label":      result["severity_label"],
                "severity_confidence": result["severity_confidence"],
                "type":                result["type"],
                "type_confidence":     result["type_confidence"],
            })
            if i % 50 == 0:
                print(f"  {i}/{len(threads)} done...")

    print(f"Predictions saved → {output_path}")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MalayalamCyberCon inference")
    parser.add_argument("--text",           help="Thread text to classify")
    parser.add_argument("--csv",            help="JSONL file for batch prediction")
    parser.add_argument("--output",         default="data/predictions.csv")
    parser.add_argument("--conflict-model", default=str(DEFAULT_CONFLICT))
    parser.add_argument("--severity-model", default=str(DEFAULT_SEVERITY))
    parser.add_argument("--type-model",     default=str(DEFAULT_TYPE))
    parser.add_argument("--max-len",        type=int, default=256)
    args = parser.parse_args()

    if not args.text and not args.csv:
        parser.print_help()
        sys.exit(1)

    print("Loading conflict model...")
    conflict_tok, conflict_model = load_model(Path(args.conflict_model))
    if conflict_tok is None:
        print("[ERROR] Conflict model is required.")
        sys.exit(1)

    print("Loading severity model...")
    severity_tok, severity_model = load_model(Path(args.severity_model))
    if severity_tok is None:
        print("[ERROR] Severity model is required.")
        sys.exit(1)

    print("Loading type model...")
    type_tok, type_model = load_model(Path(args.type_model))
    if type_tok is None:
        print("[WARN] Type model not found — type prediction disabled.")

    if args.text:
        result = predict_thread(
            args.text,
            conflict_tok, conflict_model,
            severity_tok, severity_model,
            type_tok,     type_model,
            args.max_len,
        )
        print_result(args.text, result)

    if args.csv:
        predict_jsonl(
            Path(args.csv),
            conflict_tok, conflict_model,
            severity_tok, severity_model,
            type_tok,     type_model,
            Path(args.output),
            args.max_len,
        )


if __name__ == "__main__":
    main()
