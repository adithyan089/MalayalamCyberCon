# MalayalamCyberCon — NLP Conflict Detection in Malayalam YouTube Comments

Final-year NLP project detecting cyberbullying and conflict in Malayalam/Manglish YouTube comment threads.
Scrapes reply threads via YouTube Data API v3, filters for Manglish content, and classifies across four tasks.
Annotation uses multi-annotator agreement (Cohen's κ); evaluation uses macro-F1 per task.
Data is never committed — all raw and processed files live in `data/` which is gitignored.
See `src/` for scraping and inference logic, `annotation/` for label schemas, and `evaluation/` for metrics and LIME explainability.

## Tasks

| Task       | Classes | Notes |
|------------|---------|-------|
| Conflict   | 0/1     | Binary; all threads |
| Severity   | mild / moderate / severe | Conflict=1 only |
| Type       | personal / political / sexual/gendered / threat | Conflict=1 only |
| Target     | commenter / creator/pub_fig / community/group   | Conflict=1 only |

## Models

Three transformer backbones compared on all four tasks (macro-F1 on held-out test set):

| Model                   | Conflict | Severity | Type  | Target |
|-------------------------|----------|----------|-------|--------|
| xlm-roberta-base        | 0.780    | 0.389    | 0.344 | TBD    |
| google/muril-base-cased | 0.747    | 0.368    | 0.337 | TBD    |
| xlm-roberta-large       | 0.773    | 0.411    | 0.309 | TBD    |

**Recommended model:** `xlm-roberta-base` (best conflict + type, competitive severity, lighter than large).
MuRIL underperforms because Manglish is written in Roman script — MuRIL's Indic-script pre-training provides no advantage here.

## Inference

```bash
# Single thread — default (legacy MuRIL) model layout
python src/predict.py --text "[1] poda mandan [2★] ninte taste level ariyam"

# With a specific model slug (from comparison run)
python src/predict.py --model-slug xlmr_base --text "..."

# Batch prediction from JSONL
python src/predict.py --model-slug xlmr_base --csv data/raw_threads.jsonl --output results.csv
```

## LIME Explainability

```bash
pip install lime
python evaluation/lime_explain.py \
    --text "[1] poda mandan [2★] ninte taste level ariyam" \
    --task conflict \
    --model-slug xlmr_base \
    --num-samples 300
# Saves HTML report to evaluation/lime_conflict_xlmr_base.html
```
