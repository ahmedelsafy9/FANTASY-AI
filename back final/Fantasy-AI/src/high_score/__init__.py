"""High-Score Discrimination, Ranking, and Training-Window Optimization module (Feedback 5).

Provides:
- Training window filtering and recency weighting
- Dedicated high-score classification models (>=6, >=8, >=10, >=12)
- Upper-tail quantile regression for ceiling estimation
- Gameweek-level pairwise/listwise ranking models
- Hurdle two-stage participation and scoring models
- Leakage-safe learned multi-objective hybrid scoring
- Distribution, ranking, and position-aware diagnostics
"""

from __future__ import annotations
