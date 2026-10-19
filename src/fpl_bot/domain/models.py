# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 David García Luna
"""Domain models. Pure data, no I/O and no third-party dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PlayerState:
    """What the API says about one player at one moment.

    ``now_cost`` is in tenths of a million (``75`` means £7.5m), as the API reports it.
    Fields that the API may omit are ``None`` rather than guessed.
    """

    player_id: int
    web_name: str
    team_id: int
    element_type: int
    now_cost: int
    selected_by_percent: float | None
    transfers_in_event: int | None
    transfers_out_event: int | None
    cost_change_event: int | None
    status: str | None
    chance_of_playing_next_round: int | None
    news: str
    news_added: str | None

    def tracked(self) -> tuple:
        """The fields whose change is worth recording (identity fields excluded)."""
        return (
            self.now_cost,
            self.selected_by_percent,
            self.transfers_in_event,
            self.transfers_out_event,
            self.cost_change_event,
            self.status,
            self.chance_of_playing_next_round,
            self.news,
            self.news_added,
        )


@dataclass(frozen=True, slots=True)
class Snapshot:
    """All players as seen in one API response."""

    taken_at: datetime
    event: int | None
    players: tuple[PlayerState, ...]
