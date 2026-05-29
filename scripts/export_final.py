"""
Merge all annotation_batch_*.csv files into annotation_FINAL.csv.

Run this any time after finishing (or partially finishing) a batch to
update the training data. Duplicate thread_ids are deduplicated — first
occurrence wins.

Usage:
    python scripts/export_final.py

Output:
    data/annotations/annotation_FINAL.csv
"""

import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).parent.parent
ANNO_DIR  = REPO_ROOT / "data" / "annotations"
OUT_PATH  = ANNO_DIR / "annotation_FINAL.csv"

KEEP_FIELDS = [
    "thread_id", "video_id", "num_messages", "thread_text", "target_message",
    "label_conflict", "label_severity", "label_type", "label_target", "notes",
]


def main():
    batch_files = sorted(ANNO_DIR.glob("annotation_batch_*.csv"))
    if not batch_files:
        print("[ERROR] No annotation_batch_*.csv files found in", ANNO_DIR)
        sys.exit(1)

    print(f"Found {len(batch_files)} batch file(s):")

    seen_ids: set[str] = set()
    all_rows: list[dict] = []

    for path in batch_files:
        with path.open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        annotated = [r for r in rows if r.get("label_conflict", "").strip() != ""]
        dupes     = sum(1 for r in annotated if r["thread_id"] in seen_ids)
        added     = 0
        for r in annotated:
            if r["thread_id"] not in seen_ids:
                seen_ids.add(r["thread_id"])
                all_rows.append(r)
                added += 1

        print(f"  {path.name:<45}  {len(rows):>4} total  {len(annotated):>4} annotated  {added} added  ({dupes} dupes skipped)")

    if not all_rows:
        print("\n[INFO] No annotated rows found across all batches.")
        sys.exit(0)

    with OUT_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=KEEP_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    conflict1 = sum(1 for r in all_rows if r["label_conflict"] == "1")
    conflict0 = sum(1 for r in all_rows if r["label_conflict"] == "0")
    total     = len(all_rows)

    print(f"\nWrote {total} rows → {OUT_PATH}")
    print(f"  conflict=1 : {conflict1}  ({100 * conflict1 / total:.1f}%)")
    print(f"  conflict=0 : {conflict0}  ({100 * conflict0 / total:.1f}%)")
    print(f"\nNext step:")
    print(f"    python src/train.py")


if __name__ == "__main__":
    main()
