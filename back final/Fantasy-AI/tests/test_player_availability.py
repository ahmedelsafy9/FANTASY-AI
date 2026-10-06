"""Unit tests for the PlayerAvailability derivation pipeline."""

import pytest
from src.metadata.player_metadata import PlayerMetadata
from src.availability.player_availability import (
    derive_player_availability,
    PlayerAvailability,
    _classify_news,
)


def test_classify_news_categories():
    assert _classify_news("Red card against Chelsea") == "suspension"
    assert _classify_news("Serving a 3 match ban") == "suspension"
    assert _classify_news("Has joined Real Madrid permanently") == "transfer"
    assert _classify_news("On loan until end of season") == "transfer"
    assert _classify_news("Hamstring injury - 75% chance") == "injury"
    assert _classify_news("Illness - Expected back next week") == "injury"
    assert _classify_news(None) is None
    assert _classify_news("") is None


def test_derive_fit_player():
    meta = PlayerMetadata(
        player_id=1,
        web_name="Saka",
        team_id=1,
        photo_url=None,
        position="MID",
        status="a",
        chance_of_playing_next_round=None,
        news="",
        minutes_season=1800,
        starts_season=20,
    )
    avail = derive_player_availability(meta, historical_avg_minutes=85.0)

    assert isinstance(avail, PlayerAvailability)
    assert avail.player_id == 1
    assert avail.availability_status == "fit"
    assert avail.injury_flag is False
    assert avail.doubt_flag is False
    assert avail.suspension_flag is False
    assert avail.ruled_out_flag is False
    assert avail.expected_to_start is True
    assert avail.expected_minutes == 85.0
    assert avail.rotation_risk == 0.0


def test_derive_doubtful_player_75():
    meta = PlayerMetadata(
        player_id=2,
        web_name="White",
        team_id=1,
        photo_url=None,
        position="DEF",
        status="d",
        chance_of_playing_next_round=75,
        news="Groin injury - 75% chance of playing",
        minutes_season=1800,
        starts_season=20,
    )
    avail = derive_player_availability(meta, historical_avg_minutes=90.0)

    assert avail.availability_status == "doubtful"
    assert avail.doubt_flag is True
    assert avail.injury_flag is False
    assert avail.ruled_out_flag is False
    assert avail.expected_to_start is True
    assert avail.expected_minutes == pytest.approx(67.5)


def test_derive_minor_injury_25():
    meta = PlayerMetadata(
        player_id=3,
        web_name="Odegaard",
        team_id=1,
        photo_url=None,
        position="MID",
        status="d",
        chance_of_playing_next_round=25,
        news="Ankle injury - 25% chance of playing",
    )
    avail = derive_player_availability(meta, historical_avg_minutes=80.0)

    assert avail.availability_status == "minor_injury"
    assert avail.injury_flag is True
    assert avail.doubt_flag is True
    assert avail.expected_to_start is False
    assert avail.expected_minutes == pytest.approx(20.0)


def test_derive_major_injury_status_i():
    meta = PlayerMetadata(
        player_id=4,
        web_name="Saliba",
        team_id=1,
        photo_url=None,
        position="DEF",
        status="i",
        chance_of_playing_next_round=0,
        news="Back injury - Unknown return date",
    )
    avail = derive_player_availability(meta, historical_avg_minutes=90.0)

    assert avail.availability_status == "major_injury"
    assert avail.injury_flag is True
    assert avail.ruled_out_flag is True
    assert avail.expected_minutes == 0.0
    assert avail.expected_to_start is False


def test_derive_suspended_status_s():
    meta = PlayerMetadata(
        player_id=5,
        web_name="Romero",
        team_id=2,
        photo_url=None,
        position="DEF",
        status="s",
        chance_of_playing_next_round=0,
        news="Suspended until GW6",
    )
    avail = derive_player_availability(meta, historical_avg_minutes=90.0)

    assert avail.availability_status == "suspended"
    assert avail.suspension_flag is True
    assert avail.ruled_out_flag is True
    assert avail.expected_minutes == 0.0
    assert avail.expected_to_start is False


def test_derive_unavailable_status_u():
    meta = PlayerMetadata(
        player_id=6,
        web_name="Martinelli",
        team_id=1,
        photo_url=None,
        position="MID",
        status="u",
        news="Has joined Al Hilal permanently",
    )
    avail = derive_player_availability(meta, historical_avg_minutes=75.0)

    assert avail.availability_status == "unavailable"
    assert avail.ruled_out_flag is True
    assert avail.expected_minutes == 0.0
    assert avail.expected_to_start is False
