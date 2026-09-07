"""Multi-stage prediction pipeline for Fantasy-AI.

Implements a three-stage prediction architecture:
1. Match Result Model — predicts team-level match outcomes
2. Player Contribution Model — predicts individual player contributions
3. Points Model — predicts FPL points using base features + upstream predictions

All stages use GW-level expanding walk-forward cross-validation to prevent
target leakage. Downstream models only ever see upstream predictions that
were generated without knowledge of the target period.
"""
