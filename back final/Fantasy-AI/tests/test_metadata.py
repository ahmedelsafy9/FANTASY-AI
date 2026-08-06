"""Unit tests for src.metadata (team_metadata, player_metadata)."""

from __future__ import annotations

from src.metadata.player_metadata import build_player_metadata, player_photo_url
from src.metadata.team_metadata import build_team_metadata, team_badge_url


def test_team_badge_url_builds_from_code() -> None:
    """A team with a code must get a constructed badge URL."""
    assert team_badge_url(3) == "https://resources.premierleague.com/premierleague/badges/70/t3.png"


def test_team_badge_url_none_without_code() -> None:
    """No code means no fabricated URL — must return None."""
    assert team_badge_url(None) is None


def test_build_team_metadata_skips_records_without_id() -> None:
    """A team record with no 'id' must be skipped, not crash."""
    teams = [{"name": "No ID Team"}, {"id": 1, "name": "Arsenal", "code": 3}]
    result = build_team_metadata(teams)
    assert list(result.keys()) == [1]
    assert result[1].badge_url is not None


def test_player_photo_url_builds_from_photo_field() -> None:
    """A player with a photo field must get a constructed photo URL."""
    url = player_photo_url("118748.jpg")
    assert url == "https://resources.premierleague.com/premierleague25/photos/players/110x140/p118748.png"


def test_player_photo_url_none_without_photo_field() -> None:
    """No photo field means no fabricated URL — must return None."""
    assert player_photo_url(None) is None
    assert player_photo_url("") is None


def test_build_player_metadata_handles_missing_photo_gracefully() -> None:
    """A player missing the photo field must have photo_url=None, not crash."""
    elements = [{"id": 1, "web_name": "Salah", "team": 11, "photo": "1.jpg"}, {"id": 2, "web_name": "NoPhoto", "team": 12}]
    result = build_player_metadata(elements)
    assert result[1].photo_url is not None
    assert result[2].photo_url is None
