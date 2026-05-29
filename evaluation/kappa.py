"""
Inter-annotator agreement for MalayalamCyberCon pilot.

Usage:
    python evaluation/kappa.py

Reads:  data/annotations/pilot_annotation_*.csv
Prints: pairwise Cohen's κ for label_conflict and label_severity
        Fleiss' κ if 3+ annotators
        Threads with high disagreement (flagged for adjudication)

Interpretation of κ:
    < 0.20  Slight       0.21–0.40  Fair
    0.41–0.60  Moderate  0.61–0.80  Substantial  > 0.80  Almost perfect
"""

import csv
import sys
from itertools import combinations
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT   = Path(__file__).parent.parent
ANNOT_DIR   = REPO_ROOT / "data" / "annotations"
PILOT_CSV   = REPO_ROOT / "data" / "pilot_annotation.csv"

# ── κ interpretation ────────────────────────────────────────────────────────

def kappa_label(k: float) -> str:
    if k < 0.00: return "Poor"
    if k < 0.20: return "Slight"
    if k < 0.40: return "Fair"
    if k < 0.60: return "Moderate"
    if k < 0.80: return "Substantial"
    return "Almost perfect"

# ── Cohen's κ ───────────────────────────────────────────────────────────────

def cohen_kappa(a: list, b: list) -> float:
    """Compute Cohen's κ for two equal-length label sequences."""
    assert len(a) == len(b) and len(a) > 0
    n = len(a)
    cats = sorted(set(a) | set(b))

    # observed agreement
    po = sum(1 for x, y in zip(a, b) if x == y) / n

    # expected agreement
    pe = sum(
        (a.count(c) / n) * (b.count(c) / n)
        for c in cats
    )

    if pe == 1.0:
        return 1.0  # both annotators used only one identical category
    return (po - pe) / (1.0 - pe)

# ── Fleiss' κ ────────────────────────────────────────────────────────────────

def fleiss_kappa(ratings: list[list]) -> float:
    """
    ratings: list of rows; each row is the list of labels for one item
             from ALL annotators.
    Returns Fleiss' κ (generalises to any number of raters ≥ 2).
    """
    n_items = len(ratings)
    n_raters = len(ratings[0])
    cats = sorted({v for row in ratings for v in row})

    # n_ij  = count of category j for item i
    def cat_count(row, c):
        return row.count(c)

    # P_i = proportion of agreeing pairs for item i
    P_bar = 0.0
    for row in ratings:
        s = sum(cat_count(row, c) ** 2 for c in cats) - n_raters
        P_bar += s / (n_raters * (n_raters - 1))
    P_bar /= n_items

    # P_j = marginal proportion of category j
    P_e_bar = 0.0
    total = n_items * n_raters
    for c in cats:
        p_j = sum(cat_count(row, c) for row in ratings) / total
        P_e_bar += p_j ** 2

    if P_e_bar == 1.0:
        return 1.0
    return (P_bar - P_e_bar) / (1.0 - P_e_bar)

# ── Load annotator files ─────────────────────────────────────────────────────

def load_annotations(csv_path: Path) -> dict[str, dict]:
    """Return pilot_id → {label_conflict, label_severity, label_type, notes}."""
    rows = {}
    with csv_path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pid = row["pilot_id"].strip()
            lc  = row.get("label_conflict", "").strip()
            ls  = row.get("label_severity", "").strip()
            lt  = row.get("label_type", "").strip()
            if lc == "":
                continue  # skip unlabeled rows
            rows[pid] = {
                "label_conflict": int(lc),
                "label_severity": int(ls) if ls != "" else 0,
                "label_type":     int(lt) if lt != "" else None,
                "notes":          row.get("notes", "").strip(),
            }
    return rows

def load_all_annotators() -> dict[str, dict[str, dict]]:
    """Return annotator_name → {pilot_id → labels}."""
    files = sorted(ANNOT_DIR.glob("pilot_annotation_*.csv"))
    if not files:
        print(f"[ERROR] No annotation files found in {ANNOT_DIR}")
        print("        Run: python scripts/annotate.py --annotator <name>")
        sys.exit(1)

    annotators = {}
    for f in files:
        name = f.stem.replace("pilot_annotation_", "")
        data = load_annotations(f)
        if not data:
            print(f"[WARN]  {f.name} has no completed labels — skipping")
            continue
        annotators[name] = data
        print(f"  Loaded {len(data):>3} labels  ←  {f.name}")
    return annotators

# ── Shared pilot IDs ─────────────────────────────────────────────────────────

def shared_ids(annotators: dict[str, dict]) -> list[str]:
    """Pilot IDs that ALL annotators have labeled."""
    sets = [set(v.keys()) for v in annotators.values()]
    common = sorted(sets[0].intersection(*sets[1:]))
    return common

# ── Disagreement table ───────────────────────────────────────────────────────

def find_disagreements(
    annotators: dict[str, dict],
    ids: list[str],
    column: str,
    threshold: int = 1,
) -> list[dict]:
    """Return items where the range of labels across annotators >= threshold."""
    flagged = []
    names = list(annotators.keys())
    for pid in ids:
        vals = [annotators[n][pid][column] for n in names]
        if max(vals) - min(vals) >= threshold:
            flagged.append({"pilot_id": pid, "labels": dict(zip(names, vals))})
    return flagged

# ── Pretty-print helpers ──────────────────────────────────────────────────────

SEP  = "─" * 65
SEP2 = "═" * 65

def print_kappa_row(label: str, k: float):
    bar_len = max(0, int((k + 1) / 2 * 30))  # map [-1,1] → [0,30]
    bar = "█" * bar_len
    print(f"  {label:<20}  κ = {k:+.3f}  {bar}  [{kappa_label(k)}]")

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(SEP2)
    print("  MalayalamCyberCon — Inter-Annotator Agreement")
    print(SEP2)
    print()
    print(f"  Reading from: {ANNOT_DIR}")
    print()

    annotators = load_all_annotators()
    names = list(annotators.keys())
    n_ann = len(names)

    if n_ann < 2:
        print("\n[ERROR] Need at least 2 completed annotator files to compute κ.")
        sys.exit(1)

    ids = shared_ids(annotators)
    print(f"\n  Annotators : {', '.join(names)}")
    print(f"  Shared IDs : {len(ids)} threads\n")

    if len(ids) == 0:
        print("[ERROR] No pilot IDs are shared across all annotators.")
        print("        Check that all annotators labeled the same pilot_annotation.csv.")
        sys.exit(1)

    # ── Pairwise Cohen's κ ────────────────────────────────────────────────
    print(SEP)
    print("  Pairwise Cohen's κ")
    print(SEP)

    for col in ("label_conflict", "label_severity"):
        print(f"\n  [{col}]")
        for a, b in combinations(names, 2):
            seq_a = [annotators[a][pid][col] for pid in ids]
            seq_b = [annotators[b][pid][col] for pid in ids]
            k = cohen_kappa(seq_a, seq_b)
            print_kappa_row(f"{a} vs {b}", k)

    # label_type kappa — only on threads where both annotators said conflict=1
    type_ids = [
        pid for pid in ids
        if all(annotators[n][pid]["label_type"] is not None for n in names)
    ]
    if type_ids:
        print(f"\n  [label_type]  (conflict=1 threads only, n={len(type_ids)})")
        for a, b in combinations(names, 2):
            seq_a = [annotators[a][pid]["label_type"] for pid in type_ids]
            seq_b = [annotators[b][pid]["label_type"] for pid in type_ids]
            k = cohen_kappa(seq_a, seq_b)
            print_kappa_row(f"{a} vs {b}", k)

    # ── Fleiss' κ (3+ annotators) ─────────────────────────────────────────
    if n_ann >= 3:
        print(f"\n{SEP}")
        print("  Fleiss' κ  (all annotators)")
        print(SEP)
        for col in ("label_conflict", "label_severity"):
            ratings = [
                [annotators[n][pid][col] for n in names]
                for pid in ids
            ]
            k = fleiss_kappa(ratings)
            print_kappa_row(col, k)
        if type_ids:
            ratings = [
                [annotators[n][pid]["label_type"] for n in names]
                for pid in type_ids
            ]
            k = fleiss_kappa(ratings)
            print_kappa_row(f"label_type (n={len(type_ids)})", k)

    # ── Overall percent agreement ─────────────────────────────────────────
    print(f"\n{SEP}")
    print("  Percent Agreement (exact match, all pairs)")
    print(SEP)
    for col in ("label_conflict", "label_severity"):
        agreements = []
        for a, b in combinations(names, 2):
            seq_a = [annotators[a][pid][col] for pid in ids]
            seq_b = [annotators[b][pid][col] for pid in ids]
            pct = sum(x == y for x, y in zip(seq_a, seq_b)) / len(ids) * 100
            agreements.append(pct)
        avg = sum(agreements) / len(agreements)
        print(f"  {col:<22}  avg {avg:.1f}%")
    if type_ids:
        agreements = []
        for a, b in combinations(names, 2):
            seq_a = [annotators[a][pid]["label_type"] for pid in type_ids]
            seq_b = [annotators[b][pid]["label_type"] for pid in type_ids]
            pct = sum(x == y for x, y in zip(seq_a, seq_b)) / len(type_ids) * 100
            agreements.append(pct)
        avg = sum(agreements) / len(agreements)
        print(f"  {'label_type':<22}  avg {avg:.1f}%  (conflict=1 only, n={len(type_ids)})")

    # ── Disagreement flags ────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  Threads Flagged for Adjudication  (label range ≥ 1)")
    print(SEP)

    for col in ("label_conflict", "label_severity"):
        flagged = find_disagreements(annotators, ids, col, threshold=1)
        print(f"\n  [{col}]  — {len(flagged)} thread(s) need review")
        if flagged:
            header = f"  {'pilot_id':<10}" + "".join(f"  {n:<10}" for n in names)
            print(header)
            print("  " + "-" * (len(header) - 2))
            for item in flagged:
                row = f"  {item['pilot_id']:<10}"
                row += "".join(f"  {item['labels'][n]:<10}" for n in names)
                print(row)

    if type_ids:
        flagged = [
            {"pilot_id": pid, "labels": {n: annotators[n][pid]["label_type"] for n in names}}
            for pid in type_ids
            if len({annotators[n][pid]["label_type"] for n in names}) > 1
        ]
        print(f"\n  [label_type]  — {len(flagged)} thread(s) need review")
        if flagged:
            header = f"  {'pilot_id':<10}" + "".join(f"  {n:<10}" for n in names)
            print(header)
            print("  " + "-" * (len(header) - 2))
            for item in flagged:
                row = f"  {item['pilot_id']:<10}"
                row += "".join(f"  {str(item['labels'][n]):<10}" for n in names)
                print(row)

    # ── Notes from annotators ─────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  Annotator Notes")
    print(SEP)
    has_notes = False
    for name in names:
        for pid, data in sorted(annotators[name].items()):
            if data["notes"]:
                print(f"  {pid}  [{name}]  {data['notes']}")
                has_notes = True
    if not has_notes:
        print("  (no notes recorded)")

    print(f"\n{SEP2}")
    print("  Done.")
    print(SEP2)
    print()


if __name__ == "__main__":
    main()
