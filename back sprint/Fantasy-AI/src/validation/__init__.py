"""Validation layer: dataset quality checks and report generation.

This layer sits between data collection and preprocessing. It never
mutates data — it only inspects it and reports on structural and
quality issues (missing values, duplicates, invalid types, invalid
Gameweek numbers, invalid player identifiers). Cleaning/fixing those
issues is the responsibility of the preprocessing layer (Sprint 4).
"""
