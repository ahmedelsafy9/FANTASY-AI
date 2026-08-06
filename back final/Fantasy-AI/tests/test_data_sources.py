"""Unit tests for the DataSource interface and its skeleton implementations."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data_collection.interfaces.data_source import DataSource, DataSourceMetadata
from src.data_collection.sources.fpl_api_source import FPLApiDataSource
from src.data_collection.sources.understat_source import UnderstatDataSource
from src.data_collection.sources.vaastav_source import VaastavDataSource


def test_data_source_cannot_be_instantiated_directly() -> None:
    """DataSource is an abstract base class and must not be instantiable."""
    with pytest.raises(TypeError):
        DataSource()  # type: ignore[abstract]


def test_data_source_metadata_holds_expected_fields() -> None:
    """DataSourceMetadata should store name, source_url and optional extras."""
    metadata = DataSourceMetadata(
        name="vaastav",
        source_url="https://github.com/vaastav/Fantasy-Premier-League",
    )
    assert metadata.name == "vaastav"
    assert metadata.retrieved_at is None
    assert metadata.records_count is None
    assert metadata.extra == {}


@pytest.mark.parametrize(
    "source_factory,expected_name",
    [
        (lambda: VaastavDataSource(repo_url="https://example.com/repo"), "vaastav"),
        (lambda: FPLApiDataSource(base_url="https://example.com/api"), "fpl_api"),
        (lambda: UnderstatDataSource(base_url="https://example.com"), "understat"),
    ],
)
def test_concrete_sources_expose_expected_name(source_factory, expected_name: str) -> None:
    """Every concrete DataSource must expose a stable, expected `name`."""
    source = source_factory()
    assert isinstance(source, DataSource)
    assert source.name == expected_name


@pytest.mark.parametrize(
    "source_factory",
    [
        lambda: UnderstatDataSource(base_url="https://example.com"),
    ],
)
def test_remaining_skeletons_raise_not_implemented(source_factory, tmp_path: Path) -> None:
    """UnderstatDataSource remains an unimplemented skeleton.

    No method should silently return a fake result — every method must
    raise NotImplementedError until its owning sprint implements it.
    VaastavDataSource (Sprint 2) and FPLApiDataSource (Sprint 9) are
    implemented and covered separately in their own test modules.
    """
    source = source_factory()

    with pytest.raises(NotImplementedError):
        source.download(tmp_path)

    with pytest.raises(NotImplementedError):
        source.load(tmp_path)

    with pytest.raises(NotImplementedError):
        source.validate(pd.DataFrame())

    with pytest.raises(NotImplementedError):
        source.update(tmp_path)


def test_vaastav_source_defaults_to_empty_seasons_tuple() -> None:
    """VaastavDataSource must not hardcode any season by default."""
    source = VaastavDataSource(repo_url="https://example.com/repo")
    assert source._seasons == ()


def test_vaastav_source_accepts_explicit_seasons() -> None:
    """VaastavDataSource must accept an explicit, caller-provided season tuple."""
    source = VaastavDataSource(
        repo_url="https://example.com/repo", seasons=("2022-23", "2023-24")
    )
    assert source._seasons == ("2022-23", "2023-24")
