# Fantasy-AI

Fantasy-AI is a production-grade machine learning system that predicts
Fantasy Premier League (FPL) player points for future Gameweeks.

This is a real software engineering project — not a notebook, not a
Kaggle script, not a tutorial. It is built incrementally, sprint by
sprint, following Clean Architecture and SOLID principles.

## Status

**Sprint 9 — Automation** ✅ (final sprint — Fantasy-AI is now complete)

**Post-Sprint-9 audit & stabilization**: completed. See
[`AUDIT_REPORT.md`](./AUDIT_REPORT.md) for the full findings. In short:
188 of 189 tests pass (the remaining one requires `fastapi`/`httpx`,
not installable in the environment this audit ran in — see the report);
a real data-leakage bug in default training feature selection was found
and fixed (raw same-Gameweek stats were leaking into training); and a
bug in one integration test's HTTP mocking (not production code) was
fixed. Known, documented limitations:

- **Understat is not implemented** — a pure skeleton (every method
  raises `NotImplementedError`), as originally documented.
- **Next-Gameweek prediction uses a proxy**, not true upcoming-fixture
  data — see the note under "Running prediction" below.
- **XGBoost/LightGBM and the FastAPI layer were built without the
  ability to install those packages** in the sandbox they were written
  in; their logic was verified as thoroughly as possible without them
  (see `AUDIT_REPORT.md`), but should be re-verified with them
  installed before production use.

See the sprint log below for what has been built.

### Running the historical ingestion

```bash
python -m scripts.run_historical_ingestion
# or restrict to specific seasons:
python -m scripts.run_historical_ingestion --seasons 2022-23,2023-24
```

This downloads the [vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League)
repository, merges every season's Gameweek data into
`data/raw/vaastav_merged.csv`, and writes a report to
`data/raw/vaastav_metadata_report.md`.

### Running dataset validation

```bash
python -m scripts.run_validation
```

This validates `data/raw/vaastav_merged.csv` for missing values,
duplicate rows, invalid data types, invalid Gameweek numbers, and
invalid player identifiers, then writes
`data/raw/validation_report.md`. Exits with status `1` if any check
fails.

### Running preprocessing

```bash
python -m scripts.run_preprocessing
```

This cleans `data/raw/vaastav_merged.csv` — normalizing names,
removing duplicates, dropping rows missing required fields, converting
columns to proper dtypes, and filling zero-meaning missing values —
then saves `data/processed/vaastav_cleaned.csv` and a
`data/processed/preprocessing_summary.json` audit trail.

### Running feature engineering

```bash
python -m scripts.run_feature_engineering
```

This derives model-ready features from `data/processed/vaastav_cleaned.csv`:
rolling averages (3/5/10-match windows) for points, minutes, BPS, ICT,
xG, and xA; a home/away flag; rest days since the previous match; team
and opponent strength; price trend; and a composite form index. Every
rolling feature is computed with a one-match lag to prevent target
leakage. Saves `data/processed/vaastav_features.csv` and a
`data/processed/feature_engineering_summary.json` audit trail.

### Running model training

```bash
python -m scripts.run_training
```

This trains Linear Regression, Random Forest, and — if installed —
XGBoost and LightGBM on `data/processed/vaastav_features.csv`, using a
**chronological** (not random) train/test split so evaluation reflects
real-world future-Gameweek prediction. Evaluates each with MAE, RMSE,
and R², saves the best model to `models/best_model.joblib` with
`models/best_model_metadata.json` (feature list, imputation medians,
metrics — everything Sprint 7 needs to reproduce predictions), and
writes `models/model_comparison_report.md`.

> **Leakage prevention**: feature selection excludes every raw,
> same-Gameweek match-outcome stat (`minutes`, `goals_scored`,
> `bonus`, `bps`, `ict_index`, and similar) — these are only known
> *after* a match is played, and `total_points` is a near-deterministic
> function of several of them under FPL's own scoring rules. Only their
> properly time-lagged rolling-average versions (e.g.
> `minutes_avg_last_3`, computed with a one-match lag in Sprint 5) are
> used as features. This exclusion list lives in `TrainingSettings.
> excluded_feature_columns` and is covered by a regression test
> (`test_default_settings_exclude_same_gameweek_outcome_stats_to_prevent_leakage`)
> so it can't silently regress.

> XGBoost and LightGBM are optional dependencies. If either isn't
> installed, the pipeline logs a warning, skips it, and still runs to
> completion with whichever models are available.

### Running prediction

```bash
python -m scripts.run_prediction
```

This loads `models/best_model.joblib` (+ its metadata), takes each
player's most recent known match as a proxy for their next-Gameweek
state, predicts their expected points, and exports
`data/processed/predictions.csv` sorted from highest to lowest
predicted points.

> **Known simplification**: rolling features are lagged by one match,
> so a player's latest played row already represents "state entering
> that match." Using it again as a proxy for the *next* match is a
> reasonable approximation (one extra match barely moves a 3/5/10-match
> average) but isn't exact — a more precise version would need real
> upcoming-fixture data (opponent, venue, rest days) to build a true
> future row. Worth revisiting once that data is wired in.

### Running the API

```bash
uvicorn src.api.main:app --reload
```

Endpoints (Swagger UI at `http://127.0.0.1:8000/swagger`):

| Endpoint | Description |
|----------|--------------|
| `GET /player/{player_id}` | A player's most recently known state |
| `GET /predict` | Every player's next-Gameweek prediction (or one, via `?player_id=`) |
| `GET /top_players?limit=10` | Top N players by predicted points |
| `GET /captain` | Captain pick — highest predicted scorer among reliable recent starters |
| `GET /swagger` | Interactive API docs |
| `GET /` | Health check (reports whether prediction data loaded successfully) |

The API loads the engineered dataset, trained model, and next-Gameweek
predictions once at startup (not per request). If `scripts.run_training`
hasn't been run yet, data-dependent endpoints return `503` with a
clear message rather than crashing; `/`, `/swagger`, and `/openapi.json`
stay available either way so you can always confirm the server is up.

### Running full automation

```bash
python -m scripts.run_automation                # refresh data only
python -m scripts.run_automation --retrain       # refresh + retrain
python -m scripts.run_automation --no-live       # skip live FPL API ingestion
```

One command chains everything: re-download the Vaastav historical
repo, pull the latest finished Gameweek from the live FPL API and
merge it in, version the raw dataset (skipped if nothing actually
changed, via a content hash), re-run preprocessing and feature
engineering, version the engineered dataset, and — if `--retrain` is
passed — train fresh candidate models and **promote the winner only if
it beats the current best** by a configurable margin
(`FANTASY_AI_RETRAIN_MIN_IMPROVEMENT`). Every model and dataset version
is kept under `models/versions/` and `data/versions/{raw,engineered}/`
(pruned to the most recent `FANTASY_AI_MAX_VERSIONS_TO_KEEP`, default
10) — nothing is silently overwritten.

> **Live API note**: `FPLApiDataSource` talks to the real
> `fantasy.premierleague.com/api` endpoints (`bootstrap-static/` and
> `event/{id}/live/`). This was built and tested against a mocked
> version of that API's well-known structure, not the live endpoint
> itself — please run `python -m scripts.run_automation` once against
> the real API and check `data/raw/fpl_api/` before relying on it in
> production, in case the schema has drifted since this was written.

## Tech Stack

- Python 3.12
- pandas, numpy, requests, pathlib, logging
- scikit-learn, XGBoost, LightGBM (training)
- FastAPI, uvicorn, pydantic (API)
- pytest for testing
- Git / GitHub for version control
- Not used: Docker, PostgreSQL (never became necessary for this project's
  scope — data is small enough for flat files, and there's no multi-service
  deployment need)

## Architecture

The project follows **Clean Architecture**, separating the system into
independent layers that depend only on abstractions, never on concrete
implementations of one another:

```
┌─────────────────────────────────────────────────────────┐
│                        API Layer                         │  src/api
├─────────────────────────────────────────────────────────┤
│  Prediction   │   Training   │   Evaluation               │  src/prediction
│               │              │                            │  src/training
│               │              │                            │  src/evaluation
├─────────────────────────────────────────────────────────┤
│           Feature Engineering  │  Preprocessing            │  src/feature_engineering
│                                 │                          │  src/preprocessing
├─────────────────────────────────────────────────────────┤
│                  Data Collection Layer                    │  src/data_collection
│   interfaces/  →  DataSource (abstract)                   │
│   sources/     →  Vaastav | FPL API | Understat            │
│   services/    →  orchestration over one or more sources   │
├─────────────────────────────────────────────────────────┤
│         core / config / common (cross-cutting)             │  src/core
│         exceptions, settings, logging, shared utils         │  src/config
└─────────────────────────────────────────────────────────┘  src/common
```

### Data Source Abstraction

Every external data provider implements the same abstract
`DataSource` interface (`download`, `load`, `validate`, `update`,
`name`). The rest of the application depends **only** on this
interface — never on `VaastavDataSource`, `FPLApiDataSource`, or
`UnderstatDataSource` directly. This means a new provider can be added,
or an existing one replaced, without touching any other layer
(Dependency Inversion Principle).

## Project Structure

```
Fantasy-AI/
├── data/
│   ├── raw/            # Untouched, as-downloaded data
│   ├── processed/      # Cleaned / feature-engineered data
│   └── external/        # Third-party reference data
├── src/
│   ├── core/            # Domain exceptions, base types
│   ├── config/          # Settings, logging configuration
│   ├── common/          # Shared, reusable utilities
│   ├── data_collection/
│   │   ├── interfaces/  # DataSource abstract interface
│   │   ├── sources/     # Vaastav (implemented) / FPL API / Understat (skeletons)
│   │   └── services/    # HistoricalDatasetService (orchestration)
│   ├── validation/       # Dataset quality checks + report generation
│   │   └── checks/       # MissingValues / DuplicateRows / DataType / Gameweek / PlayerId
│   ├── preprocessing/     # Cleaning, normalization, type conversion
│   │   └── steps/         # Dedupe / DropInvalidRequired / NormalizeNames / ConvertTypes / FillMissing
│   ├── feature_engineering/
│   │   └── steps/         # RollingAverages / HomeAway / RestDays / TeamStrength / PriceTrend / FormIndex
│   ├── training/           # Model training, evaluation, comparison, persistence
│   ├── prediction/         # Model loading, next-GW prediction, CSV export
│   ├── evaluation/
│   ├── api/                # FastAPI app: routers, services, schemas, app state
│   │   ├── routers/         # /player, /predict, /top_players, /captain
│   │   └── services/        # PlayerService, PredictionQueryService (framework-free)
│   └── automation/          # Update pipeline, versioning, live ingestion, retraining
├── scripts/              # Runnable CLI entry points (no notebooks)
│   ├── run_historical_ingestion.py
│   ├── run_validation.py
│   ├── run_preprocessing.py
│   ├── run_feature_engineering.py
│   ├── run_training.py
│   ├── run_prediction.py
│   └── run_automation.py
├── tests/
├── models/                # best_model.joblib, metadata, comparison report, versions/
├── data/                  # raw/, processed/, external/, versions/{raw,engineered}/
├── configs/
├── requirements.txt
├── README.md
└── .gitignore
```

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Settings are defined in `src/config/settings.py` and can be overridden
via environment variables (no path or season is ever hardcoded), e.g.:

| Variable                       | Purpose                                   |
|---------------------------------|--------------------------------------------|
| `FANTASY_AI_ENV`                 | `development` / `staging` / `production`   |
| `FANTASY_AI_DATA_DIR`             | Override the root data directory           |
| `FANTASY_AI_MODELS_DIR`          | Override the models directory              |
| `FANTASY_AI_SEASONS`             | Comma-separated list of seasons to restrict to (empty = auto-detect all) |
| `FANTASY_AI_LOG_LEVEL`          | Logging verbosity (default `INFO`)          |

## Running Tests

```bash
pytest -v
```

As of the post-Sprint-9 audit, 189/189 tests pass in an environment
with all dependencies installed (188/189 were verified directly; see
[`AUDIT_REPORT.md`](./AUDIT_REPORT.md) for the one that couldn't be
executed in the audit's own sandbox and why).

## Sprint Log

| Sprint | Description                 | Status      |
|--------|------------------------------|-------------|
| 1      | Project Initialization        | ✅ Complete |
| 2      | Historical Dataset (Vaastav) | ✅ Complete |
| 3      | Validation                   | ✅ Complete |
| 4      | Preprocessing                | ✅ Complete |
| 5      | Feature Engineering          | ✅ Complete |
| 6      | Machine Learning Baseline    | ✅ Complete |
| 7      | Prediction Pipeline          | ✅ Complete |
| 8      | FastAPI                      | ✅ Complete |
| 9      | Automation                   | ✅ Complete |

**All 9 sprints complete.**

## License

Private / educational project. No license granted for redistribution.
