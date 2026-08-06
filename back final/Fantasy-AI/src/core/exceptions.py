"""Domain-level exceptions shared across all layers of Fantasy-AI.

Centralizing exceptions here (rather than scattering ad-hoc exceptions
throughout each layer) keeps error handling consistent and makes it
easy for callers to catch a single family of exceptions.
"""

from __future__ import annotations


class FantasyAIError(Exception):
    """Base class for all Fantasy-AI application exceptions."""


class DataSourceError(FantasyAIError):
    """Raised when a :class:`~src.data_collection.interfaces.data_source.DataSource`
    operation (download, load, validate, update) fails.
    """


class DataSourceNotAvailableError(DataSourceError):
    """Raised when a requested data source cannot be reached or is offline."""


class DataValidationError(FantasyAIError):
    """Raised when a dataset fails validation rules (missing values,
    duplicate rows, invalid types, invalid identifiers, etc.).
    """


class ConfigurationError(FantasyAIError):
    """Raised when application configuration is missing or invalid."""


class ModelNotFoundError(FantasyAIError):
    """Raised when a requested trained model artifact cannot be located."""


class PredictionError(FantasyAIError):
    """Raised when the prediction pipeline fails to produce a result."""


class PlayerNotFoundError(FantasyAIError):
    """Raised when a requested player identifier does not exist in the dataset."""
