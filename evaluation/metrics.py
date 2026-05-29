"""
Shared evaluation utilities for conflict detection and severity classification.
"""

import numpy as np
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
)


def conflict_report(y_true: list, y_pred: list) -> dict:
    """Binary conflict classification metrics."""
    labels = [0, 1]
    report = classification_report(
        y_true, y_pred,
        labels=labels,
        target_names=["no_conflict", "conflict"],
        output_dict=True,
        zero_division=0,
    )
    mcc = matthews_corrcoef(y_true, y_pred)
    report["mcc"] = mcc
    return report


def severity_report(y_true: list, y_pred: list) -> dict:
    """Ordinal severity classification metrics (0=mild, 1=moderate, 2=severe)."""
    labels = [0, 1, 2]
    names  = ["mild", "moderate", "severe"]
    report = classification_report(
        y_true, y_pred,
        labels=labels,
        target_names=names,
        output_dict=True,
        zero_division=0,
    )
    report["mae"] = float(np.mean(np.abs(np.array(y_true) - np.array(y_pred))))
    return report


def print_conflict_report(y_true: list, y_pred: list):
    report = conflict_report(y_true, y_pred)
    print("\n  Conflict Classification Report")
    print("  " + "─" * 50)
    for cls in ["no_conflict", "conflict"]:
        r = report[cls]
        print(f"  {cls:<14}  P={r['precision']:.3f}  R={r['recall']:.3f}  F1={r['f1-score']:.3f}  n={int(r['support'])}")
    print("  " + "─" * 50)
    print(f"  macro F1   : {report['macro avg']['f1-score']:.3f}")
    print(f"  accuracy   : {report['accuracy']:.3f}")
    print(f"  MCC        : {report['mcc']:.3f}")
    print()
    _print_cm(y_true, y_pred, ["no_conflict", "conflict"])


def print_severity_report(y_true: list, y_pred: list):
    report = severity_report(y_true, y_pred)
    names  = ["mild", "moderate", "severe"]
    print("\n  Severity Classification Report")
    print("  " + "─" * 55)
    for cls in names:
        if cls not in report:
            continue
        r = report[cls]
        print(f"  {cls:<12}  P={r['precision']:.3f}  R={r['recall']:.3f}  F1={r['f1-score']:.3f}  n={int(r['support'])}")
    print("  " + "─" * 55)
    print(f"  macro F1   : {report['macro avg']['f1-score']:.3f}")
    print(f"  weighted F1: {report['weighted avg']['f1-score']:.3f}")
    print(f"  MAE        : {report['mae']:.3f}")
    print()
    _print_cm(y_true, y_pred, names)


def type_report(y_true: list, y_pred: list) -> dict:
    """Single-label type classification (0=personal,1=political,2=sexual/gendered,3=threat)."""
    labels = [0, 1, 2, 3]
    names  = ["personal", "political", "sexual/gendered", "threat"]
    report = classification_report(
        y_true, y_pred,
        labels=labels,
        target_names=names,
        output_dict=True,
        zero_division=0,
    )
    return report


def print_type_report(y_true: list, y_pred: list):
    report = type_report(y_true, y_pred)
    names  = ["personal", "political", "sexual/gendered", "threat"]
    print("\n  Conflict Type Classification Report")
    print("  " + "─" * 55)
    for cls in names:
        if cls not in report:
            continue
        r = report[cls]
        print(f"  {cls:<16}  P={r['precision']:.3f}  R={r['recall']:.3f}  F1={r['f1-score']:.3f}  n={int(r['support'])}")
    print("  " + "─" * 55)
    print(f"  macro F1   : {report['macro avg']['f1-score']:.3f}")
    print(f"  weighted F1: {report['weighted avg']['f1-score']:.3f}")
    print()
    _print_cm(y_true, y_pred, names)


def type_report_multilabel(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Multi-label type metrics. y_true / y_pred shape: (n_samples, 4), binary int."""
    names = ["personal", "political", "sexual/gendered", "threat"]
    return classification_report(
        y_true, y_pred,
        target_names=names,
        output_dict=True,
        zero_division=0,
    )


def print_type_report_multilabel(y_true: np.ndarray, y_pred: np.ndarray):
    names  = ["personal", "political", "sexual/gendered", "threat"]
    report = type_report_multilabel(y_true, y_pred)
    print("\n  Conflict Type Classification Report (multi-label)")
    print("  " + "─" * 55)
    for cls in names:
        if cls not in report:
            continue
        r = report[cls]
        print(f"  {cls:<16}  P={r['precision']:.3f}  R={r['recall']:.3f}  F1={r['f1-score']:.3f}  n={int(r['support'])}")
    print("  " + "─" * 55)
    print(f"  macro F1   : {report['macro avg']['f1-score']:.3f}")
    print(f"  weighted F1: {report['weighted avg']['f1-score']:.3f}")
    print()


def _print_cm(y_true: list, y_pred: list, labels: list):
    unique = sorted(set(y_true) | set(y_pred))
    label_names = [labels[i] for i in unique] if all(isinstance(i, int) for i in unique) else unique
    cm = confusion_matrix(y_true, y_pred, labels=unique)
    col_w = max(len(n) for n in label_names) + 2
    print("  Confusion matrix (rows=true, cols=pred)")
    header = "  " + " " * col_w + "".join(f"{n:>{col_w}}" for n in label_names)
    print(header)
    for i, row in enumerate(cm):
        print("  " + f"{label_names[i]:>{col_w}}" + "".join(f"{v:>{col_w}}" for v in row))
    print()
