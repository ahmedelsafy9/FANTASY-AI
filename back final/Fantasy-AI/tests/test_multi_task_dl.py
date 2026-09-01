"""Unit tests for the Multi-Task Deep Learning model."""

from __future__ import annotations

import pickle

import numpy as np
import pandas as pd
import pytest

from src.training.multi_task_dl import MultiTaskDLConfig, MultiTaskTabularNN, TabularMultiTaskRegressor


def test_multi_task_nn_forward_pass():
    """Test MultiTaskTabularNN forward pass and output head shapes."""
    import torch

    batch_size = 8
    input_dim = 20
    model = MultiTaskTabularNN.create(input_dim=input_dim, hidden_layers=(64, 32), head_hidden_dim=16)

    x = torch.randn(batch_size, input_dim)
    out = model(x)

    assert "minutes_logits" in out
    assert out["minutes_logits"].shape == (batch_size, 2)

    assert "goals_raw" in out
    assert out["goals_raw"].shape == (batch_size,)

    assert "assists_raw" in out
    assert out["assists_raw"].shape == (batch_size,)

    assert "cs_logits" in out
    assert out["cs_logits"].shape == (batch_size,)

    assert "gc_raw" in out
    assert out["gc_raw"].shape == (batch_size,)

    assert "saves_raw" in out
    assert out["saves_raw"].shape == (batch_size,)

    assert "cards_logits" in out
    assert out["cards_logits"].shape == (batch_size, 2)

    assert "bonus_raw" in out
    assert out["bonus_raw"].shape == (batch_size,)


def test_tabular_multi_task_regressor_fit_and_predict():
    """Test end-to-end fit, predict_events, predict_breakdown, and predict."""
    np.random.seed(42)
    n_samples = 100
    n_features = 10

    X = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=[f"feat_{i}" for i in range(n_features)],
    )
    # Add position one-hot columns
    X["is_position_gkp"] = 0.0
    X["is_position_def"] = 0.0
    X["is_position_mid"] = 1.0
    X["is_position_fwd"] = 0.0

    y = pd.Series(np.random.choice([0.0, 1.0, 2.0, 5.0, 8.0, 12.0], size=n_samples))

    Y_events = pd.DataFrame(
        {
            "minutes": np.random.choice([0, 30, 90], size=n_samples),
            "goals_scored": np.random.choice([0, 1, 2], p=[0.85, 0.12, 0.03], size=n_samples),
            "assists": np.random.choice([0, 1, 2], p=[0.88, 0.10, 0.02], size=n_samples),
            "clean_sheets": np.random.choice([0, 1], p=[0.75, 0.25], size=n_samples),
            "goals_conceded": np.random.choice([0, 1, 2, 3], size=n_samples),
            "saves": np.zeros(n_samples),
            "yellow_cards": np.random.choice([0, 1], p=[0.9, 0.1], size=n_samples),
            "red_cards": np.zeros(n_samples),
            "bonus": np.random.choice([0, 1, 2, 3], p=[0.85, 0.05, 0.05, 0.05], size=n_samples),
        }
    )

    cfg = MultiTaskDLConfig(
        hidden_layers=(32, 16),
        head_hidden_dim=8,
        epochs=3,
        batch_size=32,
    )
    model = TabularMultiTaskRegressor(config=cfg)
    model.fit(X, y, Y_events=Y_events)

    # Predict total points
    preds = model.predict(X)
    assert isinstance(preds, np.ndarray)
    assert preds.shape == (n_samples,)
    assert not np.isnan(preds).any()

    # Predict events
    events = model.predict_events(X)
    assert "p_play_any" in events
    assert "expected_goals" in events
    assert (events["expected_goals"] >= 0.0).all()
    assert (events["clean_sheet_prob"] >= 0.0).all()
    assert (events["clean_sheet_prob"] <= 1.0).all()

    # Predict breakdown
    breakdown = model.predict_breakdown(X)
    assert isinstance(breakdown, pd.DataFrame)
    assert "predicted_appearance_points" in breakdown.columns
    assert "predicted_goal_points" in breakdown.columns
    assert "predicted_total_points" in breakdown.columns
    np.testing.assert_allclose(breakdown["predicted_total_points"].to_numpy(), preds)


def test_tabular_multi_task_regressor_pickling():
    """Test serialization and deserialization via pickle/joblib."""
    np.random.seed(42)
    X = np.random.randn(20, 5)
    y = np.random.randn(20)

    cfg = MultiTaskDLConfig(hidden_layers=(16,), head_hidden_dim=8, epochs=1)
    model = TabularMultiTaskRegressor(config=cfg)
    model.fit(X, y)

    orig_preds = model.predict(X)

    pickled = pickle.dumps(model)
    restored = pickle.loads(pickled)

    restored_preds = restored.predict(X)
    np.testing.assert_allclose(orig_preds, restored_preds, atol=1e-5)
