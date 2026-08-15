"""Unit tests for ranking and recall metrics."""

from __future__ import annotations

import numpy as np
import pytest

from src.training.ranking_metrics import high_score_recall, top_n_recall


def test_top_n_recall_perfect_match() -> None:
    y_true = np.array([1, 2, 3, 10, 20, 30])
    y_pred = np.array([0.1, 0.2, 0.3, 1.0, 2.0, 3.0])

    recall = top_n_recall(y_true, y_pred, n=3)
    assert recall == 1.0


def test_top_n_recall_partial_match() -> None:
    y_true = np.array([1, 2, 3, 10, 20, 30])
    y_pred = np.array([30, 20, 10, 3, 2, 1])

    recall = top_n_recall(y_true, y_pred, n=3)
    assert recall == 0.0


def test_top_n_recall_small_sample() -> None:
    y_true = np.array([1, 2])
    y_pred = np.array([1, 2])

    recall = top_n_recall(y_true, y_pred, n=5)
    assert np.isnan(recall)


def test_high_score_recall_perfect() -> None:
    y_true = np.array([1.0, 2.0, 7.0, 10.0, 12.0])
    y_pred = np.array([0.5, 1.5, 6.5, 8.0, 11.0])

    recall = high_score_recall(y_true, y_pred, threshold=6.0, pred_threshold=6.0)
    assert recall == 1.0


def test_high_score_recall_under_prediction() -> None:
    y_true = np.array([1.0, 2.0, 7.0, 10.0, 12.0])
    y_pred = np.array([0.5, 1.5, 4.0, 5.0, 11.0])

    recall = high_score_recall(y_true, y_pred, threshold=6.0, pred_threshold=6.0)
    assert pytest.approx(recall) == 1.0 / 3.0


def test_high_score_recall_no_positives() -> None:
    y_true = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([1.0, 2.0, 3.0])

    recall = high_score_recall(y_true, y_pred, threshold=6.0, pred_threshold=6.0)
    assert np.isnan(recall)
