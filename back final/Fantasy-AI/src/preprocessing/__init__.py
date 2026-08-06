"""Preprocessing layer: cleans, normalizes, and type-converts raw datasets.

This layer consumes the merged raw dataset produced by the data
collection layer (Sprint 2) and, informed by the issues surfaced by
the validation layer (Sprint 3), produces a clean dataset ready for
feature engineering (Sprint 5). Unlike the validation layer, this
layer *mutates* data.
"""
