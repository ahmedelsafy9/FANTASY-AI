"""Presentation-only metadata layer (Phase 5): player photos, team badges.

Deliberately kept separate from `src.feature_engineering` and
`src.data_collection` — this package produces data for DISPLAY only
(the frontend), never for model features. Nothing here is ever merged
into the engineered training dataset.

**Verification status**: the URL patterns in this package are built
from real bootstrap-static fields (a team's ``code``, a player's
``photo`` filename) using the Fantasy Premier League site's publicly
known asset URL conventions. They were written from general knowledge,
not verified against a live response in this environment (no internet
access here — see the same caveat already documented for
`FPLApiDataSource`). Confirm against a real `bootstrap-static/`
response before relying on these in production; if a pattern has
changed, only this one module needs updating.
"""
