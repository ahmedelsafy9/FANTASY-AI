# Fantasy-AI — Fixture-Aware Prediction Roadmap (Phases 1-7)

Implemented on top of the completed Sprint 0-9 build and the subsequent
audit. This document is the honest record of what changed, what was
verified, and what wasn't.

## Environment note (read first)

This sandbox has **no internet access**. Every change below was
implemented as real, production code and verified with mocked-network
integration tests (the same approach used throughout Sprints 2-9) —
but **no real training run against the actual Vaastav dataset or the
live FPL API happened here**. Where the original task description
stated specific numbers (866 predictions, an XGBoost baseline of
MAE=0.7588, etc.), this repository had **no such artifacts on disk** —
no trained model, no processed dataset — when this work began. Those
numbers could not be reproduced or compared against here; they can
only be generated in an environment with real network access, by
running `scripts.run_automation --retrain` against this code.

## Phase 1 — Fixture-aware prediction engine

**Root cause of the `opponent_strength` bug, investigated**: Vaastav's
`team` column is always a real team name; `opponent_team` is
inconsistent across seasons — some store the real name, some store a
small integer (an FPL internal team ID). `TeamStrengthStep`'s
domain-compatibility check (built in Sprint 5) correctly detected this
mismatch and skipped the join rather than silently corrupting data —
but skipping isn't a fix.

**The fix**: `TeamMappingService` (new) builds a team-ID → name mapping
from the live FPL API's `bootstrap-static` teams list. A new
preprocessing step, `NormalizeOpponentIdStep`, resolves a numeric
`opponent_team` column to team names using that mapping *before*
feature engineering runs. `TeamStrengthStep`'s existing join then
succeeds. Verified end-to-end with a regression test
(`test_run_fixes_opponent_strength_domain_mismatch_end_to_end`) that
reproduces the exact bug scenario and confirms `opponent_strength` is
populated afterward, not all-NaN.

**Known limitation, documented not hidden**: FPL team IDs are not
guaranteed stable across seasons (promotion/relegation causes ID
reuse). The mapping is built from the *current* live API snapshot, so
it's correct for the current/most recent season's opponent IDs — the
common case in practice — but a numeric ID from an older season that
has since been reassigned to a different club could resolve
incorrectly. There is no way to fully solve this without a
season-indexed historical ID mapping, which the public API doesn't
expose. Flagged in `team_mapping_service.py`'s module docstring.

**New feature**: `team_form_trend` (short-window minus long-window
rolling team strength — positive = team improving, negative =
declining). Leakage-safe: built with the same `shift(1)`-before-window
pattern as every other rolling feature in this codebase, verified with
an explicit no-leakage test.

**Chronological split preserved**: no change to `prepare_split_dataset`
or the train/test split logic — the new features are additive columns
that flow through the *existing* leakage-safe pipeline.

## Phase 2 — Retrain and evaluate

`ModelTrainer`, `select_feature_columns`, and the comparison-report
writer required **no changes** — they already operate on whatever
columns are present in the engineered dataset. Verified:
`opponent_strength` and `team_form_trend` are not in
`TrainingSettings.excluded_feature_columns`, and a full
`AutomationOrchestrator.run(retrain=True)` cycle was executed against
mocked data, confirming the new columns appear in
`best_model_metadata.json`'s `feature_columns` list and in
`model_comparison_report.md`.

**I did not, and could not, compare against your stated baseline.**
No baseline exists in this repository. Please run
`python -m scripts.run_automation --retrain` yourself (with the real
pipeline already populated) and compare the new
`model_comparison_report.md` against your own prior one — that
comparison has to happen in an environment with the real data, and I
won't pretend to have done it here.

## Phase 3 — Improve next-Gameweek prediction

**Confirmed the reported problem was real**: the original
`build_next_gameweek_rows` used each player's last-played row as a
proxy, wrapping `predicted_for_gw` to `1` for every player at the
season's final Gameweek — exactly the "866 players" symptom described.

**Fix, not a hide**: `build_fixture_aware_next_gameweek_rows` (new)
fetches real upcoming fixtures from the FPL API's `/fixtures/`
endpoint (`team_h`/`team_a`, official `team_h_difficulty`/
`team_a_difficulty` 1-5 ratings, and the real `event` Gameweek number)
and resolves each team's true next opponent, home/away status, and
difficulty. Every output row is labeled `fixture_source`:
`"real_fixture"` or `"proxy_last_played"` — nothing is silently
upgraded to look more certain than it is. When a team's fixture can't
be resolved (API unreachable, or that team has no upcoming fixture in
the fetched window), the original proxy behavior — including the
season-rollover warning — is preserved exactly, not hidden.

## Phase 4 — Prediction API

The existing response schemas already return `dict[str, Any]` rows by
design (a deliberate Sprint 8 choice for schema-drift tolerance), so
every new column (`opponent_team`, `fixture_difficulty`,
`fixture_source`, `photo_url`, `team_logo_url`, `opponent_logo_url`,
`model_test_rmse`, `prediction_uncertainty_std`) flows through
automatically — **no breaking schema change**. `HealthResponse` gained
one new optional field, `live_metadata_available`.

**Confidence/uncertainty — what I did NOT do**: I did not invent a
"confidence" percentage. A single stored test-set RMSE is the same
number for every prediction from a given model — using it to
differentiate "confidence" between two different players would itself
be a form of fabrication (implying a distinction that isn't there).
Instead:
- `model_test_rmse`: the model's real held-out chronological test RMSE
  — model-level context, not player-specific.
- `prediction_uncertainty_std`: added **only** for models exposing a
  scikit-learn-style `estimators_` tree ensemble (e.g.
  `RandomForestRegressor`) — the standard deviation of that specific
  row's prediction *across the ensemble's individual trees*, a
  genuine, well-established per-prediction uncertainty proxy. For
  Linear Regression (and any model without this structure), the column
  is simply **omitted** — verified by test
  (`test_predict_omits_uncertainty_for_non_ensemble_model`).

## Phase 5 — Player and team metadata

New `src/metadata/` package (`team_metadata.py`, `player_metadata.py`),
deliberately outside `src/feature_engineering` and
`src/data_collection` — nothing in it is ever merged into the ML
dataset. Badge/photo URLs are constructed from real bootstrap-static
fields (a team's `code`, a player's `photo` filename) using the FPL
site's publicly known asset URL conventions.

**Verification status, stated plainly**: I could not verify these URL
patterns against a live response in this sandbox (no internet access —
same limitation as the rest of this project's FPL API integration).
They're built from general knowledge of the FPL site's asset
conventions, not fabricated per-player/team — but "not fabricated"
isn't the same as "confirmed correct." **Please verify one real badge
and one real photo URL load correctly before relying on this in
production.** If the pattern has drifted, only `src/metadata/` needs
updating — nothing else depends on the exact URL shape.

Missing source fields (no `code`, no `photo`) always produce `None`,
never a guessed URL — verified by test.

## Phase 6 — Frontend

**No rebuild.** `PlayerRecord`, `HealthResponse` gained additive
optional fields. `PlayerAvatar`/`TeamBadge` now accept optional
`photoUrl`/`logoUrl` props — when present, they render a real `<img>`
(falling back to the existing initials/color mark on load failure or
absence); when absent, behavior is byte-for-byte what it was before
this change. `PlayerCard` gained one new conditionally-rendered badge
(`FDR {n}`) for `fixture_difficulty`, shown only when the backend
provides it.

## Phase 7 — Fantasy squad experience

New `Squad` page + `useSquad` hook: browse real predictions, add up to
15 players to a client-side squad, see live total price / total
expected points, an auto-suggested strongest XI (top 11 by predicted
points), and a captain pick (highest predicted scorer in your squad).
No new backend endpoint was invented for this — squad state is
session-local, built entirely from the existing `/predict` data every
other page already uses.

## What was NOT fully verified

- No real training run happened — all metrics in this document's
  example runs are from small mocked/synthetic datasets, explicitly
  not comparable to a real baseline.
- The `/fixtures/` endpoint and the metadata URL patterns were never
  hit against the live FPL API.
- `test_api_routes.py` (Sprint 8) still cannot run in this sandbox —
  `fastapi`/`httpx` are not installable here. Unrelated to this
  roadmap's changes, but still an open item.

## Test suite status

226 tests pass (up from 189 before this roadmap), 0 failures, in this
environment's available dependencies. Full breakdown of new test files
in the diff: `test_team_mapping_service.py`,
`test_normalize_opponent_id.py`, `test_team_form_trend.py`,
`test_fixture_aware_next_gameweek.py`, `test_metadata.py`,
`test_api_state.py`, plus one new regression test appended to
`test_automation_orchestrator.py`.
