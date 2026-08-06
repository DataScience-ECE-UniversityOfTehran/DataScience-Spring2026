# Stack Overflow C++ Similar-Question Recommender — Phase 3

Phase 3 takes the exploratory recommender from Phase 2 and turns it into a
**production-shaped, end-to-end machine-learning system**: several candidate
models are compared and the best is selected, it is trained and evaluated with
proper ranking metrics, and it is wired into **two automated pipelines** — one
that **trains** the model and one that **predicts** and **saves recommendations
back into the database**. Two bonus tracks are included: **MLflow** experiment
tracking and a **Prefect** DAG that orchestrates the whole pipeline.

## Task

The task is unchanged from Phase 2: **semantic similar-question recommendation**.
Given a C++ question, return the most similar previously-asked questions. The
"prediction" the model makes is a **ranked list of the nearest questions**; those
recommendations are what we save back to the database.

## Phase 3 coverage

| Phase 3 section | Delivered implementation |
| --- | --- |
| 1. Model development & task definition | Seven candidates compared — `title_word_tfidf`, `document_word_tfidf`, `char_wb_tfidf`, `lsa_document`, **`bm25_document`**, **`document_prf`** (pseudo-relevance feedback), and a **hybrid** — under a temporal train/validation/test split; best chosen by **cross-validated nDCG@10**. |
| 2. Model training & evaluation | **BM25 tuned** on validation; hybrid weights searched via Dirichlet sampling with 5-fold CV; the selected model is evaluated **once** on the held-out test set with Hit@K, Recall@K, MAP@K, MRR@K, nDCG@K and a **graded** `gnDCG@K`, plus random/popularity baselines, a **leave-one-out ablation**, and an **error analysis**. |
| 3. Integration into the pipeline (automation) | Separate **training** (`train_pipeline.py`) and **prediction** (`predict_pipeline.py`) pipelines; `run_pipeline.py` runs both with one command. Predictions are written to a `recommendations` table in SQLite. **MMR diversity** re-ranking is available at inference. |
| 3 (bonus). Workflow-automation tool | The same stages are also orchestrated as a **Prefect DAG** — `orchestration/pipeline_flow.py` — the *Airflow/Prefect* option from the brief. Prefect only orchestrates, so the results are identical; it adds task-level retries, logging, and a UI/graph view. |
| 4. MLflow model management (bonus) | Every training run logs params, metrics, and artefacts (model + report) to a local `mlruns/` store; browse with the MLflow UI. |
| 5. Final presentation video | Google Drive link provided in **`video_link.txt`** at the project root. |

## Results (26,162-question dataset)

Split (temporal): **train = 18,313**, validation = 3,000, test = 3,000.

**Section 1 — model selection (cross-validated nDCG@10 on validation):**

| Model | CV nDCG@10 | | Model | CV nDCG@10 |
| --- | --- | --- | --- | --- |
| **hybrid** ✅ | **0.759 ± 0.011** | | lsa_document | 0.705 ± 0.012 |
| char_wb_tfidf | 0.739 ± 0.011 | | document_prf | 0.681 ± 0.011 |
| bm25_document (tuned) | 0.726 ± 0.011 | | document_word_tfidf | 0.676 ± 0.011 |
| | | | title_word_tfidf | 0.376 ± 0.007 |

The **hybrid** blend wins; the **character n-gram** model is the strongest single
component (see the ablation), while BM25, LSA, and PRF add complementary signal.

**Section 2 — selected model on the held-out test set vs. baselines:**

| | Hit@10 | MRR@10 | nDCG@10 |
| --- | --- | --- | --- |
| **hybrid model** | **0.893** | **0.710** | **0.559** |
| popularity baseline | 0.105 | 0.056 | 0.019 |
| random baseline | 0.376 | 0.138 | 0.059 |

The recommender lands a relevant neighbour in the top-10 for ~**89%** of unseen
questions (95.5% coverage) — about **2.4×** the random baseline and far above
popularity. (Hit@5 = 0.836, Hit@20 = 0.931.)

## Models and enhancements (no embeddings, fully reproducible)

- **BM25** — Okapi BM25, the classic probabilistic ranker used by search engines,
  implemented **dependency-free** on a `CountVectorizer`. It *saturates* term
  frequency and *penalises long documents*, so it ranks differently from cosine
  TF-IDF. Its `k1`/`b` are **tuned on validation**.
- **Pseudo-relevance feedback (`document_prf`)** — Rocchio query expansion: retrieve
  once, assume the top-M are relevant, add their centroid to the query, retrieve
  again. Pulls in related vocabulary the query never mentioned.
- **Graded nDCG (`gnDCG`)** — a fairer metric that credits candidates sharing *more*
  tags, reported next to the strict binary metrics.
- **MMR diversity** — optional Maximal-Marginal-Relevance re-ranking at inference to
  avoid near-duplicate recommendations (`recommend(..., diversity=λ)`).
- **Ablation + error analysis** — leave-one-out contribution of each hybrid component,
  and the hardest test queries surfaced for inspection.
- **Interactive CLI** — `scripts/recommend_cli.py` for live demos.

All of the above are lexical/latent (no neural embeddings) and run in CI and Docker.

## Project structure

```text
Phase3/
├── data/                              # Generated; excluded from Git
│   ├── stackoverflow_questions.db     #   SQLite DB (incl. the recommendations table)
│   ├── processed/preprocessed_questions.csv
│   ├── models/best_recommender.joblib #   deployment artefact
│   ├── models/holdout_test_ids.json   #   unseen questions reserved for prediction
│   └── reports/*.csv, *.json          #   metric tables + recommendations.csv
├── scripts/
│   ├── database_connection.py         # shared SQLite connection (from Phase 2)
│   ├── import_to_db.py                 # CSV → normalized SQLite (from Phase 2)
│   ├── load_data.py                   # DB → Pandas (from Phase 2)
│   ├── preprocess.py                  # technical text cleaning (from Phase 2)
│   ├── recommender.py                 # NEW: models (BM25, PRF), metrics (graded), hybrid, MMR, inference
│   ├── train_model.py                 # NEW: training stage (tune, select, ablation, error analysis, MLflow)
│   ├── make_predictions.py            # NEW: prediction stage (retrieve, save to DB)
│   └── recommend_cli.py               # NEW: interactive demo (by question id or free text; MMR)
├── train_pipeline.py                   # training pipeline (single command)
├── predict_pipeline.py                 # prediction pipeline (single command)
├── run_pipeline.py                     # both pipelines end-to-end
├── orchestration/pipeline_flow.py      # BONUS: same stages as a Prefect DAG
├── docs/prefect_pipeline_run.png       # BONUS: Prefect UI — successful DAG run
├── tests/                              # pytest: metrics, BM25, models, inference
├── phase3_report.ipynb                 # executed report: selection, metrics, live demo
├── requirements.txt
├── pyproject.toml
└── docs/PHASE3_REPORT.md               # full walkthrough (Persian + English)
```

The reusable data/DB scripts are shared with Phase 2 so the whole project stays
consistent; the recommender, training, and prediction code is new in Phase 3.

## Installation

Python 3.11+, from this directory:

```bash
python -m pip install -r requirements.txt
```

The pipeline reads the source data from `../Phase1/stackoverflow_questions.csv`.

## Run it

**Everything, one command** (training then prediction):

```bash
python run_pipeline.py
```

**Or the two pipelines separately:**

```bash
python train_pipeline.py     # import → load → preprocess → train & select model (+ MLflow)
python predict_pipeline.py   # load → preprocess → retrieve top-K → save to the database
```

The prediction stage also accepts options when run directly:

```bash
python scripts/make_predictions.py --top-k 10        # recommendations per query (default 10)
python scripts/make_predictions.py --all             # predict for every question, not just the holdout
```

**Interactive demo (great for the presentation/video):**

```bash
# free-text query, with MMR diversity on:
python scripts/recommend_cli.py --text "how to std::move a vector into a thread" --diversity 0.7
# an existing question by id:
python scripts/recommend_cli.py --question-id 79907170 --top-k 5
```

### The two pipelines

- **Training pipeline** — `import_to_db → load_data → preprocess → train_model`.
  Splits temporally, fits every candidate on the training corpus, selects the best
  by cross-validated nDCG@10, tunes the hybrid weights, evaluates once on test,
  refits the chosen model on train+validation, and saves `best_recommender.joblib`.
  The **test questions are reserved** as the unseen data for prediction.
- **Prediction pipeline** — `load_data → preprocess → make_predictions`.
  Loads the saved model (**never retrains**), retrieves the top-K similar questions
  for each reserved holdout question, and writes them to the database.

### Predictions in the database

Recommendations are stored in a `recommendations` table:

| column | meaning |
| --- | --- |
| `query_question_id` | the question being matched |
| `rank` | 1 = most similar |
| `recommended_question_id` | a similar historical question |
| `score` | similarity score |
| `model_name` | model that produced it |
| `generated_at` | UTC timestamp |

```sql
SELECT r.rank, q.title, r.score
FROM recommendations r JOIN questions q ON q.question_id = r.recommended_question_id
WHERE r.query_question_id = 79907170
ORDER BY r.rank;
```

A CSV copy is also written to `data/reports/recommendations.csv`.

## Prefect orchestration (bonus)

The Phase 3 brief lets you automate the pipeline three ways: a plain
`run_pipeline.py`, GitHub Actions, or a **workflow-automation tool (Apache Airflow
or Prefect)**. We ship the last one too: `orchestration/pipeline_flow.py` defines
the exact same stages as a **Prefect DAG**

```text
import_to_db → load_data → preprocess → train_model → make_predictions
```

so the whole train-then-predict workflow runs as one observable graph with
task-level state, retries, and logging. Prefect only *orchestrates* — every stage
is seeded, so the metrics are byte-for-byte identical to `run_pipeline.py`.

```bash
pip install prefect
# optional: start the UI first, then open http://127.0.0.1:4200
prefect server start
# run the DAG
python orchestration/pipeline_flow.py
```

`docs/prefect_pipeline_run.png` is a screenshot of a successful run in the Prefect
UI (all five tasks `Completed`).

## MLflow (bonus)

Training logs to a local file store under `mlruns/`. Browse and compare runs:

```bash
mlflow ui --backend-store-uri mlruns      # then open http://127.0.0.1:5000
```

If MLflow is not installed the pipeline still runs — tracking degrades to a log
message, so the core deliverable never depends on the bonus.

## Tests and linting

```bash
python -m pytest          # metrics, BM25 correctness, model interface, inference
python -m ruff check .    # style + common bugs
```

## Reports and evidence

`phase3_report.ipynb` is committed **with outputs saved**: the model-selection
table and chart, the test metrics, the baseline comparison, a **live
recommendation demo**, and the stored predictions read back from SQLite. It loads
the pipeline's outputs rather than retraining, so the report always matches the
code. `docs/PHASE3_REPORT.md` is a step-by-step walkthrough in Persian and English.
