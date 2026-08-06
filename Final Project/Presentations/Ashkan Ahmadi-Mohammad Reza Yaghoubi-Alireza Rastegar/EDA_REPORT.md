# EDA and preprocessing notes

Dataset: Hate Speech and Offensive Language (Davidson et al.), 24,783 labelled tweets.
The figures referenced below are produced by `eda/eda.py` and saved in `eda/figures/`.

## Structure

Every tweet was rated by a panel of CrowdFlower annotators. Each row stores the raw
text, the number of annotators, the vote split across the three categories, and the
majority label (`class`). There are no missing values in any column and no duplicate
tweets. Panel size is 3 for the large majority of tweets (22,807 of them); a smaller
group was rated by 6, and a handful by 4, 7, or 9 annotators (see Q4 in
`sql/query_outputs.txt`).

## Class balance

The dataset is heavily imbalanced (`01_class_distribution.png`):

| class      | count  | share  |
|------------|--------|--------|
| offensive  | 19,190 | 77.4%  |
| neither    | 4,163  | 16.8%  |
| hate       | 1,430  | 5.8%   |

Hate speech is the rare class at under 6%. This matters for the modeling phase — plain
accuracy will be misleading, so the eventual classifier should be judged on macro-F1 or
per-class recall, and class weighting / resampling is worth considering.

## Length

Raw tweets average 85 characters (median 81, max 754). Length barely separates the
classes: after cleaning, the mean word count is ~12.9 for hate and offensive and ~13.6
for neither (`02_wordcount_by_class.png`, `03_charcount_hist.png`). Length on its own is
a weak signal; the content of the text carries the information.

## Annotator agreement

Agreement is the share of the panel that voted for the winning label. It is high for
offensive (0.92) and neither (0.90) but noticeably lower for hate (0.73), and 70.5% of
all tweets are unanimous (`04_annotator_agreement.png`). Hate speech is the hardest
category for humans to agree on, and it sits close to the offensive class: 3,311 tweets
labelled offensive still received at least one hate vote (Q5). This overlap is the main
reason the task is hard.

## Vocabulary

Top tokens per class are in `05_top_words_by_class.png`. Offensive and hate tweets are
dominated by profanity and slurs, while the neither class is built from ordinary
conversational words. There is shared profanity between the offensive and hate classes,
which again points to the difficulty of separating the two.

## Feature engineering

Two feature groups are built in `scripts/feature_engineering.py`:

- **Structural / lexical** (13 features): character and word counts, average word length,
  unique-word ratio, counts of `!`, `?`, mentions, hashtags, URLs, digits, all-caps
  words, the uppercase-letter ratio, and elongated characters (e.g. "soooo"). These are
  standardized with `StandardScaler`. A correlation check at |r| > 0.95 found no pair
  worth dropping (`results/structural_correlation.csv`); the strongest pair, character
  vs. word count, stays below that threshold.
- **TF-IDF** on the cleaned text: word 1–2 grams, `min_df=5`, `max_features=5000`,
  sublinear term frequency, English stop words removed.

The two groups are combined into a single sparse matrix `X` of shape (24,781 × 5,013)
with labels `y`, saved alongside the fitted vectorizer and scaler so the modeling phase
can load them directly.

## What was deliberately excluded

The vote columns (`hate_votes`, `offensive_votes`, `neither_votes`) are **not** used as
features. The label is the argmax of those votes, so including them would leak the target
and produce an unrealistically perfect model. They are kept in the database and used only
for EDA.

## Cleaning decisions

`scripts/preprocess.py` unescapes HTML entities (`&amp;` → `&`), lowercases, strips URLs,
`@mentions`, the `RT` marker, and the `#` from hashtags (keeping the word), then removes
everything that is not a letter. Two tweets become empty after cleaning (they were only
mentions/links) and are dropped, leaving 24,781 rows.
