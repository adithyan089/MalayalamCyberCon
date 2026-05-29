"""
LIME explainability for MalayalamCyberCon classifiers.

Usage:
    python evaluation/lime_explain.py \
        --text "[1] poda mandan [2★] ninte taste level ariyam" \
        --task conflict \
        --model-slug xlmr_base \
        --num-samples 300

    # HTML report saved to evaluation/lime_<task>_<slug>.html
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

REPO_ROOT = Path(__file__).parent.parent

TASK_META = {
    "conflict": {"num_labels": 2, "names": ["no_conflict", "conflict"]},
    "severity": {"num_labels": 3, "names": ["mild", "moderate", "severe"]},
    "type":     {"num_labels": 4, "names": ["personal", "political", "sexual/gendered", "threat"]},
    "target":   {"num_labels": 3, "names": ["commenter", "creator/pub_fig", "community/group"]},
}


def model_dir(task: str, slug: str | None) -> Path:
    if slug:
        return REPO_ROOT / "models" / slug / task / "best"
    return REPO_ROOT / "models" / task / "best"


def load_model(task: str, slug: str | None):
    d = model_dir(task, slug)
    if not d.exists():
        sys.exit(f"[ERROR] Model not found: {d}")
    tokenizer = AutoTokenizer.from_pretrained(str(d))
    model = AutoModelForSequenceClassification.from_pretrained(str(d))
    model.eval()
    return tokenizer, model


def make_predictor(tokenizer, model, max_len: int = 256):
    """Return a function that LIME can call: list[str] → np.ndarray of probs."""
    def predict_proba(texts):
        enc = tokenizer(
            texts, truncation=True, padding="max_length",
            max_length=max_len, return_tensors="pt",
        )
        with torch.no_grad():
            logits = model(**enc).logits
        return torch.softmax(logits, dim=-1).cpu().numpy()
    return predict_proba


def explain(text: str, task: str, slug: str | None, num_samples: int, top_n: int):
    try:
        from lime.lime_text import LimeTextExplainer
    except ImportError:
        sys.exit("[ERROR] lime not installed. Run: pip install lime")

    meta = TASK_META[task]
    tokenizer, model = load_model(task, slug)
    predictor = make_predictor(tokenizer, model)

    explainer = LimeTextExplainer(class_names=meta["names"])
    exp = explainer.explain_instance(
        text,
        predictor,
        num_features=top_n,
        num_samples=num_samples,
    )

    # Console output
    print(f"\nTask : {task}  |  Model slug : {slug or 'default (MuRIL)'}")
    print(f"Text : {text[:120]}")
    print()
    pred_probs = predictor([text])[0]
    for i, (name, p) in enumerate(zip(meta["names"], pred_probs)):
        marker = " ←" if i == int(np.argmax(pred_probs)) else ""
        print(f"  {name:<20} {p:.3f}{marker}")
    print()
    print(f"Top-{top_n} token attributions (class: {meta['names'][exp.top_labels[0]]}):")
    for word, weight in exp.as_list():
        bar = "+" * int(abs(weight) * 40) if weight > 0 else "-" * int(abs(weight) * 40)
        print(f"  {word:<20} {weight:+.4f}  {bar}")

    # HTML report
    slug_label = slug or "muril"
    out_path = REPO_ROOT / "evaluation" / f"lime_{task}_{slug_label}.html"
    exp.save_to_file(str(out_path))
    print(f"\nHTML report saved → {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text",        required=True, help="Thread text to explain")
    parser.add_argument("--task",        default="conflict", choices=list(TASK_META))
    parser.add_argument("--model-slug",  default=None,
                        help="Model slug (e.g. xlmr_base). Omit to use models/<task>/best/")
    parser.add_argument("--num-samples", type=int, default=300,
                        help="LIME perturbation samples (higher = more accurate, slower)")
    parser.add_argument("--top-n",       type=int, default=15,
                        help="Number of top tokens to show")
    args = parser.parse_args()
    explain(args.text, args.task, args.model_slug, args.num_samples, args.top_n)


if __name__ == "__main__":
    main()
