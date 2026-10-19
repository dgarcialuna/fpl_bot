# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 David García Luna
import pytest

from fpl_bot.data.parsing import SchemaError, parse_bootstrap

from .conftest import make_player


def test_parses_players_and_current_event(bootstrap_payload, t0):
    snap = parse_bootstrap(bootstrap_payload, t0)
    assert snap.event == 7
    assert [p.player_id for p in snap.players] == [1, 2]
    first, injured = snap.players
    assert first.selected_by_percent == 12.3
    assert first.now_cost == 75
    assert injured.status == "i"
    assert injured.news.startswith("Knee injury")


def test_missing_optional_fields_become_none(t0):
    raw = make_player(1)
    for key in ("transfers_in_event", "transfers_out_event", "cost_change_event",
                "selected_by_percent", "status", "news", "news_added"):
        del raw[key]
    snap = parse_bootstrap({"elements": [raw]}, t0)
    player = snap.players[0]
    assert player.transfers_in_event is None
    assert player.selected_by_percent is None
    assert player.news == ""
    assert snap.event is None


def test_unparseable_optional_number_becomes_none(t0):
    snap = parse_bootstrap({"elements": [make_player(1, selected_by_percent="n/a")]}, t0)
    assert snap.players[0].selected_by_percent is None


@pytest.mark.parametrize("payload", [None, [], {}, {"elements": "x"}, {"elements": []}])
def test_rejects_payloads_that_are_not_bootstrap(payload, t0):
    with pytest.raises(SchemaError):
        parse_bootstrap(payload, t0)


def test_rejects_player_without_required_field(t0):
    raw = make_player(1)
    del raw["now_cost"]
    with pytest.raises(SchemaError, match="now_cost"):
        parse_bootstrap({"elements": [raw]}, t0)
