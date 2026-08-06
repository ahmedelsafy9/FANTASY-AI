"""Feature engineering layer: derives model-ready features from cleaned data.

Consumes the cleaned dataset produced by the preprocessing layer
(Sprint 4) and produces an engineered dataset with rolling-window
statistics, contextual flags, and derived indices — ready for model
training (Sprint 6). Like preprocessing, this layer mutates data (by
adding new columns); unlike preprocessing, it never removes rows.
"""
