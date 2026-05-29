"""
Merge multiple raw_threads.jsonl files from different scrapers into one.

Usage:
    python scripts/merge_jsonl.py file1.jsonl file2.jsonl [file3.jsonl ...]
    python scripts/merge_jsonl.py data/raw_A.jsonl data/raw_B.jsonl

Output: data/raw_threads.jsonl (deduplicated by thread_id)

Deduplication: if the same thread_id appears in multiple files, the first
occurrence is kept (in the order files are passed on the command line).
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT   = Path(__file__).parent.parent
OUTPUT_PATH = REPO_ROOT / "data" / "raw_threads.jsonl"

def load_jsonl(path: Path) -> list[dict]:
    threads = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                threads.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  [WARN] Skipping malformed line {i} in {path.name}: {e}")
    return threads

def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/merge_jsonl.py file1.jsonl file2.jsonl [...]")
        print("       At least 2 input files required.")
        sys.exit(1)

    input_paths = [Path(p) for p in sys.argv[1:]]

    for p in input_paths:
        if not p.exists():
            print(f"[ERROR] File not found: {p}")
            sys.exit(1)

    print(f"\nMerging {len(input_paths)} files → {OUTPUT_PATH.name}")
    print()

    seen_ids:   set[str]  = set()
    all_threads: list[dict] = []

    for path in input_paths:
        threads = load_jsonl(path)
        before  = len(all_threads)
        dupes   = 0
        for t in threads:
            tid = t.get("thread_id", "")
            if tid in seen_ids:
                dupes += 1
                continue
            seen_ids.add(tid)
            all_threads.append(t)
        added = len(all_threads) - before
        print(f"  {path.name:<35}  {len(threads):>4} threads  →  {added} added  ({dupes} duplicates skipped)")

    print(f"\n  Total unique threads: {len(all_threads)}")

    # Conflict stats
    conflict = sum(1 for t in all_threads if t.get("likely_conflict"))
    print(f"  Conflict    : {conflict} ({conflict/len(all_threads)*100:.1f}%)")
    print(f"  No conflict : {len(all_threads) - conflict} ({(len(all_threads)-conflict)/len(all_threads)*100:.1f}%)")

    # Intensity distribution
    counts = {i: 0 for i in range(6)}
    for t in all_threads:
        counts[t.get("conflict_intensity", 0)] += 1
    labels = {0:"none", 1:"mild", 2:"insult", 3:"political", 4:"slur", 5:"threat"}
    print()
    print("  Intensity distribution:")
    for i in range(6):
        print(f"    [{i}] {labels[i]:<12} {counts[i]:>4} threads")

    # Write output
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for t in all_threads:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    print(f"\n  Saved → {OUTPUT_PATH}")
    print("  Next steps:")
    print("    1. python scripts/spotcheck.py          — verify the merged dataset")
    print("    2. python scripts/export_pilot.py       — re-export pilot if needed")
    print("    3. python scripts/annotate.py --annotator <name>  — annotate")

if __name__ == "__main__":
    main()
