"""Feedback learning / adaptive prediction system.

Learns systematic prediction errors from previous Gameweeks and applies
residual corrections to improve future predictions. Architecture:

    Base DL Model → Base Prediction → Feedback Adapter → Final Prediction

The feedback system consists of:

- **SnapshotStore**: saves immutable pre-match prediction snapshots
- **FeedbackStore**: joins predictions with actual results to create feedback
- **FeedbackAnalyzer**: computes error metrics and discovers systematic biases
- **ResidualModel**: learns to predict the residual (actual - predicted)
- **FeedbackAdapter**: orchestrates correction application
- **evaluation**: walk-forward temporal evaluation framework
"""
