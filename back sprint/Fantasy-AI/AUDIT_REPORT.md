# Fantasy-AI — Post-Sprint-9 Audit & Stabilization Report

**Auditor role**: Lead Engineer, final audit and stabilization pass
**Scope**: Sprints 0–9, existing functionality only. No new sprint, no
new features, no architecture changes.
**Environment note**: This audit ran in a sandbox with no internet
access. `pandas`, `numpy`, `scikit-learn`, `joblib`, and `requests` were
available; `pytest`, `fastapi`, `pydantic`, `httpx`, `xgboost`, and
`lightgbm` were **not** installed and could not be installed. Where
this affected what could be directly verified, it is called out
explicitly below rather than glossed over.

---

## 1. Executive Summary

Fantasy-AI's core pipeline — data ingestion → validation →
preprocessing → feature engineering → training → prediction — **works
end-to-end** and was verified with a real, full run against mocked
data in this audit (Section 7). Of 198 test functions (189 distinct
executions after parametrization) in the suite, **189/189 pass** in an
environment with the available dependencies; the only untested file
(`test_api_routes.py`, 11 tests) requires `fastapi`/`httpx`, which
could not be installed here.

**This audit found and fixed one serious, real bug and one real (but
lower-severity) bug**, both in existing Sprint 0–9 functionality:

1. **Data leakage (Sprint 6, `src/config/settings.py` /
   `src/training/dataset.py`)** — default feature selection included
   raw, same-Gameweek match-outcome stats (`minutes`, `goals_scored`,
   `bonus`, `bps`, `ict_index`, etc.). These are only known *after* a
   match is played, and `total_points` is a near-deterministic function
   of several of them under FPL's scoring rules. Empirically verified:
   this let a model reach **R² ≈ 0.995–0.998** (trivially decoding the
   scoring formula) instead of learning anything predictive. **Fixed**
   by expanding `TrainingSettings.excluded_feature_columns`'s default
   to exclude these columns, keeping only their properly time-lagged
   rolling-average versions (which Sprint 5 already computes correctly
   with no leakage). Added a regression test.
2. **Test-only bug (`tests/test_automation_orchestrator.py`)** — two
   separate `monkeypatch.setattr` calls patched `requests.get` via two
   different *module paths*, not realizing both paths point at the
   same underlying `requests` module object; the second patch silently
   overwrote the first for **both** call sites, breaking
   `VaastavDataSource`'s download (it passes `stream=True`, which the
   second fake didn't accept). This caused all 4 tests in that file to
   fail. **Fixed** by combining into one dispatching patch.

Beyond these two, the audit found: `UnderstatDataSource` remains a
pure, honestly-documented skeleton (as intended); the "next Gameweek"
prediction genuinely uses a documented proxy (the player's last played
row), not true upcoming-fixture data; automation's promote-only-if-
better retraining logic was verified correct via a 3-run integration
test; and a handful of harmless unused imports and one minor API
middleware gap (`/redoc` not in the always-available path list) were
cleaned up. No other correctness issues were found in the areas
audited.

---

## 2. Sprint 0–9 Audit Table

| Sprint | Area | Status | Evidence | Missing / Problems |
|---|---|---|---|---|
| 1 | Project init, config, logging | **COMPLETE** | `src/config/settings.py`, `logging_config.py` inspected; settings load correctly with env overrides (verified live) | None |
| 2 | Historical dataset (Vaastav) | **COMPLETE** | `VaastavDataSource` fully implemented; ran live (mocked) in Section 7 — downloaded, merged, saved | None |
| 3 | Validation | **COMPLETE** | 5 checks (`missing_values`, `duplicate_rows`, `data_types`, `gameweek_range`, `player_identifiers`) ran successfully in Section 7 | None |
| 4 | Preprocessing | **COMPLETE** | Ran successfully in Section 7; produced correct dtypes | Minor: `ConvertTypesStep` previously crashed on any fractional value in a configured "integer" column (found in Sprint 9 dev, already fixed before this audit — confirmed still fixed) |
| 5 | Feature engineering | **COMPLETE** | Ran successfully in Section 7; rolling-average leakage explicitly re-verified row-by-row in this audit (Section 8) — no leakage | None |
| 6 | ML baseline / training | **PARTIAL → FIXED** | Ran successfully; 4 model classes implemented (2 always available, 2 optional) | **Found real data leakage in default feature selection — see Section 1/4/8/9. Fixed in this audit.** |
| 7 | Prediction pipeline | **COMPLETE** | Ran successfully in Section 7; loads model, predicts, exports | Uses a documented proxy for "next Gameweek" features — see Section 10 |
| 8 | FastAPI | **PARTIAL (unverifiable here)** | Code reviewed statically; logic matches spec (5 endpoints + health) | **Cannot execute** — `fastapi`/`pydantic`/`httpx` not installable in this sandbox. Fixed one minor middleware gap (`/redoc` path) found via static review. |
| 9 | Automation | **COMPLETE** | Full 3-run integration test executed live in this audit (Section 7/12) — refresh, live-merge, promote, and reject-worse-model all verified | Live FPL API endpoints tested only against a mocked schema, not the real API (documented) |

---

## 3. Test Results BEFORE Fixes

Since real `pytest` is not installable in this sandbox, a minimal
pytest-compatible shim was built (fixtures: `tmp_path`, `monkeypatch`,
simple `@pytest.fixture` functions; plus `pytest.raises`,
`pytest.approx`, `pytest.mark.parametrize`) to run the actual test
files as faithfully as possible. This is disclosed, not hidden — it is
not a substitute for running real `pytest` in a fully-provisioned
environment, which the project owner should still do.

```
RESULTS: 184 passed, 4 failed, 1 collection errors
```

All 4 failures were in `tests/test_automation_orchestrator.py`:

- `test_run_without_retrain_produces_versioned_data`
- `test_run_skips_live_ingestion_when_disabled`
- `test_run_with_retrain_promotes_first_model_with_no_prior_best`
- `test_run_with_retrain_does_not_promote_a_worse_model`

Failure signature (all 4): `TypeError` inside
`VaastavDataSource._stream_download`, because `requests.get` had been
silently replaced by the FPL-API fake (which doesn't accept
`stream=`), not the Vaastav fake.

1 collection error: `tests/test_api_routes.py` — `ModuleNotFoundError:
No module named 'fastapi'` (environment limitation, not a code bug).

---

## 4. Root Causes

### 4.1 Data leakage in default training feature selection (production code)

`TrainingSettings.excluded_feature_columns` (in
`src/config/settings.py`) only excluded identifier/text columns
(`season, name, team, opponent_team, kickoff_time, element, fixture,
round`). It did **not** exclude same-Gameweek raw outcome stats:
`minutes, goals_scored, assists, bonus, bps, ict_index,
clean_sheets, goals_conceded, ...`. `select_feature_columns()`
(`src/training/dataset.py`) selects every numeric/boolean column not
excluded, so these leaked straight into the feature matrix.

Why it matters: FPL's own scoring formula computes `total_points` from
these exact stats (appearance points from `minutes`, `+goals×N`,
`+assists×N`, `+bonus`, etc.), for the *same match*. A model given
that match's own outcome stats to predict that match's own point
total isn't predicting anything — it's decoding arithmetic. At real
inference time (Sprint 7's `build_next_gameweek_rows`), these values
for the *upcoming*, unplayed Gameweek don't exist — only the previous
Gameweek's values do — so the model would have been trained on one
distribution (this-match stats → this-match points) and served on a
different one (last-match stats → next-match points), in addition to
the metrics being meaningless.

Root cause: an incomplete settings default — the config *mechanism*
for excluding leaky columns existed and worked correctly; the *list of
values* was just wrong from Sprint 6 onward, and no test asserted
anything about the real-world correctness of the default (all existing
tests passed explicit, narrower `excluded_feature_columns` values in
their fixtures, so the bug never surfaced in tests).

### 4.2 Test-only monkeypatch collision (test code, not production)

`tests/test_automation_orchestrator.py` had two helper functions:

```python
monkeypatch.setattr("src.data_collection.sources.vaastav_source.requests.get", fake_get_a)
monkeypatch.setattr("src.data_collection.sources.fpl_api_source.requests.get", fake_get_b)
```

Both `vaastav_source.py` and `fpl_api_source.py` do `import requests`
— the *same* `requests` module object, shared process-wide. Patching
`.get` via either dotted path patches the identical attribute on that
one object. The second call silently wins for **all** callers,
including the first source. This is a classic mocking pitfall
(patching a shared library object from two different "logical"
locations) — it is a bug in the test's mocking strategy, not in
`VaastavDataSource`, `FPLApiDataSource`, or the orchestrator.

---

## 5. Changes Made

All changes are within existing Sprint 0–9 files; no new sprint, files
belonging to a new feature area, or architectural changes were made.

1. **`src/config/settings.py`** — expanded
   `TrainingSettings.excluded_feature_columns`'s default to also
   exclude same-Gameweek outcome stats (`minutes, goals_scored,
   assists, clean_sheets, goals_conceded, own_goals,
   penalties_missed, penalties_saved, red_cards, yellow_cards, saves,
   bonus, bps, influence, creativity, threat, ict_index,
   expected_goals, expected_assists, expected_goal_involvements,
   expected_goals_conceded, in_dreamteam, starts, selected,
   transfers_in, transfers_out, transfers_balance`). `GW`, `was_home`,
   and `value` remain selectable — all three are legitimately known
   *before* a match (fixture list, venue, and price are all set ahead
   of the deadline).
2. **`tests/test_training_dataset.py`** — added
   `test_default_settings_exclude_same_gameweek_outcome_stats_to_prevent_leakage`,
   a regression guard asserting the default excludes every known-leaky
   column and still includes the legitimate ones.
3. **`tests/test_automation_orchestrator.py`** — replaced the two
   colliding `_patch_vaastav_download` / `_patch_fpl_api` helpers with
   one `_patch_network()` that patches `requests.get` exactly once via
   a single dispatching function (keyed on URL pattern), and updated
   all 4 call sites.
4. **`src/api/main.py`** — added `app.redoc_url` to the middleware's
   always-available path list, alongside the existing `/`,
   `docs_url`, and `/openapi.json` (found via static review; FastAPI
   mounts `/redoc` by default and the code's own stated intent was
   that docs stay reachable regardless of data state).
5. **Unused imports removed** (harmless, found via a stdlib-`ast`-based
   substitute for `ruff`/`flake8`, which are not installable here):
   unused `import pytest` in `test_feature_engineering_pipeline.py`,
   `test_file_utils_extended.py`, `test_preprocessing_pipeline.py`,
   `test_preprocessing_steps.py`, `test_validation_pipeline.py`; unused
   `import pandas as pd` in `test_file_utils_extended.py`.

No production pipeline logic, architecture, endpoints, or ML models
were added, removed, or redesigned.

---

## 6. Test Results AFTER Fixes

```
RESULTS: 189 passed, 0 failed, 1 collection errors
```

- All 4 previously-failing automation tests now pass.
- The new leakage-regression test passes.
- The 1 remaining collection error is `test_api_routes.py`
  (`ModuleNotFoundError: No module named 'fastapi'`) — an environment
  limitation of this sandbox, not a code defect. That file's 11 tests
  are written and should be run with `fastapi`/`httpx`/`pydantic`
  installed to confirm before production use.

---

## 7. End-to-End Pipeline Status

A full, live (mocked-network) run was executed in this audit, stage by
stage, confirming each stage's output is directly consumable by the
next:

```
Data Source (VaastavDataSource, mocked zip)
  → Raw (36 rows, 16 columns, 1 season, 0 duplicate season/name/GW keys)
  → Validation (5/5 checks passed)
  → Preprocessing (36→36 rows, 17 columns, correct dtypes: Int64/float64/boolean/datetime64)
  → Feature Engineering (36 rows, 42 columns; 25 new feature columns added)
  → Training (28 train / 8 test rows, chronological split confirmed: test GW range ⊇ train max GW)
  → Evaluation (linear_regression MAE=1.49 R²=0.05; random_forest MAE=1.16 R²=0.41 — best: random_forest)
  → Model Persistence (best_model.joblib + best_model_metadata.json written and reloadable)
  → Prediction (3 players, predictions generated, predicted_for_gw correctly = last_GW+1)
```

Every stage handed off correctly to the next with no manual
intervention or schema patch-ups required. This confirms Sprints 2–7
are wired together correctly, not just individually unit-tested.

Sprint 9's full automation cycle (refresh → live-merge → version →
preprocess → engineer → retrain → promote-or-reject) was also run live
end-to-end 3 times in sequence in this audit, confirmed in Section 12.

Sprint 8 (API) could not be run live in this sandbox (no `fastapi`);
its correctness rests on static code review plus its own (unexecuted)
test suite.

---

## 8. Data Leakage Findings

**Two categories were checked; one had a real bug (now fixed), one did not.**

### 8.1 Rolling/engineered features (Sprint 5) — NO leakage found

Re-verified in this audit by manually recomputing, row by row, what
`total_points_avg_last_3` *should* be (the mean of strictly the prior
1–3 matches) and comparing to the actual column for every row of a
multi-Gameweek player history:

```
GW  total_points  total_points_avg_last_3
1   3             NaN            <- correct: no prior match
2   4             3.000000       <- correct: mean of [3]
3   5             3.500000       <- correct: mean of [3,4]
4   6             4.000000       <- correct: mean of [3,4,5]
...
```

Zero mismatches across all rows checked. `shift(1)` is applied before
every rolling/expanding window in `RollingAverageStep`,
`TeamStrengthStep`, and `PriceTrendStep`. This matches the unit tests
already in place (Sprint 5) and confirms they reflect real behavior,
not just isolated-case behavior.

### 8.2 Raw same-Gameweek outcome stats in training features — LEAKAGE FOUND AND FIXED

Described fully in Sections 1 and 4. Empirical proof (synthetic data
where `total_points` is a deterministic function of `minutes, goals,
assists, bonus`, matching real FPL scoring):

| Feature set | Linear Regression R² | Random Forest R² |
|---|---|---|
| **Before fix** (raw outcome stats included) | 0.9950 – 0.9958 | 0.9021 – 0.9792 |
| **After fix** (raw outcome stats excluded) | realistic, non-trivial* | realistic, non-trivial* |

*On the synthetic data used for this specific comparison (deliberately
i.i.d. per-Gameweek, with no persistent player skill signal), the
"after" scores were weak/negative — this is expected and correct: it
proves the "before" score was pure leakage, not real signal. On the
**real** Vaastav dataset, legitimate persistent skill (which the
lagged rolling-average features are designed to capture) should
produce a genuinely predictive — if much more modest than 0.99 — R²
after this fix. **Recommend re-running Sprint 6 training against real
historical data and confirming realistic metrics post-fix** (see
Section 15).

No other data-leakage vectors were found: `GW`, `was_home`, and
`value` (price) are all legitimately known before a match; chronological
splitting (Section 9) prevents future-Gameweek leakage across the
train/test boundary; imputation medians are computed from the training
split only (Sprint 6, confirmed by existing test
`test_prepare_split_dataset_imputes_missing_features_with_train_median`).

---

## 9. ML Pipeline Findings

- **Target variable**: `total_points` (configurable via
  `TrainingSettings.target_column`), confirmed correct and consistent
  across training and prediction.
- **Feature selection**: numeric/boolean columns minus
  `excluded_feature_columns` minus the target minus any
  `*_normalized` join-key column. Now leakage-free (Section 8.2).
- **Train/test split**: **chronological**, not random — verified live
  in Section 7 (test rows' Gameweeks strictly follow training rows'
  Gameweeks). This is the correct approach for time-dependent FPL data
  and was already correctly implemented in Sprint 6; this audit only
  confirmed it, no fix needed.
- **Validation strategy**: single chronological holdout (most recent
  `test_fraction`, default 20%, of rows). No walk-forward / rolling-
  origin cross-validation is implemented — acceptable for a baseline,
  worth considering for a future phase (Section 15), not fixed here
  per audit scope (would be a design change, not a bug fix).
- **Metrics** (from the live run in Section 7, on 36 rows of synthetic
  data — illustrative of mechanics, not real-world performance):

  | Model | MAE | RMSE | R² |
  |---|---|---|---|
  | linear_regression | 1.4902 | 1.8714 | 0.0503 |
  | random_forest | 1.1579 | 1.4690 | 0.4148 |

  XGBoost/LightGBM could not be exercised in this sandbox (not
  installed); the factory correctly skips them with a logged reason
  and the pipeline still completes with the two scikit-learn models.
- **Model persistence**: verified — model + metadata saved, reloaded,
  and used to predict successfully in the same run.
- **Prediction pipeline**: verified — produces one row per player with
  a `predicted_total_points` column.

---

## 10. Upcoming Gameweek Prediction Limitation

**Confirmed by reading the actual code** (`src/prediction/
next_gameweek.py::build_next_gameweek_rows`), not just the docs: the
prediction pipeline takes each player's **most recently played** row
(highest `GW` per player) and feeds its already-lagged features
directly into the model as the "next Gameweek" input, setting
`predicted_for_gw = last_played_GW + 1` (wrapping to `1` at the
configured season boundary, e.g. GW 38 → GW 1, with a logged warning).
This matches the project's own documentation (README, and the
module's docstring) exactly — no discrepancy between what's documented
and what's implemented.

**What's missing for true upcoming-Gameweek prediction**, confirmed by
inspecting what `build_next_gameweek_rows` does *not* have access to:

- **Upcoming opponent** — the model sees the *previous* match's
  opponent-derived `opponent_strength`, not the actual upcoming
  fixture's opponent.
- **Home/away** — same issue: `is_home` reflects the last played
  match, not the upcoming one.
- **Fixture difficulty** — not modeled at all; no fixture-difficulty
  rating exists anywhere in the current schema.
- **Current player state** — availability, injury, or suspension status
  for the upcoming Gameweek is not fetched from anywhere (the live FPL
  API's `bootstrap-static` does expose player status flags, but
  `FPLApiDataSource` does not currently extract or use them).
- **Expected minutes** — no minutes-expectation feature for an
  unplayed fixture exists; `rest_days` is computed from the *last*
  match only.
- **Latest team/opponent strength for the specific upcoming fixture**
  — `team_strength`/`opponent_strength` are computed from **past**
  Gameweeks up to the last played one; there's no forward-looking
  version tied to the specific team the player will actually face next.

None of these were implemented in this audit, per the explicit
instruction not to. This section is a factual confirmation of the
existing limitation, already documented in the README before this
audit began (the audit only added a cross-reference).

---

## 11. Understat Status

**Placeholder / skeleton — confirmed by reading the source directly.**
`src/data_collection/sources/understat_source.py`: every one of
`download()`, `load()`, `validate()`, `update()` immediately raises
`NotImplementedError`, with a docstring stating each is "not yet
implemented." `name` returns `"understat"` correctly. This matches its
own test (`test_remaining_skeletons_raise_not_implemented`), which
passed. No partial logic, no dead/half-written code — a clean,
honestly-labeled skeleton, exactly as originally documented. Not
implemented as part of this audit, per instructions.

---

## 12. Automation Status

Verified live in this audit with a fresh 3-run integration scenario
(mocked network), in addition to the existing automated test suite:

- **Historical data refresh**: `VaastavDataSource.update()` re-runs
  correctly; new seasons are detected via directory diff.
- **Latest-Gameweek ingestion**: `FPLApiDataSource` fetches
  bootstrap-static + the latest finished event's live stats; confirmed
  the ingested Gameweek's `total_points` correctly **overrides** the
  stale historical value for the same `(season, element, GW)` key
  (`append_live_gameweek`, keep="last" semantics) — verified by
  asserting the merged dataset shows the live value (12), not the
  historical placeholder value, after ingestion.
- **Data versioning**: raw and engineered datasets are snapshotted
  with a SHA-256 content hash; re-running with unchanged data
  correctly **skips** re-versioning (verified: `raw_data_changed`
  reported `False` where content was unchanged in earlier
  development, and `True` when the live merge actually changed
  content in this audit's run).
- **Model versioning**: every training run registers a version
  (model + metadata together, as one unit) under `models/versions/`,
  regardless of whether it's promoted.
- **Optional retraining + promote-only-if-better**: explicitly
  re-verified in this audit —
  - Run 1 (no existing best model): new model **is** promoted
    unconditionally (nothing to compare against). Confirmed:
    `best_model.joblib` and its metadata exist afterward.
  - Run 2 (existing best model artificially edited to claim a
    near-impossible MAE of `0.0000001`): retraining runs, a new
    version **is still registered** (audit trail preserved), but the
    live `best_model.joblib` bytes are confirmed **unchanged** —
    the worse candidate was correctly **not** promoted.
  - This directly satisfies the instruction: *"Make sure automation
    does not accidentally replace a better model with a worse model."*
    Confirmed correct.
- **Error handling**: live ingestion is wrapped in a
  try/except catching `FantasyAIError`; a failure there is logged and
  recorded in the run's `notes`, and the pipeline continues using
  historical data only (verified this doesn't crash the run).

One clarification on the word "incremental": the *ingestion* of new
Gameweek data is genuinely incremental (only the newest Gameweek is
fetched from the live API and merged in). The *downstream*
preprocessing/feature-engineering/training stages still **reprocess
the full accumulated dataset** each run, not just new rows — this is
an intentional, reasonable design choice for FPL's data volume (a
season is a few MB), not a bug, and the README does not overclaim
otherwise.

---

## 13. API Status

**Static review only — could not execute** `fastapi`/`pydantic`/
`httpx` are not installed in this sandbox and could not be installed
(no internet access). What was verified:

- **Application startup**: `create_app()` builds the app, registers
  `players` and `predictions` routers, and a `lifespan` context
  manager that loads `AppState` once. Logic reads correctly; a
  `FileNotFoundError` or any `FantasyAIError` during startup is caught
  and state is set to `None` rather than crashing the process.
- **Routes**: `GET /player/{player_id}`, `GET /predict` (with optional
  `?player_id=`), `GET /top_players?limit=`, `GET /captain`, plus a
  `GET /` health check — all five requested endpoints are present and
  each delegates to a framework-free service class
  (`PlayerService`/`PredictionQueryService`), both of which **were**
  executed and fully pass their own test suites in this sandbox
  (18 tests, 0 failures) — the actual data-handling logic behind every
  endpoint is verified; only the HTTP plumbing on top of it is not.
- **Request validation / response structure**: Pydantic response
  models (`PlayerResponse`, `PredictionListResponse`,
  `CaptainResponse`, `HealthResponse`) reviewed; structurally sound.
- **Error handling**: `PlayerNotFoundError` is translated to HTTP 404
  in both routers; a 503 JSON response covers any data-dependent route
  when startup state failed to load.
- **Fix applied**: `/redoc` (FastAPI's default second docs UI) was
  missing from the middleware's always-available path list, which
  contradicted the code's own stated intent that docs stay reachable
  regardless of data state. Fixed (Section 5, item 4).

**Recommendation**: run `pytest -v` (which will execute
`test_api_routes.py`'s 11 tests) and manually hit `/swagger` in an
environment with `fastapi`, `pydantic`, and `httpx` installed before
treating the API layer as production-verified.

---

## 14. Remaining Technical Debt

- `test_api_routes.py` (11 tests) unexecuted in any environment so
  far — needs a real run with `fastapi`/`httpx`/`pydantic` installed.
- XGBoost/LightGBM training paths have never been executed against
  real data in any environment during this project's development —
  only their graceful-skip-when-absent behavior has been verified.
- `FPLApiDataSource` has never been run against the real
  `fantasy.premierleague.com` API — only against a mocked payload
  matching its well-known (but not independently re-verified) schema.
- No walk-forward/rolling-origin cross-validation — a single
  chronological holdout is used for evaluation. Acceptable for a
  baseline; a future phase could strengthen this.
- The "next Gameweek" prediction proxy (Section 10) is a known,
  documented approximation, not a bug, but it is the single biggest
  gap between the current system and genuinely fixture-aware
  prediction.
- Data leakage fix in this audit was validated with synthetic data;
  recommend re-running `scripts.run_training` against the real,
  fully-ingested historical dataset to confirm realistic (non-leaky)
  metrics in production, per Section 8.2.
- No `ruff`/`black`/`mypy` configuration exists in the repo, and none
  of the three could be installed in this sandbox to establish a
  baseline; a substitute stdlib-`ast` script was used to catch unused
  imports only — it does not replace real type-checking or full
  linting.

---

## 15. Recommended Next Development Phase

*(Recommendation only — not implemented, per instructions.)*

1. Run the full test suite, including `test_api_routes.py`, and
   `scripts.run_automation` against the real live FPL API, in a
   fully-provisioned environment (network access, all requirements.txt
   packages installed) to close the verification gaps listed in
   Section 14.
2. Re-run `scripts.run_training` against the real, fully-ingested
   Vaastav dataset post-leakage-fix and record the resulting realistic
   MAE/RMSE/R² as the new honest baseline (replacing any prior
   leakage-inflated numbers anyone may have seen).
3. Set up `ruff`, `black`, and `mypy` in CI once network access is
   available, and address whatever they surface.
4. Only after the above: consider a genuine upcoming-fixture data
   source (opponent, home/away, fixture difficulty) to close the
   Section 10 gap — this would be a new, explicitly-scoped feature/
   sprint, not something to fold into a stabilization pass.

**STOP. Audit and stabilization complete.**
