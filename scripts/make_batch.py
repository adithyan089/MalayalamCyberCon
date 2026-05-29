"""
Generate a new annotation batch from unbatched threads.

Skips any thread_id already present in existing annotation batch CSVs so
there is no overlap between batches.

Usage:
    python scripts/make_batch.py --count 200 --annotator adithyanr
    python scripts/make_batch.py --count 100 --annotator adithyarajesh
    python scripts/make_batch.py --count all  --annotator adithyanr

Options:
    --count       Number of threads to include, or "all" for every remaining thread.
                  (default: all)
    --annotator   Name appended to the output filename.
                  (default: annotator1)
    --output      Override the output path entirely.
    --seed        Random seed for shuffling. (default: 42)

Output:
    data/annotations/annotation_batch_<annotator>.csv

The file is ready to open with:
    python src/annotate.py --annotator <annotator>
"""

import argparse
import csv
import json
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT   = Path(__file__).parent.parent
DATA_DIR    = REPO_ROOT / "data"
ANNO_DIR    = DATA_DIR / "annotations"
JSONL_FILES = [
    DATA_DIR / "raw_threads.jsonl",
    DATA_DIR / "new_threads_batch.jsonl",
]

BATCH_FIELDS = [
    "batch_id", "thread_id", "video_id", "num_messages",
    "thread_text", "target_message",
    "label_conflict", "label_severity", "label_type", "label_target",
    "notes", "adjudicated",
]


def load_all_threads() -> list[dict]:
    threads = []
    seen: set[str] = set()
    for path in JSONL_FILES:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                t = json.loads(line)
                tid = t.get("thread_id", "")
                if tid and tid not in seen:
                    seen.add(tid)
                    threads.append(t)
            except json.JSONDecodeError:
                pass
    return threads


def already_batched_ids() -> set[str]:
    """Collect thread_ids from every existing annotation batch CSV."""
    ids: set[str] = set()
    for csv_path in ANNO_DIR.glob("annotation_batch_*.csv"):
        with csv_path.open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                tid = row.get("thread_id", "").strip()
                if tid:
                    ids.add(tid)
    return ids


def highest_existing_batch_num() -> int:
    """Return the highest A#### number across all existing batches."""
    max_n = 0
    for csv_path in ANNO_DIR.glob("annotation_batch_*.csv"):
        with csv_path.open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                bid = list(row.values())[0]   # first column = batch_id
                if bid.startswith("A") and bid[1:].isdigit():
                    max_n = max(max_n, int(bid[1:]))
    return max_n


def format_thread_text(t: dict) -> str:
    lines = []
    for i, msg in enumerate(t.get("messages", [])):
        prefix = f"[{i + 1}★]" if i == t.get("target_index", len(t["messages"]) - 1) else f"[{i + 1}]"
        lines.append(f"{prefix} {msg}")
    return "\n".join(lines)


def get_target_message(t: dict) -> str:
    msgs = t.get("messages", [])
    idx  = t.get("target_index", len(msgs) - 1)
    return msgs[idx] if msgs else ""


def main():
    parser = argparse.ArgumentParser(description="Generate annotation batch from remaining threads")
    parser.add_argument("--count",      default="all", help="Number of threads (int or 'all')")
    parser.add_argument("--annotator",  default="annotator1")
    parser.add_argument("--output",     default=None,  help="Override output path")
    parser.add_argument("--seed",       type=int, default=42)
    args = parser.parse_args()

    # Resolve output path
    out_path = Path(args.output) if args.output else ANNO_DIR / f"annotation_batch_{args.annotator}.csv"
    if out_path.exists():
        print(f"[ERROR] Output file already exists: {out_path}")
        print("        Rename it or pass a different --output path to avoid overwriting work.")
        sys.exit(1)

    # Load threads and filter out already-batched ones
    all_threads  = load_all_threads()
    batched_ids  = already_batched_ids()
    remaining    = [t for t in all_threads if t.get("thread_id", "") not in batched_ids]

    print(f"Total threads across all JSONL files : {len(all_threads)}")
    print(f"Already batched                       : {len(batched_ids)}")
    print(f"Available (unbatched)                 : {len(remaining)}")

    if not remaining:
        print("\n[INFO] No unbatched threads left. Scrape more data first.")
        sys.exit(0)

    # Resolve --count
    if args.count.lower() == "all":
        count = len(remaining)
    else:
        try:
            count = int(args.count)
        except ValueError:
            print(f"[ERROR] --count must be an integer or 'all', got: {args.count!r}")
            sys.exit(1)

    count = min(count, len(remaining))

    # Shuffle and sample
    rng = random.Random(args.seed)
    rng.shuffle(remaining)
    selected = remaining[:count]

    # Assign batch IDs continuing from the last existing batch
    start_n = highest_existing_batch_num() + 1

    ANNO_DIR.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BATCH_FIELDS)
        writer.writeheader()
        for i, t in enumerate(selected):
            writer.writerow({
                "batch_id":       f"A{start_n + i:04d}",
                "thread_id":      t.get("thread_id", ""),
                "video_id":       t.get("video_id", ""),
                "num_messages":   len(t.get("messages", [])),
                "thread_text":    format_thread_text(t),
                "target_message": get_target_message(t),
                "label_conflict": "",
                "label_severity": "",
                "label_type":     "",
                "label_target":   "",
                "notes":          "",
                "adjudicated":    "",
            })

    print(f"\nBatch created  : {count} threads  (IDs A{start_n:04d}–A{start_n + count - 1:04d})")
    print(f"Saved to       : {out_path}")
    print(f"\nNext step:")
    print(f"    python src/annotate.py --annotator {args.annotator}")


if __name__ == "__main__":
    main()
