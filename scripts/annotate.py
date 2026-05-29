"""
Interactive CLI annotation tool for MalayalamCyberCon pilot.

Usage:
    python scripts/annotate.py --annotator yourname

Reads:  data/pilot_annotation.csv
Saves:  data/annotations/pilot_annotation_<name>.csv

Features:
- Shows one thread at a time with clear formatting
- Saves after every label so you can resume if interrupted
- Shows progress and lets you go back to fix a label
- Validates input so no accidental bad values
"""

import argparse
import csv
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT    = Path(__file__).parent.parent
INPUT_CSV    = REPO_ROOT / "data" / "pilot_annotation.csv"
ANNOTATIONS_DIR = REPO_ROOT / "data" / "annotations"

# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

SEP = "─" * 70

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def print_header(current: int, total: int, annotator: str):
    print(SEP)
    print(f"  MalayalamCyberCon Annotation  |  {annotator}  |  {current}/{total}")
    print(SEP)

def print_thread(row: dict):
    print(f"\n  Pilot ID : {row['pilot_id']}")
    print(f"  Video    : {row['video_id']}")
    print(f"  Messages : {row['num_messages']}")
    print()
    print("  THREAD TEXT  (★ = target / final message)")
    print("  " + "·" * 60)
    for line in row["thread_text"].split("\n"):
        print(f"  {line}")
    print("  " + "·" * 60)

def print_scale():
    print("""
  CONFLICT:   0 = no conflict   |   1 = conflict

  SEVERITY (only if conflict=1):
    1 = mild        (poda, dismissive, passive-aggressive)
    2 = moderate    (direct insult: mandan, kalla, koothara)
    3 = severe      (slur, threat, sexual harassment: myre, thayoli, vedi...)

  TYPE (only if conflict=1):
    1 = personal insult       (mandan, pottan, character/intelligence attack)
    2 = political/ideological (chanakam, targeted political abuse at commenter)
    3 = sexual/gendered       (objectification, sexual harassment at a user)
    4 = threat                (veettil keri thallum, physical or social threat)
""")

def ask(prompt: str, valid: list[str]) -> str:
    while True:
        val = input(f"  {prompt} [{'/'.join(valid)}]: ").strip()
        if val in valid:
            return val
        print(f"  ✗ Please enter one of: {', '.join(valid)}")

# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_input() -> list[dict]:
    with INPUT_CSV.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def load_progress(out_path: Path) -> dict[str, dict]:
    """Return dict of pilot_id → completed row."""
    done = {}
    if not out_path.exists():
        return done
    with out_path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("label_conflict", "").strip() != "":
                done[row["pilot_id"]] = row
    return done

def save_all(rows: list[dict], out_path: Path):
    fields = [
        "pilot_id", "thread_id", "video_id", "num_messages",
        "thread_text", "target_message",
        "label_conflict", "label_severity", "label_type", "notes",
    ]
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

# ---------------------------------------------------------------------------
# Main annotation loop
# ---------------------------------------------------------------------------

def annotate(annotator: str):
    ANNOTATIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ANNOTATIONS_DIR / f"pilot_annotation_{annotator}.csv"

    threads = load_input()
    done = load_progress(out_path)

    # Build working list — merge saved labels into loaded rows
    rows = []
    for t in threads:
        if t["pilot_id"] in done:
            rows.append(done[t["pilot_id"]])
        else:
            rows.append(dict(t))  # copy so we don't mutate input

    total = len(rows)
    pending_indices = [i for i, r in enumerate(rows) if r.get("label_conflict", "").strip() == ""]

    if not pending_indices:
        print(f"\nAll {total} threads already labeled. Output: {out_path}")
        return

    print(f"\nWelcome, {annotator}. {len(done)} already done, {len(pending_indices)} remaining.")
    print(f"Output will be saved to: {out_path}")
    print("\nPress Enter to start, or Ctrl+C to exit at any time.\n")
    input()

    i = 0
    while i < len(pending_indices):
        idx = pending_indices[i]
        row = rows[idx]
        completed = total - len(pending_indices) + i + 1

        clear()
        print_header(completed, total, annotator)
        print_thread(row)
        print_scale()

        # --- label_conflict ---
        conflict = ask("label_conflict", ["0", "1"])

        # --- label_severity + label_type ---
        if conflict == "0":
            severity   = "0"
            label_type = ""
        else:
            severity   = ask("label_severity", ["1", "2", "3"])
            label_type = ask("label_type",     ["1", "2", "3", "4"])

        # --- notes ---
        notes = input("  notes (optional, press Enter to skip): ").strip()

        # --- confirm ---
        type_str = f"  type={label_type}" if label_type else ""
        print(f"\n  → conflict={conflict}  severity={severity}{type_str}  notes={notes or '(none)'}")
        confirm = ask("Save this label?", ["y", "n", "b"])

        if confirm == "b":
            # go back one
            if i > 0:
                i -= 1
                prev_idx = pending_indices[i]
                rows[prev_idx]["label_conflict"] = ""
                rows[prev_idx]["label_severity"] = ""
                rows[prev_idx]["label_type"]     = ""
                rows[prev_idx]["notes"]          = ""
                save_all(rows, out_path)
            continue

        if confirm == "n":
            continue  # re-do same thread

        # save
        row["label_conflict"] = conflict
        row["label_severity"] = severity
        row["label_type"]     = label_type
        row["notes"]          = notes
        save_all(rows, out_path)
        i += 1

    clear()
    print(SEP)
    print(f"  All {total} threads labeled. Thank you, {annotator}!")
    print(f"  File saved: {out_path}")
    print(SEP)
    print("\nSend this file to the team lead for κ computation.")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MalayalamCyberCon annotation tool")
    parser.add_argument(
        "--annotator", "-a", required=True,
        help="Your name or initials (used in the output filename)"
    )
    args = parser.parse_args()
    try:
        annotate(args.annotator)
    except KeyboardInterrupt:
        print("\n\nExiting — progress saved. Run again to resume.")
