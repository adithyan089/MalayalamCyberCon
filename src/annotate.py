"""
Interactive annotation tool for MalayalamCyberCon.

Usage:
    python src/annotate.py
    python src/annotate.py --file data/annotations/annotation_batch.csv
    python src/annotate.py --annotator adithyanr

Controls:
    Enter labels when prompted.
    s  → skip this thread (come back later)
    b  → go back to previous thread
    q  → save and quit (resumes from where you left off next run)
"""

import argparse
import csv
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_FILE = REPO_ROOT / "data" / "annotations" / "annotation_batch.csv"

SEP_THICK = "═" * 65
SEP_THIN  = "─" * 65

SEVERITY_LABELS = {"1": "mild", "2": "moderate", "3": "severe"}
TYPE_LABELS     = {"1": "personal", "2": "political", "3": "sexual/gendered", "4": "threat"}
TARGET_LABELS   = {"1": "another commenter", "2": "creator/public figure", "3": "community/group"}


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def save_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def is_annotated(row: dict) -> bool:
    return row.get("label_conflict", "").strip() != ""


def print_thread(row: dict, idx: int, total: int, annotated_count: int):
    clear()
    print(SEP_THICK)
    print(f"  Thread {idx + 1} of {total}  |  Done: {annotated_count}  |  ID: {row['batch_id']}")
    print(f"  Video: {row['video_id']}  |  Messages: {row['num_messages']}")
    print(SEP_THICK)
    print()
    for line in row["thread_text"].split("\n"):
        print(f"  {line}")
    print()
    print(SEP_THIN)
    print(f"  TARGET → {row['target_message'][:120]}")
    print(SEP_THIN)


def ask(prompt: str, valid: set, allow_skip=True, allow_back=True) -> str:
    extras = []
    if allow_skip:
        extras.append("s=skip")
    if allow_back:
        extras.append("b=back")
    extras.append("q=quit")
    suffix = f"  [{', '.join(extras)}] "
    while True:
        raw = input(f"\n  {prompt}{suffix}").strip().lower()
        if raw == "q":
            return "q"
        if allow_skip and raw == "s":
            return "s"
        if allow_back and raw == "b":
            return "b"
        if raw in valid:
            return raw
        print(f"  ✗ Invalid — enter one of: {sorted(valid)}")


def annotate_row(row: dict) -> dict | None:
    """
    Returns updated row dict, or None if skipped, or 'back'/'quit' strings.
    """
    # --- label_conflict ---
    ans = ask("Conflict? (0=none, 1=conflict)", {"0", "1"})
    if ans in ("q", "s", "b"):
        return ans

    row["label_conflict"] = ans

    if ans == "0":
        row["label_severity"] = ""
        row["label_type"]     = ""
        row["label_target"]   = ""
        return row

    # --- label_severity ---
    print(f"\n  Severity:  1=mild  2=moderate  3=severe")
    ans = ask("Severity?", {"1", "2", "3"})
    if ans in ("q", "s", "b"):
        row["label_conflict"] = ""   # reset partial
        return ans
    row["label_severity"] = ans

    # --- label_type ---
    print(f"\n  Type:  1=personal  2=political  3=sexual/gendered  4=threat")
    print(f"  (comma-separate for multiple, e.g. 3,4)")
    while True:
        raw = input("  Type?  [b=back, s=skip, q=quit] ").strip().lower()
        if raw in ("q", "s", "b"):
            row["label_conflict"] = ""
            row["label_severity"] = ""
            return raw
        parts = [p.strip() for p in raw.split(",")]
        if all(p in {"1", "2", "3", "4"} for p in parts) and len(parts) >= 1:
            row["label_type"] = ",".join(sorted(set(parts)))
            break
        print("  ✗ Enter 1–4, comma-separated (e.g. 1 or 3,4)")

    # --- label_target ---
    print(f"\n  Target:  1=another commenter  2=creator/public figure  3=community/group")
    ans = ask("Target?", {"1", "2", "3"})
    if ans in ("q", "s", "b"):
        row["label_conflict"] = ""
        row["label_severity"] = ""
        row["label_type"]     = ""
        return ans
    row["label_target"] = ans

    # --- optional notes ---
    note = input("\n  Notes (optional, Enter to skip): ").strip()
    row["notes"] = note

    return row


def print_summary(rows: list[dict]):
    total     = len(rows)
    done      = sum(1 for r in rows if is_annotated(r))
    conflict  = sum(1 for r in rows if r.get("label_conflict") == "1")
    neutral   = sum(1 for r in rows if r.get("label_conflict") == "0")
    remaining = total - done
    print(SEP_THICK)
    print(f"  SESSION SUMMARY")
    print(SEP_THIN)
    print(f"  Total threads : {total}")
    print(f"  Annotated     : {done}  ({100*done//total}%)")
    print(f"    Conflict    : {conflict}")
    print(f"    Neutral     : {neutral}")
    print(f"  Remaining     : {remaining}")
    print(SEP_THICK)


def main():
    parser = argparse.ArgumentParser(description="MalayalamCyberCon annotation tool")
    parser.add_argument("--file",       default=None)
    parser.add_argument("--annotator",  default="annotator1")
    args = parser.parse_args()

    # Derive file from annotator name if not explicitly given
    if args.file:
        path = Path(args.file)
    else:
        path = REPO_ROOT / "data" / "annotations" / f"annotation_batch_{args.annotator}.csv"

    if not path.exists():
        print(f"[ERROR] File not found: {path}")
        print(f"        Run: python scripts/make_batch.py --annotator {args.annotator}")
        sys.exit(1)

    rows = load_csv(path)
    fieldnames = list(rows[0].keys())
    if "adjudicated" not in fieldnames:
        fieldnames.append("adjudicated")

    # Set annotator in adjudicated column only after adjudication — skip for now
    total = len(rows)

    # Find first unannotated index
    idx = next((i for i, r in enumerate(rows) if not is_annotated(r)), total)

    if idx == total:
        print("All threads already annotated!")
        print_summary(rows)
        return

    annotated_count = sum(1 for r in rows if is_annotated(r))
    print(f"\n  Resuming from thread {idx + 1}  ({annotated_count} already done)\n")
    input("  Press Enter to start...")

    while idx < total:
        row = rows[idx]

        if is_annotated(row):
            idx += 1
            continue

        print_thread(row, idx, total, sum(1 for r in rows if is_annotated(r)))
        result = annotate_row(row)

        if result == "q":
            save_csv(path, rows, fieldnames)
            print(f"\n  Saved. Progress: {sum(1 for r in rows if is_annotated(r))}/{total}")
            print_summary(rows)
            sys.exit(0)

        elif result == "b":
            # Go back to last annotated row
            prev = idx - 1
            while prev >= 0 and not is_annotated(rows[prev]):
                prev -= 1
            if prev < 0:
                print("  Already at the beginning.")
            else:
                rows[prev]["label_conflict"] = ""
                rows[prev]["label_severity"] = ""
                rows[prev]["label_type"]     = ""
                rows[prev]["label_target"]   = ""
                rows[prev]["notes"]          = ""
                idx = prev
                save_csv(path, rows, fieldnames)
            continue

        elif result == "s":
            idx += 1
            continue

        else:
            rows[idx] = result
            save_csv(path, rows, fieldnames)
            idx += 1

    clear()
    print("\n  All threads annotated!")
    print_summary(rows)


if __name__ == "__main__":
    main()
