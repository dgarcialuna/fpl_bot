# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 David García Luna
from __future__ import annotations

import copy
from datetime import UTC, datetime

import pytest


def make_player(player_id: int = 1, **overrides):
    raw = {
        "id": player_id,
        "web_name": f"Player{player_id}",
        "team": 7,
        "element_type": 3,
        "now_cost": 75,
        "selected_by_percent": "12.3",
        "transfers_in_event": 1000,
        "transfers_out_event": 400,
        "cost_change_event": 0,
        "status": "a",
        "chance_of_playing_next_round": None,
        "news": "",
        "news_added": None,
    }
    raw.update(overrides)
    return raw


@pytest.fixture
def bootstrap_payload():
    return {
        "events": [{"id": 6, "is_current": False}, {"id": 7, "is_current": True}],
        "elements": [
            make_player(1),
            make_player(2, now_cost=60, status="i", chance_of_playing_next_round=0,
                        news="Knee injury - out for the season", news_added="2026-10-18T09:00:00Z"),
        ],
    }


@pytest.fixture
def payload_factory(bootstrap_payload):
    def build(changes_by_player=None):
        changes_by_player = changes_by_player or {}
        payload = copy.deepcopy(bootstrap_payload)
        for element in payload["elements"]:
            element.update(changes_by_player.get(element["id"], {}))
        return payload

    return build


@pytest.fixture
def t0():
    return datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
