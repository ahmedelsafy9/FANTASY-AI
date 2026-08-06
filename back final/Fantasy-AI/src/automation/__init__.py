"""Automation layer: dataset updates, incremental ingestion, retraining,
and version management for models and data.

Orchestrates the pipelines built in prior sprints (data collection,
preprocessing, feature engineering, training) rather than duplicating
their logic, and adds what's new for Sprint 9: pulling in the latest
Gameweek via the live FPL API, versioning both datasets and models so
past states are never silently overwritten, and optional automatic
retraining with a promote-only-if-better policy.
"""
