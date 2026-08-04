"""Fantasy-AI source package.

Fantasy-AI is a production-grade machine learning system that predicts
Fantasy Premier League (FPL) player points for future Gameweeks.

The codebase follows Clean Architecture principles, separating concerns
into distinct layers:

- ``data_collection``: acquisition of raw data from external sources.
- ``preprocessing``: cleaning and normalization of raw data.
- ``feature_engineering``: derivation of model-ready features.
- ``training``: model training and selection.
- ``prediction``: inference using trained models.
- ``evaluation``: model and prediction quality assessment.
- ``api``: HTTP interface exposing the system's capabilities.
- ``core`` / ``config`` / ``common``: cross-cutting concerns shared by
  every layer (settings, logging, shared utilities, exceptions).
"""
