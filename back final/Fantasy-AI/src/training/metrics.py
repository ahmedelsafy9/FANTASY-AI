"""Regression evaluation metrics."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.training.models import RegressionMetrics


def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> RegressionMetrics:
    """Compute MAE, RMSE, and R² for a set of predictions.

    Args:
        y_true: Ground-truth target values.
        y_pred: Predicted target values.

    Returns:
        RegressionMetrics: The computed metrics.
    """
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    return RegressionMetrics(mae=mae, rmse=rmse, r2=r2)
