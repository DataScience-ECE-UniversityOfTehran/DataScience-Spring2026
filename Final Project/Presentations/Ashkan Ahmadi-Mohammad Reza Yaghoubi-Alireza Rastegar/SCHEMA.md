# Database schema

The data is stored in a SQLite database at `database/dataset.db`. The original flat CSV
(`labeled_data.csv`) is normalized into three tables so that the tweet content, the
annotation votes, and the label vocabulary are kept separate and linked by keys.

## Tables

### classes
Lookup table for the three label categories.

| column      | type    | key | notes                                  |
|-------------|---------|-----|----------------------------------------|
| class_id    | INTEGER | PK  | 0 = hate_speech, 1 = offensive, 2 = neither |
| class_name  | TEXT    |     | unique, human-readable label           |

### tweets
One row per tweet.

| column          | type    | key       | notes                          |
|-----------------|---------|-----------|--------------------------------|
| tweet_id        | INTEGER | PK        | original row index from the CSV |
| text            | TEXT    |           | raw tweet text                 |
| annotator_count | INTEGER |           | number of CF annotators (`count`) |
| class_id        | INTEGER | FK → classes(class_id) | majority label        |

### annotations
Vote breakdown for each tweet (one-to-one with `tweets`). Kept in a separate table
because these counts describe the labelling process rather than the tweet itself.

| column          | type    | key       | notes                |
|-----------------|---------|-----------|----------------------|
| tweet_id        | INTEGER | PK, FK → tweets(tweet_id) | |
| hate_votes      | INTEGER |           | annotators voting hate |
| offensive_votes | INTEGER |           | annotators voting offensive |
| neither_votes   | INTEGER |           | annotators voting neither |

An index `idx_tweets_class` on `tweets(class_id)` speeds up the per-class aggregations.

### predictions
Written by the Phase 3 prediction pipeline (`make_predictions.py`). One row per tweet in
the held-out test split, storing the model's predicted label and class probabilities so
results are queryable alongside the source data.

| column         | type    | key       | notes                                   |
|----------------|---------|-----------|-----------------------------------------|
| tweet_id       | INTEGER | PK, FK → tweets(tweet_id) | which tweet was scored   |
| true_class_id  | INTEGER |           | actual label (for evaluation)           |
| pred_class_id  | INTEGER |           | predicted label id                      |
| pred_class     | TEXT    |           | predicted label name                    |
| prob_hate      | REAL    |           | P(hate) — null if the model has no proba |
| prob_offensive | REAL    |           | P(offensive)                            |
| prob_neither   | REAL    |           | P(neither)                              |
| model_name     | TEXT    |           | which model produced the prediction     |

## Relationships

```
classes (1) ────< (many) tweets (1) ──── (1) annotations
```

- `tweets.class_id` references `classes.class_id`.
- `annotations.tweet_id` references `tweets.tweet_id`.

The three vote columns always sum to `annotator_count`, and `class_id` is the argmax of
the votes. The votes therefore fully determine the label, which is why they are **not**
used as model features (see `docs/EDA_REPORT.md`).
