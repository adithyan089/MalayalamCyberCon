"""
Adjudication tool for MalayalamCyberCon pilot.

Usage:
    python scripts/adjudicate.py [--adjudicator name]

Reads:  data/annotations/pilot_annotation_*.csv  (completed annotator files)
        data/pilot_annotation.csv                 (thread text source)
Saves:  data/annotations/pilot_annotation_FINAL.csv

Shows only threads with disagreements. For each:
  - Displays the full thread text
  - Shows every annotator's labels side by side
  - Prompts for the final adjudicated label
  - 's' to skip (decide later), 'q' to quit and save progress

Threads with no disagreement are copied directly from majority vote.
"""

import argparse
import csv
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT    = Path(__file__).parent.parent
ANNOT_DIR    = REPO_ROOT / "data" / "annotations"
PILOT_CSV    = REPO_ROOT / "data" / "pilot_annotation.csv"
FINAL_CSV    = ANNOT_DIR / "pilot_annotation_FINAL.csv"

SEP  = "─" * 70
SEP2 = "═" * 70

# ── helpers ──────────────────────────────────────────────────────────────────

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def ask(prompt: str, valid: list[str]) -> str:
    while True:
        val = input(f"  {prompt} [{'/'.join(valid)}]: ").strip().lower()
        if val in valid:
            return val
        print(f"  Please enter one of: {', '.join(valid)}")

# ── load ─────────────────────────────────────────────────────────────────────

def load_pilot() -> dict[str, dict]:
    """pilot_id -> full row including thread_text."""
    rows = {}
    with PILOT_CSV.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows[row["pilot_id"]] = row
    return rows

def load_annotator(path: Path) -> dict[str, dict]:
    rows = {}
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pid = row["pilot_id"].strip()
            lc  = row.get("label_conflict", "").strip()
            if lc == "":
                continue
            rows[pid] = {
                "label_conflict": int(lc),
                "label_severity": int(row.get("label_severity", "0").strip() or 0),
                "label_type":     row.get("label_type", "").strip(),
                "notes":          row.get("notes", "").strip(),
            }
    return rows

def load_all() -> dict[str, dict[str, dict]]:
    files = sorted(f for f in ANNOT_DIR.glob("pilot_annotation_*.csv")
                   if "FINAL" not in f.name)
    if not files:
        print(f"[ERROR] No annotation files found in {ANNOT_DIR}")
        sys.exit(1)
    annotators = {}
    for f in files:
        name = f.stem.replace("pilot_annotation_", "")
        data = load_annotator(f)
        if data:
            annotators[name] = data
    return annotators

# ── agreement checks ─────────────────────────────────────────────────────────

def conflict_disagrees(annotators: dict, pid: str) -> bool:
    vals = [v[pid]["label_conflict"] for v in annotators.values() if pid in v]
    return max(vals) != min(vals)

def severity_disagrees(annotators: dict, pid: str) -> bool:
    vals = [v[pid]["label_severity"] for v in annotators.values() if pid in v]
    return max(vals) != min(vals)

def type_disagrees(annotators: dict, pid: str) -> bool:
    vals = [v[pid]["label_type"] for v in annotators.values() if pid in v and v[pid]["label_conflict"] == 1]
    return len(set(vals)) > 1 if vals else False

def majority(values: list[int]) -> int:
    from collections import Counter
    return Counter(values).most_common(1)[0][0]

# ── load existing final progress ─────────────────────────────────────────────

def load_final_progress() -> dict[str, dict]:
    done = {}
    if not FINAL_CSV.exists():
        return done
    with FINAL_CSV.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pid = row["pilot_id"].strip()
            if row.get("label_conflict", "").strip() != "":
                done[pid] = row
    return done

# ── save ─────────────────────────────────────────────────────────────────────

FIELDS = [
    "pilot_id", "thread_id", "video_id", "num_messages",
    "thread_text", "target_message",
    "label_conflict", "label_severity", "label_type", "notes", "adjudicated",
]

def save_final(rows: list[dict]):
    with FINAL_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

# ── display ───────────────────────────────────────────────────────────────────

def print_thread(pilot_row: dict, annotators: dict, pid: str):
    print(f"\n  Pilot ID : {pid}")
    print(f"  Video    : {pilot_row['video_id']}")
    print(f"  Messages : {pilot_row['num_messages']}")
    print()
    print("  THREAD TEXT  (* = target message)")
    print("  " + "·" * 60)
    for line in pilot_row["thread_text"].split("\n"):
        print(f"  {line}")
    print("  " + "·" * 60)
    print()
    print("  ANNOTATOR LABELS")
    header = f"  {'Annotator':<20} {'conflict':>10} {'severity':>10} {'type':>6}  notes"
    print(header)
    print("  " + "-" * 62)
    for name, data in annotators.items():
        if pid not in data:
            print(f"  {name:<20} {'(no label)':>10}")
            continue
        lc  = data[pid]["label_conflict"]
        ls  = data[pid]["label_severity"]
        lt  = data[pid]["label_type"] or "-"
        nt  = data[pid]["notes"] or ""
        print(f"  {name:<20} {lc:>10} {ls:>10} {lt:>6}  {nt}")
    print()

def print_scale():
    print("""  CONFLICT:  0 = no conflict  |  1 = conflict

  SEVERITY (only if conflict=1):
    1 = mild        (poda, dismissive, passive-aggressive)
    2 = moderate    (direct insult: mandan, kalla, koothara)
    3 = severe      (slur, threat, sexual harassment: myre, thayoli...)

  TYPE (only if conflict=1):
    1 = personal insult       (mandan, pottan, character/intelligence attack)
    2 = political/ideological (chanakam, targeted political abuse at commenter)
    3 = sexual/gendered       (objectification, sexual harassment at a user)
    4 = threat                (veettil keri thallum, physical or social threat)
""")

# ── main ─────────────────────────────────────────────────────────────────────

def adjudicate(adjudicator: str):
    pilot   = load_pilot()
    annotators = load_all()
    names   = list(annotators.keys())
    all_ids = sorted(pilot.keys())

    print(f"\nAnnotators loaded: {', '.join(names)}")

    # Classify each thread
    auto_ids   = []   # no disagreement — copy majority
    review_ids = []   # has disagreement — needs adjudication

    for pid in all_ids:
        if not all(pid in annotators[n] for n in names):
            continue   # skip if any annotator missed it
        if conflict_disagrees(annotators, pid) or severity_disagrees(annotators, pid) or type_disagrees(annotators, pid):
            review_ids.append(pid)
        else:
            auto_ids.append(pid)

    print(f"  {len(auto_ids)} threads: full agreement (auto-resolved)")
    print(f"  {len(review_ids)} threads: disagreement (need adjudication)")

    # Load any existing adjudication progress
    done = load_final_progress()

    # Build output rows — start with auto-resolved
    final_rows: dict[str, dict] = {}

    for pid in auto_ids:
        base = dict(pilot[pid])
        lc = majority([annotators[n][pid]["label_conflict"] for n in names if pid in annotators[n]])
        ls = majority([annotators[n][pid]["label_severity"] for n in names if pid in annotators[n]])
        lt_vals = [annotators[n][pid]["label_type"] for n in names if pid in annotators[n] and annotators[n][pid]["label_type"]]
        lt = lt_vals[0] if lt_vals else ""
        base["label_conflict"] = lc
        base["label_severity"] = ls
        base["label_type"]     = lt
        base["notes"]          = ""
        base["adjudicated"]    = "auto"
        final_rows[pid]        = base

    # Fill in already-adjudicated ones
    for pid, row in done.items():
        if pid in review_ids:
            final_rows[pid] = row

    pending = [pid for pid in review_ids if pid not in final_rows]

    if not pending:
        print(f"\nAll {len(review_ids)} disagreements already adjudicated.")
        save_final([final_rows[pid] for pid in all_ids if pid in final_rows])
        print(f"Final CSV saved: {FINAL_CSV}")
        return

    print(f"\n  {len(done)} already adjudicated, {len(pending)} remaining.")
    print(f"\nPress Enter to start adjudication, Ctrl+C to quit and save.\n")
    input()

    i = 0
    while i < len(pending):
        pid = pending[i]
        completed = len(done) + i + 1

        clear()
        print(SEP2)
        print(f"  Adjudication  |  {adjudicator}  |  {completed}/{len(review_ids)}")
        print(SEP2)
        print_thread(pilot[pid], annotators, pid)
        print_scale()

        # conflict
        conflict_vals = [annotators[n][pid]["label_conflict"] for n in names if pid in annotators[n]]
        severity_vals = [annotators[n][pid]["label_severity"] for n in names if pid in annotators[n]]
        type_vals     = [annotators[n][pid]["label_type"]     for n in names if pid in annotators[n]]

        c_flag = "*" if conflict_disagrees(annotators, pid) else " "
        s_flag = "*" if severity_disagrees(annotators, pid) else " "
        t_flag = "*" if type_disagrees(annotators, pid)     else " "

        print(f"  {c_flag} label_conflict  (annotators: {conflict_vals})")
        conflict = ask("Final label_conflict", ["0", "1"])

        if conflict == "0":
            severity   = "0"
            label_type = ""
        else:
            print(f"  {s_flag} label_severity  (annotators: {severity_vals})")
            severity = ask("Final label_severity", ["1", "2", "3"])
            print(f"  {t_flag} label_type      (annotators: {type_vals})")
            label_type = ask("Final label_type", ["1", "2", "3", "4"])

        notes = input("  adjudication notes (optional): ").strip()

        type_str = f"  type={label_type}" if label_type else ""
        print(f"\n  -> conflict={conflict}  severity={severity}{type_str}  notes={notes or '(none)'}")
        confirm = ask("Save?", ["y", "n", "b", "s"])

        if confirm == "b":
            if i > 0:
                i -= 1
                prev = pending[i]
                if prev in final_rows:
                    del final_rows[prev]
                save_final([final_rows[p] for p in all_ids if p in final_rows])
            continue

        if confirm == "n":
            continue

        if confirm == "s":
            print(f"  Skipped {pid} — will revisit.")
            i += 1
            continue

        # save
        base = dict(pilot[pid])
        base["label_conflict"] = int(conflict)
        base["label_severity"] = int(severity)
        base["label_type"]     = label_type
        base["notes"]          = notes
        base["adjudicated"]    = adjudicator
        final_rows[pid]        = base
        save_final([final_rows[p] for p in all_ids if p in final_rows])
        i += 1

    # Final save — include any skipped as unresolved
    clear()
    resolved   = sum(1 for pid in review_ids if pid in final_rows)
    unresolved = len(review_ids) - resolved
    print(SEP2)
    print(f"  Adjudication complete — {adjudicator}")
    print(SEP2)
    print(f"  Auto-resolved  : {len(auto_ids)}")
    print(f"  Adjudicated    : {resolved}")
    if unresolved:
        print(f"  Skipped (todo) : {unresolved}")
    print(f"\n  Final CSV: {FINAL_CSV}")
    print(SEP2)
    print("\nThis file is ready for model training.")

# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MalayalamCyberCon adjudication tool")
    parser.add_argument("--adjudicator", "-a", default="teamlead",
                        help="Your name (recorded in the final CSV)")
    args = parser.parse_args()
    try:
        adjudicate(args.adjudicator)
    except KeyboardInterrupt:
        print("\n\nExiting — progress saved. Run again to resume.")
