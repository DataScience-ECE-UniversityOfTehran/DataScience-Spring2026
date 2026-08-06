# Phase 3: Entity Resolution Design

Status: **Phase 3 complete** (team-level resolution, player-level auto tiers, fuzzy/Pass B review queue, and manual review of the `needs_review` queue all implemented and committed).

All numbers below are final actual counts from the live database after Phase 3a (team-level resolution), Phase 3b (player-level auto tiers + review queue generation), and Phase 3c (manual review resolution), using `token_set_ratio` implemented via `difflib.SequenceMatcher` only (no new dependency — see tooling note below). Every count has been cross-checked against `dim_players`/`dim_teams`/`player_identity_map` actual row counts, not estimated.

## 1. Team-level resolution (Phase 3a — already implemented and committed)

- Merged 24 `dim_teams` duplicate/alias pairs (`DATAMB_TEAM_NAME_ALIASES` in `migrate_schema_v2.py`) — e.g. `"Atlético Madrid"`/`"Atletico Madrid"`, `"Athletic Bilbao"`/`"Athletic Club"`, `"PSG"`/`"Paris Saint Germain"`. This recovered 401 DataMB player-season rows that were previously silently dropped because the league lookup was keyed only to the Understat spelling.
- Added `TRANSFERMARKT_CLUB_NAME_MAP` (59 manually-verified pairs) bridging `dim_teams` names to Transfermarkt's actual club names (legal-form suffixes, translations like Cologne/Köln, formal names like `Associazione Sportiva Roma`).
- `team_identity_map.transfermarkt_club_id` populated for all 119 in-scope teams: 60 `auto_exact` (simple normalized string match) + 59 `manual` (human-verified via the name map).
- 36 genuinely out-of-scope teams (Eredivisie, Primeira Liga — never in the 5-league scope) correctly left unresolved, `transfermarkt_club_id = NULL`, never queried against Transfermarkt.
- `dim_teams`: 179 → 155 rows. Zero dangling FKs verified across `player_season_stats`, `team_season_stats`, `team_identity_map`, `club_budgets`.

This is the foundation every player-level match below depends on — a player can only be club-anchored (Pass A) if their team already resolved to a `transfermarkt_club_id` here.

## 2. Tooling: difflib only, no rapidfuzz

Tested empirically, not assumed. Plain `difflib.SequenceMatcher.ratio()` gave no viable threshold on real zero-hit data (a wrong match scored 0.80, a correct match scored 0.79 — no cutoff separates them). A hand-rolled `token_set_ratio` (tokenize both names into sets, compare the intersection against each side's excess tokens, take the max pairwise ratio — ~15 lines using only `difflib.SequenceMatcher`) gave clean separation on the same pair (correct → 1.00, wrong → 0.73).

Rapidfuzz's main advantages (C-speed, built-in token scorers) don't apply here: Pass A candidate lists are per-club (~20–35 players), so the whole scoped pass is ~70,000–100,000 comparisons total — speed is a non-issue, and the token-based scorer is already reproduced in stdlib. **No `requirements.txt` change.** Revisit only if a future pass needs global (non-club-scoped) matching across the full ~50k Transfermarkt pool.

## 3. Player-level matching design, by source

### 3a. Understat (full name, e.g. "Mohamed Salah")

- **Pass A (club-anchored)**: exact normalized full-name match within the player's resolved club → `auto_exact`.
- **Pass A fuzzy**: for Pass A zero-hits, `token_set_ratio` against the same club's roster, banded (see tier table below). Never auto — always `needs_review` at some priority.
- **Pass B (no club anchor)**: for the mid-season-transfer rows (Understat rows with `team_raw` set instead of `team_id`, because the original team_title was a comma-joined "OldClub,NewClub" string with no single resolvable team). Pass B does global exact-name match first, then global `token_set_ratio` fuzzy. Every Pass B result — exact or fuzzy — lands in `needs_review`, never auto, because there's no club corroborating the identity. A unique exact-name Pass B hit gets `fast_track` priority; fuzzy or ambiguous Pass B hits get `standard`/`low_conf` priority per their score.
  - **Row count note**: `player_season_stats` has 240 such rows (season-grain — one row per player per season). Grouped to distinct `(id, player_name, team_title)` triples, this is 239 — one player, Mërgim Berisha, has the identical comma-joined team string `"Augsburg,Hoffenheim"` recorded in both the 2023 and 2024 season files, so his two season-rows collapse to one entity-resolution decision. 240 is the correct count of season-level records; 239 is the correct count of distinct resolution decisions needed (since Berisha's two rows share one outcome). Both numbers are right, they're just counting at different grains — flagging so neither gets treated as "the" final number in isolation.
- **Known blind spot**: mononym rows (single-token Understat names, e.g. "Tuta", "Bernardo") can only resolve via club + token-subset matching; no fix planned beyond what token_set_ratio already does implicitly (a mononym is trivially a token subset of a fuller name).

### 3b. DataMB full-name rows (27% of DataMB — e.g. "Cristhian Mosquera")

Identical design to Understat — same Pass A exact/fuzzy, same Pass B, same bands, same `auto_exact` evidence strength (this was an explicit correction earlier in the design process: full-name DataMB rows are NOT capped at the weaker `auto_high` tier the abbreviated format gets, since they carry the same evidence as a full Understat name).

### 3c. DataMB abbreviated rows (73% of DataMB — e.g. "A. García")

Structurally different failure mode, confirmed empirically (not assumed): a lastname-only fuzzy pass within the club produced no usable signal (best scores in a 25-row sample topped out at ~0.50 — noise level). Investigating specific cases (`J. Bednarek`, `V. Milinković-Savić`, `A. Elanga`, `M. Flekken` — all well-known, clearly real players) showed they exist in Transfermarkt's data, just under a **different current club** (they transferred since the DataMB snapshot). This is a transfer-churn / recall problem, not a spelling problem.

- **Pass A (club-anchored)**: exact initial + last-name match within the resolved club → `auto_high` (capped below Understat's `auto_exact` — an initial is inherently weaker evidence than a full first name).
- **Pass B (no club anchor)**: global exact initial + last-name match across the whole in-scope Transfermarkt pool. Recovers 217/297 (73%) of Pass A zero-hits — 206 uniquely (→ `needs_review`, `fast_track` priority, since an exact initial+surname match with only one global candidate is strong evidence despite the missing anchor) and 11 ambiguously (same initial+surname exists at 2+ clubs → `needs_review`, `standard` priority, human must disambiguate — confirmed: never auto, same rule as every other ambiguous case in this design).
- **No fuzzy pass for abbreviated rows.** The remaining 80/297 (27%) are genuinely absent from the whole in-scope Transfermarkt pool — confirmed no last-name-only fuzzy signal exists to recover them (tested; max score ~0.50, indistinguishable from chance overlap). These stay `unresolved`.

## 4. Confidence tier table

| Tier | Source(s) | Exact criteria |
|---|---|---|
| `auto_exact` | Understat, DataMB full-name | Club-anchored (Pass A), exact normalized full-name match, unique candidate in that club's Transfermarkt roster |
| `auto_high` | DataMB abbreviated | Club-anchored (Pass A), exact initial + last-name match, unique candidate in that club's roster |
| `needs_review` (`fast_track`) | All | Pass A fuzzy `token_set_ratio` ≥ 0.90 (club-anchored); **or** Pass B exact match with a single unique global candidate (any source) |
| `needs_review` (`standard`) | All | Pass A fuzzy 0.80–0.89 (club-anchored); **or** Pass B ambiguous (2+ candidates share the same identity signal across clubs) |
| `needs_review` (`low_conf`) | All | Pass A fuzzy 0.70–0.79 (club-anchored); **or** Pass B fuzzy in the same band, no club anchor |
| `unresolved` | All | Pass A fuzzy < 0.70, and no Pass B exact/fuzzy candidate ≥ 0.70; **or** the player's team never resolved to a `transfermarkt_club_id` at all (genuinely out-of-scope team) |

No tier above `needs_review` is ever assigned from a fuzzy or Pass B match, regardless of score — this was reaffirmed explicitly this session (the ≥0.90 band tests as reliably correct, but stays `needs_review`/`fast_track` rather than becoming a new auto tier, per the project's no-fuzzy-auto-accept rule).

## 5. Review queue file format

One CSV per entity type, timestamped like the collection manifests: `player_review_queue_<UTC-timestamp>.csv`, one row per candidate (a player with 2+ tied Pass B candidates gets 2+ rows, ranked), sorted by `priority` then `similarity_score` descending so `fast_track` rows surface first.

Columns: `dim_player_id, our_name, our_source (understat/datamb_full/datamb_abbrev), our_team_raw, our_position, our_league, our_seasons, pass (A/B), priority (fast_track/standard/low_conf), candidate_rank, candidate_transfermarkt_player_id, candidate_name, candidate_first_name, candidate_last_name, candidate_club_name, candidate_position, candidate_sub_position, candidate_date_of_birth, candidate_nationality, match_basis (e.g. "token_set_ratio=0.92, club-anchored" or "PassB exact initial+lastname, 2 tied candidates"), similarity_score, decision, notes`

(Team-level review queue format, for reference, unchanged from the original design: `dim_team_id, our_team_name_raw, our_team_normalized, our_known_league, candidate_transfermarkt_club_id, candidate_club_name_raw, candidate_competition_id, similarity_score, decision, notes` — already consumed during Phase 3a, since all 119 in-scope teams resolved via `auto_exact` or the human-reviewed `TRANSFERMARKT_CLUB_NAME_MAP`.)

## 6. Match report format

Per source (Understat / DataMB full-name / DataMB abbreviated) and overall:
- Counts and % in each tier (`auto_exact`/`auto_high`/`needs_review` by priority/`unresolved`)
- Coverage vs. the relevant `dim_players` denominator
- `unresolved` reason breakdown: mononym, no-club-anchor exhausted, genuinely-out-of-scope team, transfer-churn absent-from-dataset
- Precision estimate: stratified random sample (~30–50 per tier) manually checked, reported as correct/N per tier — not a single blended precision number, since `auto_exact` and a `fast_track` fuzzy match carry different evidence strength

## 7. Final actual numbers (player grain, 5,902 `dim_players`)

Rolled up to the player/entity level (best tier achieved across all of a player's season rows) — this is the number that matters, since a player only needs one good season-anchor to be identified even if other seasons of theirs come up empty. These are the **final** post-manual-review numbers, not projections — Stage 1/2/3 (algorithmic tiers) matched the design doc's projected numbers exactly on first run, and Stage 3c (manual review) numbers below are the actual applied outcome.

| Source | Total players | `auto` (`auto_exact`+`auto_high`) | `human_confirmed` | `human_rejected` | `unresolved` |
|---|---|---|---|---|---|
| Understat | 4,339 | 2,480 (57.2%) | 273 (6.3%) | 173 (4.0%) | 1,413 (32.6%) |
| DataMB (full-name + abbreviated combined) | 1,563 | 1,084 (69.4%) | 328 (21.0%) | 22 (1.4%) | 129 (8.3%) |
| **Total** | **5,902** | **3,564 (60.4%)** | **601 (10.2%)** | **195 (3.3%)** | **1,542 (26.1%)** |

Sanity checks: all source totals sum to 5,902 exactly (the real `dim_players` count); DataMB's higher auto-rate is expected since genuinely out-of-scope DataMB rows (686+328 season-rows, ~1,014 before dedup) never enter `dim_players` at all — they're filtered out upstream, so the DataMB population here is already pre-selected toward more resolvable cases. Understat's larger `unresolved` share is dominated by the transfer-churn/recall gap (Transfermarkt only exposes a player's *current* club), not by matching-algorithm weakness — this was directly verified against specific well-known players (Bednarek, Milinković-Savić, Elanga, Flekken) who exist in the dataset but under a different club than their DataMB/Understat-season team.

Also verified: zero same-club exact-name collisions exist anywhere (Understat, DataMB full-name, DataMB abbreviated) — so every `auto_exact`/`auto_high` count above is a genuinely unique candidate match, not silently masking an ambiguous tie.

### Review-queue size (candidate-row grain, not player grain)

The 796 `needs_review` figure (pre-manual-review) was a player-level summary (one entry per player, using their best available season/pass evidence). The real CSV a reviewer worked through was at **candidate-row grain** — a player with 2+ tied Pass B candidates produced 2+ rows. Computed directly, not estimated:

| Priority | Understat rows | DataMB rows | Total rows |
|---|---|---|---|
| `fast_track` | 242 | 326 | 568 |
| `standard` | 52 | 40 | 92 |
| `low_conf` | 153 | 6 | 159 |
| **Total** | **447** | **372** | **819** |

819 total rows across 796 players (the gap is entirely from ties: 92 `standard`-priority rows come from only 69 players, since ambiguous Pass B ties produce one row per tied candidate). `fast_track` is the majority (568/819, 69%) and was by far the largest single bucket — most of the manual-review workload was "confirm this one strong candidate," not "pick between several."

### Stage 3c: manual review outcome (implemented)

All 819 review-queue rows (796 distinct players) were manually reviewed and the decisions applied to `player_identity_map` in a single batch:

| Decision | Players | Resulting `match_confidence` |
|---|---|---|
| Accepted | 601 | `human_confirmed` (`transfermarkt_player_id` set to the accepted candidate) |
| Rejected | 195 | `human_rejected` (`transfermarkt_player_id` stays `NULL` — explicitly considered and ruled out, distinct from `unresolved` which was never reached) |
| **Total reviewed** | **796** | |

Of the 819 candidate-rows, 601 accept decisions came from players with a single candidate and a small number came from `standard`-tier ties where one candidate was confirmed correct and its sibling row(s) rejected (e.g. the two tied "André Silva" candidates were both rejected since neither club matched; "D. Coppola" resolved by confirming the sibling `dim_player_id` 575 match instead). Verified after applying: zero players ended up with more than one accepted candidate, and zero problematic duplicate `transfermarkt_player_id` assignments were introduced — the 8 duplicate `transfermarkt_player_id` groups found post-application are all benign cross-source or duplicate-raw-row corroboration (the same real person captured under two different source rows, e.g. an Understat full-name row and a DataMB abbreviated row both correctly resolving to the same identity), consistent with the cross-source corroboration pattern documented in the addendum below — not a matching error.

## 8. Side-fix included in this batch (unrelated to matching logic)

`understat_players_raw.player_name` had an HTML-entity-decoding bug (`O&#039;Brien` instead of `O'Brien`). Fixed in `import_to_db.py`'s `import_understat_players()` — the correct fix point since it reads already-saved raw CSVs, so it retroactively cleans existing data without requiring a re-scrape. Tested: 0 remaining `&#` entities, all downstream row counts unchanged, full pipeline re-run clean.

## 10. Addendum: cross-source corroboration signal (flagged, not implemented)

After implementing Stage 1 (Understat `auto_exact`) and Stage 2 (DataMB `auto_exact`/`auto_high`), we found **989 cases where an Understat-sourced `dim_players` row and a DataMB-sourced `dim_players` row independently matched the same `transfermarkt_player_id`** — e.g. `Daley Blind` (Understat) and `D. Blind` (DataMB) both resolved to the same Transfermarkt identity via two completely different matching heuristics (full-name-exact vs. initial+lastname). Verified: all 989 are size-2 groups, and every one is cross-source (zero same-source collisions) — this is strong corroborating evidence the two rows represent the same real person, not a bug.

**This is flagged as a future opportunity, not implemented now**: a later phase could use this signal to merge/link the corresponding Understat and DataMB `dim_players` rows into one canonical identity spanning all three sources. Out of scope for the current design — noted here so it doesn't get lost, and specifically so it isn't accidentally implemented as a side-effect of Stage 3.

## 11. Final resolved coverage (Phase 3 closeout)

Combining every tier that ends in a confirmed `transfermarkt_player_id` (`auto_exact` + `auto_high` + `human_confirmed`) against every tier that doesn't (`human_rejected` + `unresolved`), as a share of all 5,902 `dim_players`:

| | Players | % of 5,902 |
|---|---|---|
| **Resolved** (`auto_exact` + `auto_high` + `human_confirmed`) | 2,737 + 827 + 601 = **4,165** | **70.6%** |
| **Not resolved** (`human_rejected` + `unresolved`) | 195 + 1,542 = **1,737** | **29.4%** |

**70.6% of all players in scope now carry a confirmed Transfermarkt identity** (2,737 `auto_exact`, 827 `auto_high`, 601 `human_confirmed`). Of the remaining 29.4%, 195 (3.3% of the total) were specifically reviewed and rejected as incorrect candidates rather than simply never reached, and 1,542 (26.1%) never had a viable candidate at all — dominated by the structural transfer-churn/recall gap described above (Transfermarkt only exposes a player's current club) and genuinely out-of-scope teams, not by matching-algorithm weakness. This closes out Phase 3 (Entity Resolution).

## Open items / not yet decided

- No `rapidfuzz` dependency added — see tooling note above.
- The 195 `human_rejected` and 1,542 `unresolved` players have no `transfermarkt_player_id` and will not carry Transfermarkt-sourced attributes (valuation, nationality, precise date of birth) into later phases unless a future pass revisits them.

## 9. Dedup defensive check (implemented)

`populate_datamb_players_identity` dedupes on the *raw* `(player_name, team)` pair before canonicalizing the team alias — in principle two different raw alias spellings of the same canonical team could silently orphan a duplicate `dim_players` row for the same real person (the dict `key_to_player_id` would just overwrite, keeping the last-inserted row's ID and leaving the first one dangling with no row ever pointing to it). Added a cheap tracking check in `migrate_schema_v2.py`: if the same canonical `(player_name, team)` key is reached via two different raw team spellings, a `WARNING` is printed listing both. Not a full fix — just insurance so this never fails silently if the raw data changes later. Tested: re-ran the full migration and pipeline, zero warnings printed (confirms zero such collisions exist in the current data), all row counts unchanged (155 `dim_teams`, 1,563 DataMB `player_season_stats` rows, 5,902 `dim_players`).
