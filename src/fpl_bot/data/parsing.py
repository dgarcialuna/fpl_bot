# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 David García Luna
"""Turn raw ``bootstrap-static`` JSON into domain models.

The API is unofficial and undocumented, so parsing is strict about the few fields we cannot
work without and lenient about the rest: an optional field that disappears becomes ``None``
instead of crashing the collector.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fpl_bot.domain.models import PlayerState, Snapshot


class SchemaError(ValueError):
    """The payload does not look like a ``bootstrap-static`` response."""


_REQUIRED = ("id", "web_name", "team", "element_type", "now_cost")


def _opt_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _current_event(payload: dict[str, Any]) -> int | None:
    for event in payload.get("events") or []:
        if isinstance(event, dict) and event.get("is_current"):
            return _opt_int(event.get("id"))
    return None


def parse_player(raw: dict[str, Any]) -> PlayerState:
    missing = [key for key in _REQUIRED if raw.get(key) is None]
    if missing:
        raise SchemaError(f"player is missing required fields: {', '.join(missing)}")
    return PlayerState(
        player_id=int(raw["id"]),
        web_name=str(raw["web_name"]),
        team_id=int(raw["team"]),
        element_type=int(raw["element_type"]),
        now_cost=int(raw["now_cost"]),
        selected_by_percent=_opt_float(raw.get("selected_by_percent")),
        transfers_in_event=_opt_int(raw.get("transfers_in_event")),
        transfers_out_event=_opt_int(raw.get("transfers_out_event")),
        cost_change_event=_opt_int(raw.get("cost_change_event")),
        status=raw.get("status"),
        chance_of_playing_next_round=_opt_int(raw.get("chance_of_playing_next_round")),
        news=str(raw.get("news") or ""),
        news_added=raw.get("news_added"),
    )


def parse_bootstrap(payload: Any, taken_at: datetime) -> Snapshot:
    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
        raise SchemaError("payload has no 'elements' list")
    players = tuple(parse_player(raw) for raw in payload["elements"])
    if not players:
        raise SchemaError("payload contains no players")
    return Snapshot(taken_at=taken_at, event=_current_event(payload), players=players)
