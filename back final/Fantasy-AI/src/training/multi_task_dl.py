"""Multi-Task Deep Learning model for Football Contribution Prediction.

Instead of directly predicting single-scalar `total_points`, this model learns
a shared latent representation of player, team, fixture, and historical state,
and branches into specialized output heads predicting fundamental football
contributions:
    1. Appearance: P(minutes > 0), P(minutes >= 60)
    2. Expected Goals: non-negative count expectation
    3. Expected Assists: non-negative count expectation
    4. Clean Sheet Probability: P(clean sheet)
    5. Expected Goals Conceded: non-negative count expectation
    6. Expected Saves: non-negative count expectation
    7. Cards: P(yellow card), P(red card)
    8. Expected Bonus: non-negative bonus contribution

At inference time, the model pipes its predicted event expectations into the
deterministic :class:`~src.prediction.scoring_engine.ScoringEngine` to produce
traceable, rule-compliant expected FPL points.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.prediction.scoring_engine import ScoringEngine

logger = get_logger(__name__)


@dataclass(frozen=True)
class MultiTaskDLConfig:
    """Hyperparameters for the multi-task neural network."""

    hidden_layers: tuple[int, ...] = (256, 128, 64)
    head_hidden_dim: int = 32
    dropout: float = 0.20
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    batch_size: int = 512
    epochs: int = 200
    patience: int = 15
    use_batch_norm: bool = True
    grad_clip_norm: float | None = 5.0
    random_state: int = 42

    # Task loss weights
    w_minutes: float = 1.0
    w_goals: float = 2.5
    w_assists: float = 2.0
    w_cs: float = 1.5
    w_gc: float = 1.0
    w_saves: float = 1.0
    w_cards: float = 0.5
    w_bonus: float = 1.5

    use_discrete_sample_weights: bool = True
    high_score_weight_power: float = 0.0


class MultiTaskTabularNN:
    """PyTorch multi-task neural network module."""

    @classmethod
    def create(
        cls,
        input_dim: int,
        hidden_layers: tuple[int, ...] = (256, 128, 64),
        head_hidden_dim: int = 32,
        dropout: float = 0.20,
        use_batch_norm: bool = True,
    ) -> Any:
        import torch
        import torch.nn as nn

        class _Module(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                # Backbone
                backbone_layers: list[nn.Module] = []
                prev_dim = input_dim
                for h_dim in hidden_layers:
                    backbone_layers.append(nn.Linear(prev_dim, h_dim))
                    if use_batch_norm:
                        backbone_layers.append(nn.BatchNorm1d(h_dim))
                    backbone_layers.append(nn.GELU())
                    if dropout > 0:
                        backbone_layers.append(nn.Dropout(dropout))
                    prev_dim = h_dim

                self.backbone = nn.Sequential(*backbone_layers)
                rep_dim = prev_dim

                # Specialized Heads
                # 1. Minutes (2 outputs: logits for [play_any, play_60])
                self.head_minutes = nn.Sequential(
                    nn.Linear(rep_dim, head_hidden_dim),
                    nn.GELU(),
                    nn.Linear(head_hidden_dim, 2),
                )

                # 2. Goals (1 output: non-negative count via softplus)
                self.head_goals = nn.Sequential(
                    nn.Linear(rep_dim, head_hidden_dim),
                    nn.GELU(),
                    nn.Linear(head_hidden_dim, 1),
                )

                # 3. Assists (1 output: non-negative count via softplus)
                self.head_assists = nn.Sequential(
                    nn.Linear(rep_dim, head_hidden_dim),
                    nn.GELU(),
                    nn.Linear(head_hidden_dim, 1),
                )

                # 4. Clean Sheet (1 output: logit)
                self.head_cs = nn.Sequential(
                    nn.Linear(rep_dim, head_hidden_dim),
                    nn.GELU(),
                    nn.Linear(head_hidden_dim, 1),
                )

                # 5. Goals Conceded (1 output: non-negative count)
                self.head_gc = nn.Sequential(
                    nn.Linear(rep_dim, head_hidden_dim),
                    nn.GELU(),
                    nn.Linear(head_hidden_dim, 1),
                )

                # 6. Saves (1 output: non-negative count)
                self.head_saves = nn.Sequential(
                    nn.Linear(rep_dim, head_hidden_dim),
                    nn.GELU(),
                    nn.Linear(head_hidden_dim, 1),
                )

                # 7. Cards (2 outputs: logits for [yellow, red])
                self.head_cards = nn.Sequential(
                    nn.Linear(rep_dim, head_hidden_dim),
                    nn.GELU(),
                    nn.Linear(head_hidden_dim, 2),
                )

                # 8. Bonus (1 output: non-negative points)
                self.head_bonus = nn.Sequential(
                    nn.Linear(rep_dim, head_hidden_dim),
                    nn.GELU(),
                    nn.Linear(head_hidden_dim, 1),
                )

            def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
                rep = self.backbone(x)
                return {
                    "minutes_logits": self.head_minutes(rep),
                    "goals_raw": self.head_goals(rep).squeeze(-1),
                    "assists_raw": self.head_assists(rep).squeeze(-1),
                    "cs_logits": self.head_cs(rep).squeeze(-1),
                    "gc_raw": self.head_gc(rep).squeeze(-1),
                    "saves_raw": self.head_saves(rep).squeeze(-1),
                    "cards_logits": self.head_cards(rep),
                    "bonus_raw": self.head_bonus(rep).squeeze(-1),
                }

        return _Module()


class TabularMultiTaskRegressor:
    """Scikit-learn compatible Multi-Task Contribution Model.

    Predicts expected football events and converts them into expected FPL points
    using the deterministic ScoringEngine.
    """

    def __init__(self, config: MultiTaskDLConfig | None = None) -> None:
        self.config = config or MultiTaskDLConfig()
        self._model: Any = None
        self._scaler_mean: np.ndarray | None = None
        self._scaler_std: np.ndarray | None = None
        self._input_dim: int | None = None
        self._feature_names: list[str] = []
        self._training_info: dict[str, Any] = {}

    def fit(
        self,
        X: Any,
        y: Any,
        sample_weight: np.ndarray | None = None,
        Y_events: pd.DataFrame | np.ndarray | dict[str, Any] | None = None,
    ) -> "TabularMultiTaskRegressor":
        """Train the multi-task model on input features and event targets."""
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
        from torch.utils.data import DataLoader, TensorDataset

        cfg = self.config
        start = time.perf_counter()

        # Reproducibility
        torch.manual_seed(cfg.random_state)
        np.random.seed(cfg.random_state)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(cfg.random_state)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

        # Store feature names if DataFrame
        if isinstance(X, pd.DataFrame):
            self._feature_names = list(X.columns)
        elif hasattr(X, "columns"):
            self._feature_names = list(X.columns)
        else:
            self._feature_names = [f"feature_{i}" for i in range(np.asarray(X).shape[1])]

        X_np = np.asarray(X, dtype=np.float32)
        y_np = np.asarray(y, dtype=np.float32).ravel()
        n_samples, self._input_dim = X_np.shape

        # Standardize features
        self._scaler_mean = X_np.mean(axis=0)
        self._scaler_std = X_np.std(axis=0)
        self._scaler_std[self._scaler_std < 1e-5] = 1.0
        X_scaled = np.clip((X_np - self._scaler_mean) / self._scaler_std, -50.0, 50.0)

        # Build Multi-Task Target Matrix (10 target channels)
        # [play_any, play_60, goals, assists, cs, gc, saves, yellow, red, bonus]
        Y_targets = self._prepare_target_matrix(y_np, Y_events, n_samples)

        # Weights
        if sample_weight is not None:
            w_np = np.asarray(sample_weight, dtype=np.float32).ravel()
        else:
            w_np = np.ones(n_samples, dtype=np.float32)

        if cfg.use_discrete_sample_weights:
            discrete_w = np.ones(len(y_np), dtype=np.float32)
            discrete_w[(y_np >= 3) & (y_np <= 5)] = 1.2
            discrete_w[(y_np >= 6) & (y_np <= 8)] = 1.5
            discrete_w[(y_np >= 9) & (y_np <= 12)] = 2.0
            discrete_w[(y_np >= 13) & (y_np <= 20)] = 2.5
            discrete_w[y_np >= 21] = 3.0
            w_np = w_np * discrete_w

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        X_tensor = torch.from_numpy(X_scaled).to(device)
        Y_tensor = torch.from_numpy(Y_targets).to(device)
        w_tensor = torch.from_numpy(w_np).to(device)

        # Chronological 85/15 train/val split
        n_val = max(1, int(n_samples * 0.15))
        n_train = n_samples - n_val

        X_tr, X_val = X_tensor[:n_train], X_tensor[n_train:]
        Y_tr, Y_val = Y_tensor[:n_train], Y_tensor[n_train:]
        w_tr, w_val = w_tensor[:n_train], w_tensor[n_train:]

        train_dataset = TensorDataset(X_tr, Y_tr, w_tr)
        train_loader = DataLoader(
            train_dataset,
            batch_size=cfg.batch_size,
            shuffle=True,
            drop_last=False,
            generator=torch.Generator().manual_seed(cfg.random_state),
        )

        # Build Multi-Task Network
        model = MultiTaskTabularNN.create(
            input_dim=self._input_dim,
            hidden_layers=cfg.hidden_layers,
            head_hidden_dim=cfg.head_hidden_dim,
            dropout=cfg.dropout,
            use_batch_norm=cfg.use_batch_norm,
        ).to(device)

        param_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
        logger.info(
            "Multi-Task DL Architecture: input=%d, hidden=%s, params=%d, device=%s",
            self._input_dim,
            cfg.hidden_layers,
            param_count,
            device,
        )

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

        # Loss functions
        bce_loss_fn = nn.BCEWithLogitsLoss(reduction="none")
        huber_loss_fn = nn.SmoothL1Loss(beta=1.0, reduction="none")

        def _compute_multi_task_loss(
            preds: dict[str, torch.Tensor],
            targets: torch.Tensor,
            weights: torch.Tensor | None = None,
        ) -> tuple[torch.Tensor, dict[str, float]]:
            # Targets:
            # 0: play_any, 1: play_60, 2: goals, 3: assists, 4: cs,
            # 5: gc, 6: saves, 7: yellow, 8: red, 9: bonus
            t_play_any = targets[:, 0]
            t_play_60 = targets[:, 1]
            t_goals = targets[:, 2]
            t_assists = targets[:, 3]
            t_cs = targets[:, 4]
            t_gc = targets[:, 5]
            t_saves = targets[:, 6]
            t_yellow = targets[:, 7]
            t_red = targets[:, 8]
            t_bonus = targets[:, 9]

            # Minutes loss (BCE for play_any and play_60)
            l_play_any = bce_loss_fn(preds["minutes_logits"][:, 0], t_play_any)
            l_play_60 = bce_loss_fn(preds["minutes_logits"][:, 1], t_play_60)
            l_minutes = l_play_any + l_play_60

            # Goals & Assists: Non-negative softplus activation + Huber loss
            pred_goals = F.softplus(preds["goals_raw"])
            l_goals = huber_loss_fn(pred_goals, t_goals)

            pred_assists = F.softplus(preds["assists_raw"])
            l_assists = huber_loss_fn(pred_assists, t_assists)

            # Clean sheet (BCE)
            l_cs = bce_loss_fn(preds["cs_logits"], t_cs)

            # Goals conceded (Softplus + Huber)
            pred_gc = F.softplus(preds["gc_raw"])
            l_gc = huber_loss_fn(pred_gc, t_gc)

            # Saves (Softplus + Huber)
            pred_saves = F.softplus(preds["saves_raw"])
            l_saves = huber_loss_fn(pred_saves, t_saves)

            # Cards (BCE)
            l_yellow = bce_loss_fn(preds["cards_logits"][:, 0], t_yellow)
            l_red = bce_loss_fn(preds["cards_logits"][:, 1], t_red)
            l_cards = l_yellow + l_red

            # Bonus (Softplus + Huber)
            pred_bonus = F.softplus(preds["bonus_raw"])
            l_bonus = huber_loss_fn(pred_bonus, t_bonus)

            # Weighted combined loss per sample
            sample_loss = (
                cfg.w_minutes * l_minutes
                + cfg.w_goals * l_goals
                + cfg.w_assists * l_assists
                + cfg.w_cs * l_cs
                + cfg.w_gc * l_gc
                + cfg.w_saves * l_saves
                + cfg.w_cards * l_cards
                + cfg.w_bonus * l_bonus
            )

            if weights is not None:
                total_loss = (sample_loss * weights).sum() / weights.sum()
            else:
                total_loss = sample_loss.mean()

            metrics_dict = {
                "l_min": float(l_minutes.mean().item()),
                "l_gls": float(l_goals.mean().item()),
                "l_ast": float(l_assists.mean().item()),
                "l_cs": float(l_cs.mean().item()),
                "l_bns": float(l_bonus.mean().item()),
            }

            return total_loss, metrics_dict

        best_val_loss = float("inf")
        best_state = None
        patience_counter = 0

        for epoch in range(1, cfg.epochs + 1):
            model.train()
            epoch_loss = 0.0
            epoch_weight_sum = 0.0

            for X_b, Y_b, w_b in train_loader:
                optimizer.zero_grad()
                preds = model(X_b)
                batch_loss, _ = _compute_multi_task_loss(preds, Y_b, w_b)
                batch_loss.backward()

                if cfg.grad_clip_norm is not None:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip_norm)

                optimizer.step()

                b_w = w_b.sum().item()
                epoch_loss += batch_loss.item() * b_w
                epoch_weight_sum += b_w

            avg_train_loss = epoch_loss / max(epoch_weight_sum, 1e-8)

            # Validation
            model.eval()
            with torch.no_grad():
                val_preds = model(X_val)
                val_loss_t, val_sub_losses = _compute_multi_task_loss(val_preds, Y_val, None)
                val_loss = val_loss_t.item()

            scheduler.step(val_loss)

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1

            if epoch % 20 == 0 or epoch == 1 or patience_counter == 0:
                lr_curr = optimizer.param_groups[0]["lr"]
                logger.info(
                    "  Epoch %3d/%d — train=%.4f, val=%.4f, goals_l=%.4f, cs_l=%.4f, lr=%.2e (patience %d/%d)",
                    epoch,
                    cfg.epochs,
                    avg_train_loss,
                    val_loss,
                    val_sub_losses["l_gls"],
                    val_sub_losses["l_cs"],
                    lr_curr,
                    patience_counter,
                    cfg.patience,
                )

            if patience_counter >= cfg.patience:
                logger.info("  Early stopping at epoch %d (best val=%.4f).", epoch, best_val_loss)
                break

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
            "train_seconds": train_duration,
            "device": str(device),
        }

        logger.info(
            "Multi-Task DL training complete: %d epochs, best_val=%.4f, duration=%.2fs",
            epoch,
            best_val_loss,
            train_duration,
        )

        return self

    def _prepare_target_matrix(
        self,
        y: np.ndarray,
        Y_events: pd.DataFrame | np.ndarray | dict[str, Any] | None,
        n_samples: int,
    ) -> np.ndarray:
        """Construct standard 10-channel multi-task target array."""
        targets = np.zeros((n_samples, 10), dtype=np.float32)

        if isinstance(Y_events, pd.DataFrame):
            # Extract actual event targets
            mins = pd.to_numeric(Y_events.get("minutes", 0.0), errors="coerce").fillna(0.0).to_numpy()
            targets[:, 0] = (mins > 0).astype(np.float32)
            targets[:, 1] = (mins >= 60).astype(np.float32)

            targets[:, 2] = pd.to_numeric(Y_events.get("goals_scored", 0.0), errors="coerce").fillna(0.0).to_numpy()
            targets[:, 3] = pd.to_numeric(Y_events.get("assists", 0.0), errors="coerce").fillna(0.0).to_numpy()
            targets[:, 4] = pd.to_numeric(Y_events.get("clean_sheets", 0.0), errors="coerce").fillna(0.0).to_numpy()
            targets[:, 5] = pd.to_numeric(Y_events.get("goals_conceded", 0.0), errors="coerce").fillna(0.0).to_numpy()
            targets[:, 6] = pd.to_numeric(Y_events.get("saves", 0.0), errors="coerce").fillna(0.0).to_numpy()
            targets[:, 7] = pd.to_numeric(Y_events.get("yellow_cards", 0.0), errors="coerce").fillna(0.0).to_numpy()
            targets[:, 8] = pd.to_numeric(Y_events.get("red_cards", 0.0), errors="coerce").fillna(0.0).to_numpy()
            targets[:, 9] = pd.to_numeric(Y_events.get("bonus", 0.0), errors="coerce").fillna(0.0).to_numpy()
            return targets

        if isinstance(Y_events, dict):
            mins = np.asarray(Y_events.get("minutes", 0.0), dtype=np.float32)
            targets[:, 0] = (mins > 0).astype(np.float32)
            targets[:, 1] = (mins >= 60).astype(np.float32)
            targets[:, 2] = np.asarray(Y_events.get("goals_scored", 0.0), dtype=np.float32)
            targets[:, 3] = np.asarray(Y_events.get("assists", 0.0), dtype=np.float32)
            targets[:, 4] = np.asarray(Y_events.get("clean_sheets", 0.0), dtype=np.float32)
            targets[:, 5] = np.asarray(Y_events.get("goals_conceded", 0.0), dtype=np.float32)
            targets[:, 6] = np.asarray(Y_events.get("saves", 0.0), dtype=np.float32)
            targets[:, 7] = np.asarray(Y_events.get("yellow_cards", 0.0), dtype=np.float32)
            targets[:, 8] = np.asarray(Y_events.get("red_cards", 0.0), dtype=np.float32)
            targets[:, 9] = np.asarray(Y_events.get("bonus", 0.0), dtype=np.float32)
            return targets

        # Fallback if raw events are not supplied: derive surrogate targets from y
        targets[:, 0] = (y > 0).astype(np.float32)
        targets[:, 1] = (y >= 2).astype(np.float32)
        targets[:, 2] = np.maximum((y - 2.0) / 5.0, 0.0).astype(np.float32)
        targets[:, 3] = np.maximum((y - 2.0) / 4.0, 0.0).astype(np.float32)
        targets[:, 4] = (y >= 6).astype(np.float32)
        targets[:, 9] = np.clip(np.maximum(y - 6.0, 0.0), 0.0, 3.0).astype(np.float32)
        return targets

    def predict_events(self, X: Any) -> dict[str, np.ndarray]:
        """Generate predicted event counts and probabilities."""
        if self._model is None:
            raise RuntimeError("TabularMultiTaskRegressor has not been fitted yet.")

        import torch
        import torch.nn.functional as F

        X_np = np.asarray(X, dtype=np.float32)
        X_scaled = np.clip((X_np - self._scaler_mean) / self._scaler_std, -50.0, 50.0)

        self._model.eval()
        with torch.no_grad():
            X_tensor = torch.from_numpy(X_scaled)
            raw = self._model(X_tensor)

            p_play_any = torch.sigmoid(raw["minutes_logits"][:, 0]).numpy()
            p_play_60 = torch.sigmoid(raw["minutes_logits"][:, 1]).numpy()
            exp_goals = F.softplus(raw["goals_raw"]).numpy()
            exp_assists = F.softplus(raw["assists_raw"]).numpy()
            cs_prob = torch.sigmoid(raw["cs_logits"]).numpy()
            exp_gc = F.softplus(raw["gc_raw"]).numpy()
            exp_saves = F.softplus(raw["saves_raw"]).numpy()
            p_yellow = torch.sigmoid(raw["cards_logits"][:, 0]).numpy()
            p_red = torch.sigmoid(raw["cards_logits"][:, 1]).numpy()
            exp_bonus = F.softplus(raw["bonus_raw"]).numpy()

        return {
            "p_play_any": p_play_any,
            "p_play_60": p_play_60,
            "expected_goals": exp_goals,
            "expected_assists": exp_assists,
            "clean_sheet_prob": cs_prob,
            "expected_goals_conceded": exp_gc,
            "expected_saves": exp_saves,
            "expected_yellow_cards": p_yellow,
            "expected_red_cards": p_red,
            "expected_bonus": exp_bonus,
        }

    def predict_breakdown(self, X: Any) -> pd.DataFrame:
        """Generate full point contribution breakdown DataFrame."""
        events = self.predict_events(X)
        breakdown = ScoringEngine.calculate_breakdown(events, X)
        return breakdown

    def predict_distribution(
        self,
        X: Any,
        n_simulations: int = 2000,
        random_state: int = 42,
    ) -> pd.DataFrame:
        """Generate full outcome distribution, percentiles, upside, and captaincy scores."""
        events = self.predict_events(X)
        return ScoringEngine.calculate_distribution(
            events,
            positions=X,
            n_simulations=n_simulations,
            random_state=random_state,
        )

    def predict(self, X: Any) -> np.ndarray:
        """Generate expected total FPL points using the ScoringEngine."""
        breakdown = self.predict_breakdown(X)
        return breakdown["predicted_total_points"].to_numpy()

    def get_params(self, deep: bool = True) -> dict[str, Any]:
        """Scikit-learn parameter getter."""
        return {"config": self.config}

    def set_params(self, **params: Any) -> "TabularMultiTaskRegressor":
        """Scikit-learn parameter setter."""
        if "config" in params:
            self.config = params["config"]
        return self

    def __getstate__(self) -> dict[str, Any]:
        """Custom pickling support."""
        state = self.__dict__.copy()
        if self._model is not None:
            import torch

            state["_model_state_dict"] = self._model.state_dict()
            state["_model_class_args"] = {
                "input_dim": self._input_dim,
                "hidden_layers": self.config.hidden_layers,
                "head_hidden_dim": self.config.head_hidden_dim,
                "dropout": self.config.dropout,
                "use_batch_norm": self.config.use_batch_norm,
            }
            del state["_model"]
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Custom unpickling support."""
        model_state_dict = state.pop("_model_state_dict", None)
        model_class_args = state.pop("_model_class_args", None)
        self.__dict__.update(state)

        if model_state_dict is not None and model_class_args is not None:
            model = MultiTaskTabularNN.create(**model_class_args)
            model.load_state_dict(model_state_dict)
            model.eval()
            self._model = model
        else:
            self._model = None
