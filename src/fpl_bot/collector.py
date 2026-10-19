# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 David García Luna
"""Take one snapshot of the whole player market and store it."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fpl_bot.data.client import FplClient
from fpl_bot.data.parsing import parse_bootstrap
from fpl_bot.data.store import Store


@dataclass(frozen=True, slots=True)
class CollectResult:
    snapshot_id: int
    event: int | None
    n_players: int
    n_changed: int


def collect_once(client: FplClient, store: Store, *, now: datetime | None = None) -> CollectResult:
    taken_at = now or datetime.now(UTC)
    snapshot = parse_bootstrap(client.bootstrap(), taken_at)
    snapshot_id, n_changed = store.save_snapshot(snapshot)
    return CollectResult(snapshot_id, snapshot.event, len(snapshot.players), n_changed)
