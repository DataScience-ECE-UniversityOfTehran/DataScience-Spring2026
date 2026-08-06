# Model report (Phase 3)

This is the modelling write-up for the hate speech project. Phase 2 turned the raw tweets
into a model-ready feature matrix; here we train a classifier on top of it, evaluate it on
held-out data, and wire the whole thing into two automated pipelines.

## Task

Multiclass text classification: given a tweet, predict whether it is **hate speech** (0),
**offensive language** (1), or **neither** (2). The label is the majority vote of the
CrowdFlower annotators. The dataset is heavily imbalanced — roughly 77% of tweets are
offensive, 17% neither, and only about 6% hate speech — so raw accuracy is misleading and
we lean on macro-averaged metrics that weight the three classes equally.

## Data splitting

We split the 24,781 rows into 70% train / 15% validation / 15% test, stratified on the
label so the class ratios are preserved in every split (`split_data.py`). The split is
seeded so it is reproducible and the exact row indices are saved to
`data/processed/splits.npz`. The test set is never touched during training or model
selection — it is only used once, in the prediction pipeline, for the final evaluation.

| split | rows  | hate | offensive | neither |
|-------|-------|------|-----------|---------|
| train | 17345 | 1001 | 13431     | 2913    |
| val   | 3718  | 214  | 2879      | 625     |
| test  | 3718  | 215  | 2879      | 624     |

## Models compared

We tuned four classifiers with 3-fold cross-validated grid search on the training split,
optimising macro-F1, and compared them on the validation split. The grids double as the
regularisation knobs (inverse penalty `C` for the linear models, tree depth / leaf size
for the ensembles). All models use balanced class weights to fight the imbalance.

| model         | best params            | val macro-F1 | val accuracy |
|---------------|------------------------|--------------|--------------|
| logreg        | C=3.0                  | 0.719        | 0.861        |
| **linear_svc**| **C=0.3**              | **0.752**    | **0.899**    |
| random_forest | max_depth=None, leaf=2 | 0.731        | 0.880        |
| lightgbm      | lr=0.05, leaves=31     | 0.735        | 0.882        |

The linear SVM won. That is the usual outcome for high-dimensional sparse TF-IDF features —
a linear decision boundary in a 5,000-dimensional space is expressive enough, and the tree
models don't get much extra mileage out of the sparse indicators. Every run (parameters,
metrics, and the validation confusion matrix) is logged to MLflow, and the winner is
registered in the MLflow model registry as `hate-speech-classifier`.

`LinearSVC` has no probability output, so the final model is wrapped in
`CalibratedClassifierCV` before it is saved. That gives us calibrated class probabilities
to store in the database and lets us report AUC-ROC and log loss.

## Final test results

The winner was refit on train + validation and evaluated once on the untouched test split
(`make_predictions.py`):

| metric            | value  |
|-------------------|--------|
| accuracy          | 0.903  |
| balanced accuracy | 0.670  |
| macro-F1          | 0.686  |
| weighted-F1       | 0.889  |
| MCC               | 0.723  |
| Cohen's kappa     | 0.718  |
| AUC-ROC (ovr)     | 0.929  |
| log loss          | 0.286  |

Per class:

| class     | precision | recall | F1    | support |
|-----------|-----------|--------|-------|---------|
| hate      | 0.564     | 0.163  | 0.253 | 215     |
| offensive | 0.923     | 0.961  | 0.942 | 2879    |
| neither   | 0.842     | 0.886  | 0.863 | 624     |

## What the numbers mean

The model is very good at the two common classes and struggles with hate speech, which is
both the rarest class and the hardest to separate from ordinary offensive language — the
two overlap heavily in vocabulary, and even the human annotators disagreed most on exactly
these tweets. AUC-ROC of 0.93 says the ranking is strong (the model usually assigns hate
tweets a higher hate-probability than non-hate tweets), but at the default decision
threshold it only recalls about 1 in 6 hate tweets while keeping precision above 0.5.

From a moderation standpoint that trade-off matters: the model is a reliable first-pass
filter for offensive content, but it should not be trusted to catch hate speech on its own.
A realistic deployment would lower the hate threshold (trading precision for recall) and
route borderline cases to human reviewers, using the stored probabilities to rank the queue.

## Limitations and future work

- **Hate-class recall is low.** The dataset simply has few hate examples. Resampling
  (SMOTE on the sparse features), threshold tuning, or a cost-sensitive objective would
  likely help more than a fancier model.
- **Vocabulary leakage.** The TF-IDF vectoriser is fit on the whole corpus rather than the
  training split alone. Only the vocabulary/IDF leaks (never the labels), which is mild, but
  a stricter setup would fit it inside the training pipeline only.
- **Bag-of-words ceiling.** TF-IDF ignores word order and context. A fine-tuned
  transformer (e.g. BERT) would almost certainly lift hate-class recall, at the cost of a
  much heavier pipeline.
