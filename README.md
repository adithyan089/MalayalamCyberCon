# MalayalamCyberCon — NLP Conflict Detection in Malayalam YouTube Comments

Final-year NLP project detecting cyberbullying and conflict in Malayalam/Manglish YouTube comment threads.
Scrapes reply threads via YouTube Data API v3, filters for Manglish content, and applies ordinal sentiment + conflict detection models.
Annotation is done with multi-annotator agreement (Cohen's κ); evaluation uses macro-F1 and LIME explainability.
Data is never committed — all raw and processed files live in `data/` which is gitignored.
See `src/` for scraping logic, `annotation/` for label schemas, and `evaluation/` for metrics scripts.
