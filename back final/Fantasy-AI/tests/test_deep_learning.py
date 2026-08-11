"""Tests for the Deep Learning tabular regression model.

Covers model construction, forward pass, weighted loss, training,
reproducibility, persistence, factory integration, trainer integration,
and graceful handling of missing PyTorch dependency.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from src.config.settings import TrainingSettings
from src.training.dataset import prepare_split_dataset
from src.training.factory import build_default_model_specs
from src.training.models import ModelSpec
from src.training.persistence import save_best_model
from src.training.trainer import ModelTrainer

# Conditionally import PyTorch — tests that require it are skipped if absent.
torch_available = True
try:
    import torch
except ImportError:
    torch_available = False

requires_torch = pytest.mark.skipif(
    not torch_available,
    reason="PyTorch is not installed.",
)


def _synthetic_dataset(
    n_rows: int = 200,
    n_features: int = 10,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Create a small synthetic regression dataset with sample weights."""
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n_rows, n_features)).astype(np.float32)
    # Target: linear combination + noise
    true_weights = rng.standard_normal(n_features).astype(np.float32)
    y = (X @ true_weights + rng.normal(0, 0.5, n_rows)).astype(np.float32)
    sample_weights = rng.uniform(1.0, 3.0, n_rows).astype(np.float32)
    return X, y, sample_weights


def _build_fpl_dataset(n_players: int = 3, n_gws: int = 20) -> pd.DataFrame:
    """A synthetic FPL dataset matching the training pipeline's expectations."""
    rng = np.random.default_rng(42)
    rows = []
    for player in range(n_players):
        for gw in range(1, n_gws + 1):
            minutes = 90.0
            noise = rng.normal(0, 0.1)
            rows.append(
                {
                    "season": "2022-23",
                    "GW": gw,
                    "element": player,
                    "minutes": minutes,
                    "bonus": float(gw % 3),
                    "total_points": 0.1 * minutes + 2 * (gw % 3) + noise,
                }
            )
    return pd.DataFrame(rows)


def _test_settings() -> TrainingSettings:
    return TrainingSettings(
        target_column="total_points",
        excluded_feature_columns=("element",),
        chronological_columns=("season", "GW"),
        test_fraction=0.2,
        random_state=42,
        dl_hidden_layers=(32, 16),
        dl_dropout=0.1,
        dl_learning_rate=1e-3,
        dl_weight_decay=1e-4,
        dl_batch_size=32,
        dl_epochs=30,
        dl_patience=10,
        dl_use_batch_norm=True,
    )


# -----------------------------------------------------------------------
# Model construction and forward pass
# -----------------------------------------------------------------------


@requires_torch
class TestModelConstruction:
    """Tests for MLP construction and basic forward pass."""

    def test_build_mlp_produces_correct_output_shape(self) -> None:
        from src.training.deep_learning import _build_mlp

        model = _build_mlp(
            input_dim=10,
            hidden_layers=(32, 16),
            dropout=0.2,
            use_batch_norm=True,
        )
        X = torch.randn(5, 10)
        out = model(X)
        assert out.shape == (5, 1)

    def test_build_mlp_without_batch_norm(self) -> None:
        from src.training.deep_learning import _build_mlp

        model = _build_mlp(
            input_dim=8,
            hidden_layers=(16,),
            dropout=0.0,
            use_batch_norm=False,
        )
        X = torch.randn(3, 8)
        out = model(X)
        assert out.shape == (3, 1)

    def test_parameter_count_is_positive(self) -> None:
        from src.training.deep_learning import _build_mlp

        model = _build_mlp(
            input_dim=10,
            hidden_layers=(32, 16),
            dropout=0.2,
            use_batch_norm=True,
        )
        param_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
        assert param_count > 0

    def test_input_output_dimensions_match_config(self) -> None:
        from src.training.deep_learning import DeepLearningConfig, TabularMLPRegressor

        config = DeepLearningConfig(
            hidden_layers=(64, 32),
            epochs=2,
            batch_size=16,
        )
        model = TabularMLPRegressor(config=config)
        X, y, _ = _synthetic_dataset(n_rows=50, n_features=15)
        model.fit(X, y)
        preds = model.predict(X)
        assert preds.shape == (50,)


# -----------------------------------------------------------------------
# Weighted loss
# -----------------------------------------------------------------------


@requires_torch
class TestWeightedLoss:
    """Tests that the weighted loss is mathematically correct."""

    def test_weighted_loss_differs_from_uniform(self) -> None:
        """Training with non-uniform weights should produce different
        results than training with uniform weights."""
        from src.training.deep_learning import DeepLearningConfig, TabularMLPRegressor

        X, y, weights = _synthetic_dataset(n_rows=100, n_features=5)

        config = DeepLearningConfig(
            hidden_layers=(16,),
            epochs=20,
            batch_size=32,
            random_state=42,
        )

        model_weighted = TabularMLPRegressor(config=config)
        model_weighted.fit(X, y, sample_weight=weights)
        preds_weighted = model_weighted.predict(X)

        model_uniform = TabularMLPRegressor(config=config)
        model_uniform.fit(X, y, sample_weight=None)
        preds_uniform = model_uniform.predict(X)

        # Predictions should not be identical
        assert not np.allclose(preds_weighted, preds_uniform, atol=1e-3)

    def test_fit_accepts_sample_weight_kwarg(self) -> None:
        """The fit method must accept sample_weight as a keyword argument
        matching the scikit-learn convention used by the trainer."""
        from src.training.deep_learning import DeepLearningConfig, TabularMLPRegressor

        X, y, weights = _synthetic_dataset(n_rows=50, n_features=5)
        config = DeepLearningConfig(hidden_layers=(8,), epochs=3, batch_size=16)
        model = TabularMLPRegressor(config=config)
        # Must not raise
        model.fit(X, y, sample_weight=weights)


# -----------------------------------------------------------------------
# Training on synthetic data
# -----------------------------------------------------------------------


@requires_torch
class TestTraining:
    """Tests that the model learns from data."""

    def test_training_reduces_loss(self) -> None:
        from src.training.deep_learning import DeepLearningConfig, TabularMLPRegressor

        X, y, _ = _synthetic_dataset(n_rows=200, n_features=5)
        config = DeepLearningConfig(
            hidden_layers=(32, 16),
            epochs=50,
            batch_size=32,
            patience=50,
        )
        model = TabularMLPRegressor(config=config)
        model.fit(X, y)
        preds = model.predict(X)

        # MAE should be significantly better than predicting the mean
        mae = float(np.mean(np.abs(y - preds)))
        mean_pred_mae = float(np.mean(np.abs(y - np.mean(y))))
        assert mae < mean_pred_mae

    def test_predict_before_fit_raises(self) -> None:
        from src.training.deep_learning import TabularMLPRegressor

        model = TabularMLPRegressor()
        with pytest.raises(RuntimeError, match="not been fitted"):
            model.predict(np.zeros((5, 10)))

    def test_near_zero_variance_precision_does_not_explode_predictions(self) -> None:
        """Features with constant training values (producing ~1e-8 std due to float precision)
        must not explode test predictions when test features contain non-constant values."""
        from src.training.deep_learning import DeepLearningConfig, TabularMLPRegressor

        # 200 rows with constant value 0.1 (which yields ~1.49e-8 std in float32 over 200k rows)
        X_train = np.full((200, 5), fill_value=0.1, dtype=np.float32)
        y_train = np.ones(200, dtype=np.float32)

        config = DeepLearningConfig(hidden_layers=(16,), epochs=2, batch_size=32)
        model = TabularMLPRegressor(config=config)
        model.fit(X_train, y_train)

        # Test set contains non-constant values (e.g., 29.0)
        X_test = np.full((10, 5), fill_value=29.0, dtype=np.float32)
        preds = model.predict(X_test)

        # Predictions must be reasonable numbers (not millions/billions)
        assert np.all(np.isfinite(preds))
        assert np.max(np.abs(preds)) < 1000.0

    def test_configurable_loss_beta_and_magnitude_weighting(self) -> None:
        """Configurable loss_beta and high_score_weight_power build and train correctly."""
        from src.training.deep_learning import DeepLearningConfig, TabularMLPRegressor

        X = np.random.randn(100, 4).astype(np.float32)
        y = np.array([0, 2, 6, 10, 12] * 20, dtype=np.float32)

        config = DeepLearningConfig(
            hidden_layers=(16,),
            epochs=2,
            batch_size=32,
            loss_beta=4.0,
            high_score_weight_power=0.5,
        )
        model = TabularMLPRegressor(config=config)
        model.fit(X, y)
        preds = model.predict(X)

        assert len(preds) == 100
        assert np.all(np.isfinite(preds))


# -----------------------------------------------------------------------
# Reproducibility
# -----------------------------------------------------------------------


@requires_torch
class TestReproducibility:
    """Tests that training is reproducible with the same seed."""

    def test_same_seed_produces_same_predictions(self) -> None:
        from src.training.deep_learning import DeepLearningConfig, TabularMLPRegressor

        X, y, w = _synthetic_dataset(n_rows=80, n_features=5)
        config = DeepLearningConfig(
            hidden_layers=(16,),
            epochs=10,
            batch_size=32,
            random_state=99,
        )

        model_a = TabularMLPRegressor(config=config)
        model_a.fit(X, y, sample_weight=w)
        preds_a = model_a.predict(X)

        model_b = TabularMLPRegressor(config=config)
        model_b.fit(X, y, sample_weight=w)
        preds_b = model_b.predict(X)

        np.testing.assert_allclose(preds_a, preds_b, atol=1e-5)


# -----------------------------------------------------------------------
# Persistence (pickle/joblib)
# -----------------------------------------------------------------------


@requires_torch
class TestPersistence:
    """Tests that the model can be saved and loaded via joblib."""

    def test_joblib_round_trip(self, tmp_path: Path) -> None:
        import joblib

        from src.training.deep_learning import DeepLearningConfig, TabularMLPRegressor

        X, y, _ = _synthetic_dataset(n_rows=50, n_features=5)
        config = DeepLearningConfig(hidden_layers=(16,), epochs=5, batch_size=16)
        model = TabularMLPRegressor(config=config)
        model.fit(X, y)
        preds_before = model.predict(X)

        path = tmp_path / "model.joblib"
        joblib.dump(model, path)
        loaded_model = joblib.load(path)
        preds_after = loaded_model.predict(X)

        np.testing.assert_allclose(preds_before, preds_after, atol=1e-6)

    def test_persistence_through_training_pipeline(self, tmp_path: Path) -> None:
        """The full save_best_model flow should work with a DL model."""
        settings = _test_settings()
        df = _build_fpl_dataset()
        split = prepare_split_dataset(df, settings)

        from src.training.deep_learning import DeepLearningConfig, TabularMLPRegressor

        config = DeepLearningConfig(
            hidden_layers=(16,),
            epochs=5,
            batch_size=16,
            random_state=42,
        )
        specs = [
            ModelSpec(
                name="deep_learning",
                build=lambda: TabularMLPRegressor(config=config),
            ),
        ]
        trainer = ModelTrainer(model_specs=specs, settings=settings)
        result = trainer.run(split, skipped_models={})

        model_path = tmp_path / "model.joblib"
        metadata_path = tmp_path / "metadata.json"
        save_best_model(result, split, model_path, metadata_path)

        assert model_path.exists()
        assert metadata_path.exists()

        import joblib

        loaded = joblib.load(model_path)
        preds = loaded.predict(split.X_test)
        assert len(preds) == len(split.X_test)

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["model_name"] == "deep_learning"


# -----------------------------------------------------------------------
# Factory integration
# -----------------------------------------------------------------------


@requires_torch
class TestFactoryIntegration:
    """Tests that the factory includes the Deep Learning model."""

    def test_factory_includes_deep_learning_when_torch_available(self) -> None:
        settings = _test_settings()
        specs, skipped = build_default_model_specs(settings)
        names = {spec.name for spec in specs}
        assert "deep_learning_weighted_huber" in names
        assert "deep_learning_weighted_huber" not in skipped

    def test_factory_skips_deep_learning_when_torch_missing(self) -> None:
        """When torch cannot be imported, the factory should skip gracefully."""
        settings = _test_settings()
        with patch.dict("sys.modules", {"torch": None}):
            specs, skipped = build_default_model_specs(settings)
        names = {spec.name for spec in specs}
        assert "deep_learning_weighted_huber" not in names
        assert "deep_learning_weighted_huber" in skipped


# -----------------------------------------------------------------------
# Trainer integration
# -----------------------------------------------------------------------


@requires_torch
class TestTrainerIntegration:
    """Tests that the model works end-to-end within the trainer."""

    def test_trainer_trains_deep_learning_alongside_linear(self) -> None:
        settings = _test_settings()
        df = _build_fpl_dataset()
        split = prepare_split_dataset(df, settings)

        from src.training.deep_learning import DeepLearningConfig, TabularMLPRegressor

        config = DeepLearningConfig(
            hidden_layers=(16,),
            epochs=5,
            batch_size=16,
            random_state=42,
        )

        specs = [
            ModelSpec(name="linear_regression", build=lambda: LinearRegression()),
            ModelSpec(
                name="deep_learning",
                build=lambda: TabularMLPRegressor(config=config),
            ),
        ]

        trainer = ModelTrainer(model_specs=specs, settings=settings)
        result = trainer.run(split, skipped_models={})

        trained_names = {r.name for r in result.results}
        assert "linear_regression" in trained_names
        assert "deep_learning" in trained_names
        assert len(result.results) == 2

        # Both should have valid metrics
        for r in result.results:
            assert r.metrics.mae > 0
            assert r.metrics.rmse > 0
            assert r.train_seconds >= 0

    def test_deep_learning_uses_sample_weights_in_trainer(self) -> None:
        """Verify the trainer passes sample_weight to the DL model."""
        settings = _test_settings()
        df = _build_fpl_dataset()
        split = prepare_split_dataset(df, settings)

        from src.training.deep_learning import DeepLearningConfig, TabularMLPRegressor

        config = DeepLearningConfig(
            hidden_layers=(8,),
            epochs=3,
            batch_size=16,
            random_state=42,
        )

        specs = [
            ModelSpec(
                name="deep_learning",
                build=lambda: TabularMLPRegressor(config=config),
            ),
        ]

        trainer = ModelTrainer(model_specs=specs, settings=settings)
        # Should not raise — sample_weight is passed correctly
        result = trainer.run(split, skipped_models={})
        assert len(result.results) == 1
        assert result.results[0].metrics.mae > 0
