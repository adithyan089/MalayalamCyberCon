"""
Adjudication script for MalayalamCyberCon.

With 3 annotators, applies majority vote (2/3) for each label.
Flags threads where all 3 disagree for manual review.
Computes Fleiss' Kappa for inter-annotator agreement.

Usage:
    python src/adjudicate.py \
        --a1 data/annotations/annotation_batch_adithyanr.csv \
        --a2 data/annotations/annotation_batch_adithyarajesh.csv \
        --a3 data/annotations/annotation_batch_annotator3.csv \
        --out data/annotations/annotation_FINAL.csv
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SEP = "─" * 65


# ── I/O ───────────────────────────────────────────────────────────────────────

def load(path: Path) -> dict[str, dict]:
    """Return {thread_id: row} from an annotated CSV."""
    rows = {}
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            tid = row["thread_id"]
            if row.get("label_conflict", "").strip() != "":
                rows[tid] = row
    return rows


# ── majority vote ─────────────────────────────────────────────────────────────

def majority(values: list[str]) -> tuple[str, bool]:
    """
    Return (winning_value, is_unanimous_or_majority).
    With 3 values, majority means 2+ agree.
    Returns ("", False) if all three differ (true 3-way split).
    """
    filled = [v for v in values if v.strip() != ""]
    if not filled:
        return "", True
    counts = Counter(filled)
    top_val, top_cnt = counts.most_common(1)[0]
    if top_cnt >= 2:
        return top_val, True
    # All three different
    return "", False


def majority_type(values: list[str]) -> tuple[str, bool]:
    """
    For label_type (potentially comma-separated multi-label).
    Majority: a type tag is included if 2+ annotators assigned it.
    """
    all_tags: list[set] = []
    for v in values:
        if v.strip():
            all_tags.append(set(v.strip().split(",")))
        else:
            all_tags.append(set())

    if not any(all_tags):
        return "", True

    # Union of all tags, keep only those with 2+ votes
    all_possible = set().union(*all_tags)
    agreed = sorted(t for t in all_possible if sum(1 for s in all_tags if t in s) >= 2)

    if agreed:
        return ",".join(agreed), True
    # No tag reached majority — flag for review
    return "", False


# ── Fleiss' Kappa ─────────────────────────────────────────────────────────────

def fleiss_kappa(annotations: list[list[str]], categories: list[str]) -> float:
    """
    Compute Fleiss' Kappa for N items, 3 raters, K categories.
    annotations: list of [r1_label, r2_label, r3_label] per item.
    categories:  list of possible label values.
    """
    n_items = len(annotations)
    n_raters = 3
    cat_index = {c: i for i, c in enumerate(categories)}
    k = len(categories)

    if n_items == 0:
        return 0.0

    # Build count matrix [n_items x k]
    mat = [[0] * k for _ in range(n_items)]
    for i, rater_labels in enumerate(annotations):
        for label in rater_labels:
            if label.strip() in cat_index:
                mat[i][cat_index[label.strip()]] += 1

    # P_i = proportion of agreeing pairs for item i
    P_i = []
    for row in mat:
        n_j_sum_sq = sum(n * (n - 1) for n in row)
        P_i.append(n_j_sum_sq / (n_raters * (n_raters - 1)) if n_raters > 1 else 0)

    P_bar = sum(P_i) / n_items

    # p_j = proportion of all assignments to category j
    total = n_items * n_raters
    p_j = [sum(mat[i][j] for i in range(n_items)) / total for j in range(k)]

    P_e = sum(pj ** 2 for pj in p_j)

    if P_e == 1.0:
        return 1.0

    return (P_bar - P_e) / (1 - P_e)


def interpret_kappa(k: float) -> str:
    if k < 0:       return "Poor (worse than chance)"
    if k < 0.20:    return "Slight"
    if k < 0.40:    return "Fair"
    if k < 0.60:    return "Moderate"
    if k < 0.80:    return "Substantial"
    return "Almost perfect"


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MalayalamCyberCon adjudication")
    parser.add_argument("--a1",  required=True, help="Annotator 1 CSV")
    parser.add_argument("--a2",  required=True, help="Annotator 2 CSV")
    parser.add_argument("--a3",  required=True, help="Annotator 3 CSV")
    parser.add_argument("--out", default="data/annotations/annotation_FINAL.csv")
    args = parser.parse_args()

    a1 = load(Path(args.a1))
    a2 = load(Path(args.a2))
    a3 = load(Path(args.a3))

    # Common thread_ids across all three
    common = set(a1) & set(a2) & set(a3)
    print(f"\nAnnotator 1 : {len(a1)} threads")
    print(f"Annotator 2 : {len(a2)} threads")
    print(f"Annotator 3 : {len(a3)} threads")
    print(f"Common (all 3 annotated) : {len(common)} threads")

    if not common:
        print("[ERROR] No threads annotated by all three annotators.")
        sys.exit(1)

    # Sort by batch_id for stable output
    sorted_ids = sorted(common, key=lambda tid: a1[tid].get("batch_id", tid))

    # ── Inter-annotator agreement ─────────────────────────────────────────────
    conflict_annotations = [
        [a1[tid]["label_conflict"], a2[tid]["label_conflict"], a3[tid]["label_conflict"]]
        for tid in sorted_ids
    ]
    severity_annotations = [
        [a1[tid]["label_severity"], a2[tid]["label_severity"], a3[tid]["label_severity"]]
        for tid in sorted_ids
        if any(a["label_conflict"] == "1" for a in [a1[tid], a2[tid], a3[tid]])
    ]

    kappa_conflict = fleiss_kappa(conflict_annotations, ["0", "1"])
    kappa_severity = fleiss_kappa(severity_annotations, ["1", "2", "3"])

    print(f"\n{SEP}")
    print(f"  Inter-Annotator Agreement (Fleiss' Kappa)")
    print(SEP)
    print(f"  Conflict  : κ = {kappa_conflict:.3f}  — {interpret_kappa(kappa_conflict)}")
    print(f"  Severity  : κ = {kappa_severity:.3f}  — {interpret_kappa(kappa_severity)}")
    print(SEP)

    # ── Adjudication ─────────────────────────────────────────────────────────
    final_rows = []
    needs_review = []

    for tid in sorted_ids:
        r1, r2, r3 = a1[tid], a2[tid], a3[tid]
        base = {k: v for k, v in r1.items()}   # carry metadata from annotator 1

        conflict_val, conflict_ok = majority(
            [r1["label_conflict"], r2["label_conflict"], r3["label_conflict"]]
        )

        if not conflict_ok:
            needs_review.append(tid)
            conflict_val = ""   # flag for manual review

        base["label_conflict"] = conflict_val

        if conflict_val == "1":
            sev_val, sev_ok = majority(
                [r1["label_severity"], r2["label_severity"], r3["label_severity"]]
            )
            if not sev_ok:
                # Use median of numeric values as fallback
                nums = sorted(
                    int(v) for v in [r1["label_severity"], r2["label_severity"], r3["label_severity"]]
                    if v.strip()
                )
                sev_val = str(nums[1]) if len(nums) >= 3 else (str(nums[0]) if nums else "")

            type_val, _ = majority_type(
                [r1["label_type"], r2["label_type"], r3["label_type"]]
            )
            target_val, target_ok = majority(
                [r1["label_target"], r2["label_target"], r3["label_target"]]
            )
            if not target_ok:
                needs_review.append(tid)
                target_val = ""

            base["label_severity"] = sev_val
            base["label_type"]     = type_val
            base["label_target"]   = target_val
        else:
            base["label_severity"] = ""
            base["label_type"]     = ""
            base["label_target"]   = ""

        # Merge notes from all three
        notes = " | ".join(
            filter(None, [r1.get("notes", ""), r2.get("notes", ""), r3.get("notes", "")])
        )
        base["notes"]       = notes
        base["adjudicated"] = "majority_vote"
        final_rows.append(base)

    # ── Write output ──────────────────────────────────────────────────────────
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "batch_id", "thread_id", "video_id", "num_messages",
        "thread_text", "target_message",
        "label_conflict", "label_severity", "label_type", "label_target",
        "notes", "adjudicated"
    ]
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(final_rows)

    conflict_count = sum(1 for r in final_rows if r["label_conflict"] == "1")
    neutral_count  = sum(1 for r in final_rows if r["label_conflict"] == "0")

    print(f"\n  Final dataset  : {len(final_rows)} threads")
    print(f"    Conflict     : {conflict_count}")
    print(f"    Neutral      : {neutral_count}")
    print(f"  Needs review   : {len(set(needs_review))} threads (all-3-disagree)")
    print(f"\n  Saved → {out_path}")

    if needs_review:
        review_path = out_path.parent / "needs_review.txt"
        review_path.write_text("\n".join(set(needs_review)), encoding="utf-8")
        print(f"  Review list → {review_path}")


if __name__ == "__main__":
    main()
