"""
Preprocess annotation_FINAL.csv and produce stratified train/val/test splits.

Steps applied to ALL data (no leakage risk since no statistics are fitted):
  1. Drop rows with blank thread_text or blank target_message
  2. Normalise whitespace in thread_text (collapse newlines → space, strip)
  3. Drop exact duplicate (thread_id) rows
  4. Stratified 70 / 15 / 15 split on label_conflict

Output files written to data/splits/:
  train.csv   — 70%
  val.csv     — 15%
  test.csv    — 15%
  clean.csv   — full cleaned dataset (all 3 splits combined)

Usage:
    python scripts/preprocess.py
"""

import csv
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT   = Path(__file__).parent.parent
INPUT_PATH  = REPO_ROOT / "data" / "annotations" / "annotation_FINAL.csv"
SPLITS_DIR  = REPO_ROOT / "data" / "splits"
SEED        = 42

# ── helpers ──────────────────────────────────────────────────────────────────

def normalise_text(text: str) -> str:
    return " ".join(text.replace("\n", " ").split())


def stratified_split(rows, label_col, ratios=(0.70, 0.15, 0.15), seed=42):
    """Split rows into (train, val, test) preserving label distribution."""
    import random
    rng = random.Random(seed)

    by_label: dict[str, list] = {}
    for r in rows:
        lbl = r[label_col]
        by_label.setdefault(lbl, []).append(r)

    train, val, test = [], [], []
    for lbl, group in by_label.items():
        rng.shuffle(group)
        n = len(group)
        n_train = int(n * ratios[0])
        n_val   = int(n * ratios[1])
        train.extend(group[:n_train])
        val.extend(group[n_train : n_train + n_val])
        test.extend(group[n_train + n_val :])

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return train, val, test


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def label_summary(rows, label="label_conflict"):
    c = Counter(r[label] for r in rows)
    total = len(rows)
    parts = "  ".join(f"{k}:{v}({100*v/total:.0f}%)" for k, v in sorted(c.items()))
    return f"{total} rows  [{parts}]"


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    if not INPUT_PATH.exists():
        print(f"[ERROR] {INPUT_PATH} not found. Run scripts/export_final.py first.")
        sys.exit(1)

    with INPUT_PATH.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

    print(f"Loaded  : {len(rows)} rows from {INPUT_PATH.name}")

    # 1. Drop rows with blank text or blank target
    before = len(rows)
    rows = [r for r in rows
            if r.get("thread_text", "").strip()
            and r.get("target_message", "").strip()]
    print(f"Dropped : {before - len(rows)} rows with blank text/target")

    # 2. Drop rows with blank label_conflict
    before = len(rows)
    rows = [r for r in rows if r.get("label_conflict", "").strip() != ""]
    print(f"Dropped : {before - len(rows)} rows with blank label")

    # 3. Normalise whitespace
    for r in rows:
        r["thread_text"]    = normalise_text(r["thread_text"])
        r["target_message"] = normalise_text(r["target_message"])

    # 3b. Remap severity: 1→0 (mild), 2→1 (moderate), 3→2 (severe)
    #     Keeps labels 0-indexed so num_labels=3, no spurious class-0 in model
    for r in rows:
        s = r.get("label_severity", "").strip()
        if s in ("1", "2", "3"):
            r["label_severity"] = str(int(s) - 1)

    # 3c. Remap type to single-label 0-indexed (take most-severe type for multi-label)
    #     personal=0, political=1, sexual/gendered=2, threat=3
    #     Priority order: threat(4) > sexual(3) > political(2) > personal(1)
    priority = {"4": 3, "3": 2, "2": 1, "1": 0}
    for r in rows:
        t = r.get("label_type", "").strip()
        if not t:
            r["label_type"] = ""
            continue
        parts = [p.strip() for p in t.split(",") if p.strip() in priority]
        if parts:
            best = max(parts, key=lambda x: priority[x])
            r["label_type"] = str(priority[best])   # 0-indexed single label

    # 4. Drop duplicate thread_ids (keep first)
    before = len(rows)
    seen: set[str] = set()
    deduped = []
    for r in rows:
        tid = r.get("thread_id", "")
        if tid not in seen:
            seen.add(tid)
            deduped.append(r)
    rows = deduped
    print(f"Dropped : {before - len(rows)} duplicate thread_ids")

    print(f"Clean   : {len(rows)} rows")
    print(f"Labels  : {label_summary(rows)}")

    # 5. Stratified split
    train_rows, val_rows, test_rows = stratified_split(rows, "label_conflict", seed=SEED)

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)

    write_csv(SPLITS_DIR / "clean.csv", rows,       fieldnames)
    write_csv(SPLITS_DIR / "train.csv", train_rows, fieldnames)
    write_csv(SPLITS_DIR / "val.csv",   val_rows,   fieldnames)
    write_csv(SPLITS_DIR / "test.csv",  test_rows,  fieldnames)

    print()
    print(f"Splits saved to {SPLITS_DIR}/")
    print(f"  train : {label_summary(train_rows)}")
    print(f"  val   : {label_summary(val_rows)}")
    print(f"  test  : {label_summary(test_rows)}")
    print()
    print("Upload data/splits/ to Kaggle as dataset 'malayalamcybercon'")
    print("Then run the Kaggle notebook.")


if __name__ == "__main__":
    main()
