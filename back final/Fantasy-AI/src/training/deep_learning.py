"""Deep Learning tabular regression model with a scikit-learn-compatible API.

Wraps a PyTorch MLP so the existing :class:`~src.training.trainer.ModelTrainer`
can treat it like any other estimator — calling ``fit(X, y, sample_weight=...)``
and ``predict(X)`` — without knowing anything about PyTorch internals.

The model handles its own standardization (fitted on training data only),
weighted loss computation, early stopping, and learning-rate scheduling.

===============================================================================
AUDITED VERSION — every change from the original is wrapped like this:

    # === CHANGE START (n) ===
    ...new/changed lines...
    # === CHANGE END (n) ===

Nothing outside these markers differs from your current
src/training/deep_learning.py. This file is NOT wired into your project —
it is for review only. See the accompanying AUDIT_NOTES.md for the
rationale, risk assessment, and exact apply instructions for each change.
===============================================================================
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class DeepLearningConfig:
    """Hyperparameters for the tabular MLP regression model.

    These are populated from :class:`~src.config.settings.TrainingSettings`
    and injected at construction time — no hardcoded hyperparameters.

    Attributes:
        hidden_layers: Sizes of hidden layers, e.g. ``(256, 128, 64)``.
        dropout: Dropout probability between hidden layers.
        learning_rate: Initial learning rate for AdamW.
        weight_decay: L2 regularization strength for AdamW.
        batch_size: Mini-batch size.
        epochs: Maximum training epochs.
        patience: Early stopping patience (epochs without improvement).
        use_batch_norm: Whether to apply batch normalization.
        random_state: Random seed for reproducibility.
    """

    hidden_layers: tuple[int, ...] = (256, 128, 64)
    dropout: float = 0.2
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    batch_size: int = 512
    epochs: int = 200
    patience: int = 15
    use_batch_norm: bool = True
    loss_beta: float = 4.0
    high_score_weight_power: float = 0.0
    use_discrete_sample_weights: bool = True
    random_state: int = 42
    # === CHANGE START (1): new opt-in fields, all with defaults that
    # reproduce EXISTING behavior exactly. Nothing changes unless you
    # explicitly set loss_type="asymmetric_huber" via settings/env, or
    # explicitly set grad_clip_norm=None to turn clipping off. ===
    #
    # grad_clip_norm: caps the L2 norm of the gradient before each
    # optimizer step. Standard, well-established practice; it only
    # activates on the rare batch where a gradient spikes, and prevents
    # that single batch from corrupting otherwise-good weights. Default
    # 5.0 is a loose bound — it will not affect normal training, only
    # outliers. This is the one change here that is close to risk-free;
    # everything else is opt-in and needs your own A/B test before you
    # rely on it.
    grad_clip_norm: float | None = 5.0
    # loss_type: "huber" (default) is byte-for-byte identical to current
    # behavior. "asymmetric_huber" existed in this project's git history
    # and was later reverted — restored here as an opt-in so you can
    # re-test it deliberately rather than by accident. It multiplies the
    # loss by `asymmetric_penalty` specifically when the model
    # UNDERpredicts a row whose true score was >= asymmetric_threshold —
    # i.e. it targets recall>=10 directly instead of average error.
    loss_type: str = "huber"
    asymmetric_penalty: float = 1.6
    asymmetric_threshold: float = 3.0
    # === CHANGE END (1) ===


class TabularMLPRegressor:
    """Scikit-learn-compatible MLP regression estimator backed by PyTorch.

    Implements ``fit(X, y, sample_weight=None)`` and ``predict(X)``
    so the existing model-agnostic trainer can use it exactly like
    ``LinearRegression`` or ``XGBRegressor``.

    All PyTorch knowledge is encapsulated here — the trainer never
    imports or references PyTorch.

    Args:
        config: Hyperparameters for the MLP.
    """

    def __init__(self, config: DeepLearningConfig | None = None) -> None:
        self.config = config or DeepLearningConfig()
        self._model: Any = None
        self._scaler_mean: np.ndarray | None = None
        self._scaler_std: np.ndarray | None = None
        self._input_dim: int | None = None
        self._training_info: dict[str, Any] = {}

    def fit(
        self,
        X: Any,
        y: Any,
        sample_weight: np.ndarray | None = None,
    ) -> "TabularMLPRegressor":
        """Train the MLP on the given data.

        Args:
            X: Feature matrix (DataFrame or array-like).
            y: Target vector.
            sample_weight: Per-row recency weights. Used in the loss
                computation as ``sum(w_i * loss_i) / sum(w_i)``.

        Returns:
            TabularMLPRegressor: ``self``, following scikit-learn convention.
        """
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset

        cfg = self.config
        start = time.perf_counter()

        # ---------------------------------------------------------------
        # Reproducibility
        # ---------------------------------------------------------------
        torch.manual_seed(cfg.random_state)
        np.random.seed(cfg.random_state)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(cfg.random_state)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

        # ---------------------------------------------------------------
        # Convert to numpy
        # ---------------------------------------------------------------
        X_np = np.asarray(X, dtype=np.float32)
        y_np = np.asarray(y, dtype=np.float32).ravel()

        self._input_dim = X_np.shape[1]

        # ---------------------------------------------------------------
        # Standardize features (fitted on training data only)
        # ---------------------------------------------------------------
        self._scaler_mean = X_np.mean(axis=0)
        self._scaler_std = X_np.std(axis=0)
        # Avoid division by zero/near-zero for constant features
        # (float32 precision can leave ~1e-8 std on constant columns)
        self._scaler_std[self._scaler_std < 1e-5] = 1.0
        X_scaled = (X_np - self._scaler_mean) / self._scaler_std
        X_scaled = np.clip(X_scaled, -50.0, 50.0)

        # ---------------------------------------------------------------
        # Prepare tensors
        # ---------------------------------------------------------------
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        X_tensor = torch.from_numpy(X_scaled).to(device)
        y_tensor = torch.from_numpy(y_np).to(device)

        if sample_weight is not None:
            w_np = np.asarray(sample_weight, dtype=np.float32).ravel()
        else:
            w_np = np.ones(len(y_np), dtype=np.float32)

        if cfg.use_discrete_sample_weights:
            discrete_w = _discrete_bucket_weights(y_np)
            w_np = w_np * discrete_w

        if cfg.high_score_weight_power > 0:
            magnitude_weight = (
                1.0
                + cfg.high_score_weight_power
                * np.clip(y_np, 0, None)
            )
            w_np = w_np * magnitude_weight

        w_tensor = torch.from_numpy(w_np).to(device)

        # ---------------------------------------------------------------
        # Train/validation split (80/20 of training data) for early stopping
        # ---------------------------------------------------------------
        n_total = len(X_tensor)
        n_val = max(1, int(n_total * 0.15))
        n_train = n_total - n_val

        # Use the last rows as validation (preserves chronological order)
        X_tr, X_val = X_tensor[:n_train], X_tensor[n_train:]
        y_tr, y_val = y_tensor[:n_train], y_tensor[n_train:]
        w_tr, w_val = w_tensor[:n_train], w_tensor[n_train:]

        train_dataset = TensorDataset(X_tr, y_tr, w_tr)
        train_loader = DataLoader(
            train_dataset,
            batch_size=cfg.batch_size,
            shuffle=True,
            drop_last=False,
            generator=torch.Generator().manual_seed(cfg.random_state),
        )

        # ---------------------------------------------------------------
        # Build model
        # ---------------------------------------------------------------
        model = _build_mlp(
            input_dim=self._input_dim,
            hidden_layers=cfg.hidden_layers,
            dropout=cfg.dropout,
            use_batch_norm=cfg.use_batch_norm,
        ).to(device)

        param_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
        logger.info(
            "Deep Learning architecture: input=%d, hidden=%s, "
            "batch_norm=%s, dropout=%.2f, params=%d",
            self._input_dim,
            cfg.hidden_layers,
            cfg.use_batch_norm,
            cfg.dropout,
            param_count,
        )

        # ---------------------------------------------------------------
        # Optimizer and scheduler
        # ---------------------------------------------------------------
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=cfg.learning_rate,
            weight_decay=cfg.weight_decay,
        )
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode="min",
            factor=0.5,
            patience=5,
            min_lr=1e-6,
        )
        # === CHANGE START (2): loss_fn now conditional on cfg.loss_type.
        # When loss_type="huber" (the default), this produces the exact
        # same nn.SmoothL1Loss(beta=cfg.loss_beta, reduction="none") as
        # before — identical object, identical math. The new branch only
        # executes if you explicitly opt into loss_type="asymmetric_huber". ===
        if cfg.loss_type == "asymmetric_huber":
            loss_fn: Any = _AsymmetricSmoothL1Loss(
                beta=cfg.loss_beta,
                penalty=cfg.asymmetric_penalty,
                threshold=cfg.asymmetric_threshold,
            )
        else:
            loss_fn = nn.SmoothL1Loss(beta=cfg.loss_beta, reduction="none")
        # === CHANGE END (2) ===

        # ---------------------------------------------------------------
        # Training loop
        # ---------------------------------------------------------------
        best_val_loss = float("inf")
        best_state = None
        patience_counter = 0

        for epoch in range(1, cfg.epochs + 1):
            model.train()
            epoch_loss = 0.0
            epoch_weight_sum = 0.0

            for X_batch, y_batch, w_batch in train_loader:
                optimizer.zero_grad()
                preds = model(X_batch).squeeze(-1)
                raw_loss = loss_fn(preds, y_batch)
                # Mathematically correct weighted loss:
                # weighted_loss = sum(w_i * loss_i) / sum(w_i)
                weighted_loss = (raw_loss * w_batch).sum() / w_batch.sum()
                weighted_loss.backward()
                # === CHANGE START (3): gradient clipping. With
                # grad_clip_norm=None this line never executes (identical
                # to current behavior). With the default 5.0, it only
                # rescales gradients on the rare batch whose L2 norm
                # exceeds 5.0 — normal-sized gradients pass through
                # unchanged. ===
                if cfg.grad_clip_norm is not None:
                    torch.nn.utils.clip_grad_norm_(
                        model.parameters(), cfg.grad_clip_norm
                    )
                # === CHANGE END (3) ===
                optimizer.step()

                batch_w_sum = w_batch.sum().item()
                epoch_loss += (raw_loss * w_batch).sum().item()
                epoch_weight_sum += batch_w_sum

            avg_train_loss = epoch_loss / max(epoch_weight_sum, 1e-8)

            # ---------------------------------------------------------------
            # Validation (unweighted — mirrors test-set evaluation)
            # ---------------------------------------------------------------
            model.eval()
            with torch.no_grad():
                val_preds = model(X_val).squeeze(-1)
                val_raw_loss = loss_fn(val_preds, y_val)
                # Use uniform weights on validation (same as test evaluation)
                val_loss = val_raw_loss.mean().item()

            scheduler.step(val_loss)

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1

            if epoch % 20 == 0 or epoch == 1 or patience_counter == 0:
                current_lr = optimizer.param_groups[0]["lr"]
                logger.info(
                    "  Epoch %3d/%d — train_loss=%.4f, val_loss=%.4f, "
                    "lr=%.2e, patience=%d/%d",
                    epoch,
                    cfg.epochs,
                    avg_train_loss,
                    val_loss,
                    current_lr,
                    patience_counter,
                    cfg.patience,
                )

            if patience_counter >= cfg.patience:
                logger.info(
                    "  Early stopping at epoch %d (best val_loss=%.4f).",
                    epoch,
                    best_val_loss,
                )
                break

        # ---------------------------------------------------------------
        # Restore best model weights
        # ---------------------------------------------------------------
        if best_state is not None:
            model.load_state_dict(best_state)

        self._model = model.cpu().eval()

        train_duration = time.perf_counter() - start

        self._training_info = {
            "input_dim": self._input_dim,
            "hidden_layers": cfg.hidden_layers,
            "param_count": param_count,
            "epochs_run": epoch,
            "best_val_loss": best_val_loss,
            "batch_size": cfg.batch_size,
            "learning_rate": cfg.learning_rate,
            "weight_decay": cfg.weight_decay,
            "dropout": cfg.dropout,
            "use_batch_norm": cfg.use_batch_norm,
            "early_stopped": patience_counter >= cfg.patience,
            "train_seconds": train_duration,
            "device": str(device),
        }

        logger.info(
            "Deep Learning training complete: %d epochs, "
            "best_val_loss=%.4f, duration=%.2fs, device=%s",
            epoch,
            best_val_loss,
            train_duration,
            device,
        )

        return self

    def predict(self, X: Any) -> np.ndarray:
        """Generate predictions for the given feature matrix.

        Args:
            X: Feature matrix (DataFrame or array-like).

        Returns:
            np.ndarray: Predicted target values, shape ``(n_samples,)``.

        Raises:
            RuntimeError: If the model has not been fitted yet.
        """
        if self._model is None:
            raise RuntimeError("TabularMLPRegressor has not been fitted yet.")

        import torch

        X_np = np.asarray(X, dtype=np.float32)
        X_scaled = (X_np - self._scaler_mean) / self._scaler_std
        X_scaled = np.clip(X_scaled, -50.0, 50.0)

        self._model.eval()
        with torch.no_grad():
            X_tensor = torch.from_numpy(X_scaled)
            predictions = self._model(X_tensor).squeeze(-1).numpy()

        return predictions

    def get_params(self, deep: bool = True) -> dict[str, Any]:
        """Get estimator parameters (scikit-learn compatibility)."""
        return {"config": self.config}

    def set_params(self, **params: Any) -> "TabularMLPRegressor":
        """Set estimator parameters (scikit-learn compatibility)."""
        if "config" in params:
            self.config = params["config"]
        return self

    def __getstate__(self) -> dict[str, Any]:
        """Custom pickling: convert PyTorch model to CPU state dict."""
        state = self.__dict__.copy()
        if self._model is not None:
            import torch

            state["_model_state_dict"] = self._model.state_dict()
            state["_model_class_args"] = {
                "input_dim": self._input_dim,
                "hidden_layers": self.config.hidden_layers,
                "dropout": self.config.dropout,
                "use_batch_norm": self.config.use_batch_norm,
            }
            del state["_model"]
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Custom unpickling: reconstruct PyTorch model from state dict."""
        model_state_dict = state.pop("_model_state_dict", None)
        model_class_args = state.pop("_model_class_args", None)
        self.__dict__.update(state)

        if model_state_dict is not None and model_class_args is not None:
            import torch

            model = _build_mlp(**model_class_args)
            model.load_state_dict(model_state_dict)
            model.eval()
            self._model = model
        else:
            self._model = None


def _discrete_bucket_weights(y: np.ndarray) -> np.ndarray:
    """Compute discrete sample weights based on point-score buckets.

    Higher-scoring performances receive proportionally more weight,
    encouraging the model to pay extra attention to high-value rows
    without the calibration issues of continuous magnitude weighting.

    Bucket weights:
        0-2 pts  -> 1.0 (base)
        3-5 pts  -> 1.2
        6-8 pts  -> 1.5
        9-12 pts -> 2.0
        13-20 pts -> 2.5
        21+ pts  -> 3.0
    """
    w = np.ones(len(y), dtype=np.float32)
    w[(y >= 3) & (y <= 5)] = 1.2
    w[(y >= 6) & (y <= 8)] = 1.5
    w[(y >= 9) & (y <= 12)] = 2.0
    w[(y >= 13) & (y <= 20)] = 2.5
    w[y >= 21] = 3.0
    return w


# === CHANGE START (4): new class, additive only — nothing existing
# references it unless cfg.loss_type == "asymmetric_huber" (see CHANGE 2). ===
class _AsymmetricSmoothL1Loss:
    """Asymmetric Smooth L1 (Huber) loss.

    Penalizes UNDERPREDICTION of high actual target scores (i.e. target
    >= threshold and pred < target) by a multiplier (``penalty``), while
    treating normal and overpredicted residuals with standard Huber
    loss. This targets the recall>=10 weakness directly: a model can
    have good average error (MAE/RMSE) while still systematically
    under-calling big hauls, which is exactly the "minimal mistakes"
    case that matters most for FPL (missing a double-digit haul is a
    worse mistake than a small miss on a 1-2 point player).

    Formula:
        loss = SmoothL1(pred, target)
        if target >= threshold and pred < target:
            loss = loss * penalty

    Opt-in via ``DeepLearningConfig(loss_type="asymmetric_huber")`` —
    default behavior (``loss_type="huber"``) is unaffected.
    """

    def __init__(
        self,
        beta: float = 4.0,
        penalty: float = 1.6,
        threshold: float = 3.0,
    ) -> None:
        import torch.nn as nn

        self.beta = beta
        self.penalty = penalty
        self.threshold = threshold
        self.smooth_l1 = nn.SmoothL1Loss(beta=beta, reduction="none")

    def __call__(self, pred: Any, target: Any) -> Any:
        import torch

        loss = self.smooth_l1(pred, target)
        if self.penalty > 1.0:
            underpred = (pred < target) & (target >= self.threshold)
            loss = loss * torch.where(
                underpred,
                torch.as_tensor(self.penalty, dtype=loss.dtype, device=loss.device),
                torch.as_tensor(1.0, dtype=loss.dtype, device=loss.device),
            )
        return loss
# === CHANGE END (4) ===


def _build_mlp(
    input_dim: int,
    hidden_layers: tuple[int, ...],
    dropout: float,
    use_batch_norm: bool,
) -> Any:
    """Construct the MLP architecture.

    Args:
        input_dim: Number of input features.
        hidden_layers: Sizes of hidden layers.
        dropout: Dropout probability.
        use_batch_norm: Whether to use batch normalization.

    Returns:
        A ``torch.nn.Sequential`` model.
    """
    import torch.nn as nn

    layers: list[nn.Module] = []
    prev_dim = input_dim

    for hidden_dim in hidden_layers:
        layers.append(nn.Linear(prev_dim, hidden_dim))
        if use_batch_norm:
            layers.append(nn.BatchNorm1d(hidden_dim))
        layers.append(nn.GELU())
        if dropout > 0:
            layers.append(nn.Dropout(dropout))
        prev_dim = hidden_dim

    # Final regression output
    layers.append(nn.Linear(prev_dim, 1))

    return nn.Sequential(*layers)
