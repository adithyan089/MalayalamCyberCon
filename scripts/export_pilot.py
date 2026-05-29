"""
Export 30 threads for the pilot annotation round.

Selection strategy:
  - All intensity >= 3  (definite conflict signal)
  - All intensity == 2  (likely conflict)
  - Top 6 intensity == 1 by message count (borderline)
  - 10 intensity == 0   (non-conflict, random sample for balance)

Produces two files:
  data/pilot_annotation.csv  — for annotators (no auto scores, no bias)
  data/pilot_key.csv         — for team lead (includes auto intensity)

Annotators label each thread independently with:
  label_conflict  : 0 = no conflict  |  1 = conflict
  label_severity  : 0 = none, 1 = mild, 2 = moderate, 3 = severe
  notes           : free text
"""

import csv
import json
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SEED = 42          # fix random seed so the same 10 neutral threads are always picked
PILOT_SIZE = 30

# ---------------------------------------------------------------------------
# Load threads
# ---------------------------------------------------------------------------
repo_root = Path(__file__).parent.parent
jsonl_path = repo_root / "data" / "raw_threads.jsonl"
out_annotation = repo_root / "data" / "pilot_annotation.csv"
out_key        = repo_root / "data" / "pilot_key.csv"

threads = []
for i, line in enumerate(jsonl_path.open(encoding="utf-8"), 1):
    line = line.strip()
    if not line:
        continue
    try:
        threads.append(json.loads(line))
    except json.JSONDecodeError as e:
        print(f"[WARN] Skipping malformed line {i}: {e}", file=sys.stderr)

print(f"Loaded {len(threads)} threads from {jsonl_path.name}")

# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------
by_intensity: dict[int, list] = {i: [] for i in range(6)}
for t in threads:
    by_intensity[t.get("conflict_intensity", 0)].append(t)

selected = []

# All intensity >= 3
for level in [5, 4, 3]:
    selected.extend(by_intensity[level])

# All intensity 2
selected.extend(by_intensity[2])

# Top 6 intensity-1 by message count (most context = hardest to judge)
i1_sorted = sorted(by_intensity[1], key=lambda t: len(t["messages"]), reverse=True)
selected.extend(i1_sorted[:6])

# 10 random intensity-0
rng = random.Random(SEED)
neutral_pool = by_intensity[0].copy()
rng.shuffle(neutral_pool)
selected.extend(neutral_pool[:10])

# Trim to PILOT_SIZE and assign stable pilot IDs
selected = selected[:PILOT_SIZE]
print(f"Selected {len(selected)} threads for pilot:")
for level in [5, 4, 3, 2, 1, 0]:
    count = sum(1 for t in selected if t.get("conflict_intensity", 0) == level)
    if count:
        labels = {0:"none",1:"mild",2:"insult",3:"political",4:"slur",5:"threat"}
        print(f"  intensity {level} ({labels[level]}): {count}")

# ---------------------------------------------------------------------------
# Format messages for CSV cells
# ---------------------------------------------------------------------------

def format_messages(thread: dict) -> str:
    """Format thread messages as a numbered list for the CSV cell."""
    lines = []
    for i, msg in enumerate(thread["messages"]):
        prefix = f"[{i+1}]"
        if i == thread["target_index"]:
            prefix = f"[{i+1}★]"   # ★ marks the final/target message
        lines.append(f"{prefix} {msg}")
    return "\n".join(lines)


def format_target(thread: dict) -> str:
    return thread["messages"][thread["target_index"]]

# ---------------------------------------------------------------------------
# Write annotation CSV (for annotators — no auto scores)
# ---------------------------------------------------------------------------
annotation_fields = [
    "pilot_id", "thread_id", "video_id",
    "num_messages", "thread_text", "target_message",
    "label_conflict", "label_severity", "label_type", "notes",
]

with out_annotation.open("w", encoding="utf-8-sig", newline="") as f:
    # utf-8-sig adds BOM so Excel opens it correctly
    writer = csv.DictWriter(f, fieldnames=annotation_fields)
    writer.writeheader()
    for idx, t in enumerate(selected, 1):
        writer.writerow({
            "pilot_id":       f"P{idx:03d}",
            "thread_id":      t["thread_id"],
            "video_id":       t["video_id"],
            "num_messages":   len(t["messages"]),
            "thread_text":    format_messages(t),
            "target_message": format_target(t),
            "label_conflict": "",   # annotator fills: 0 or 1
            "label_severity": "",   # annotator fills: 1-3 if conflict=1
            "label_type":     "",   # annotator fills: 1-4 if conflict=1
            "notes":          "",
        })

print(f"\nAnnotation CSV → {out_annotation}")
print("  Columns: pilot_id, thread_id, video_id, num_messages,")
print("           thread_text, target_message, label_conflict, label_severity, notes")
print("  Share this file with annotators. Do NOT share pilot_key.csv.")

# ---------------------------------------------------------------------------
# Write key CSV (for team lead — includes auto intensity)
# ---------------------------------------------------------------------------
key_fields = [
    "pilot_id", "thread_id", "video_id",
    "num_messages", "auto_intensity", "auto_conflict",
    "thread_text", "target_message",
]

with out_key.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=key_fields)
    writer.writeheader()
    for idx, t in enumerate(selected, 1):
        writer.writerow({
            "pilot_id":      f"P{idx:03d}",
            "thread_id":     t["thread_id"],
            "video_id":      t["video_id"],
            "num_messages":  len(t["messages"]),
            "auto_intensity": t.get("conflict_intensity", 0),
            "auto_conflict":  t.get("likely_conflict", False),
            "thread_text":   format_messages(t),
            "target_message": format_target(t),
        })

print(f"\nKey CSV        → {out_key}")
print("  Keep this with the team lead. Compare with annotator labels after pilot.")
print("\nNext step: share pilot_annotation.csv with 2-3 annotators.")
print("Each annotator labels independently, then compute Cohen's κ.")
