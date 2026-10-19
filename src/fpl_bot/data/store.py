# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 David García Luna
"""SQLite storage for price and injury history.

Only *changes* are stored: a player's row is written when something we track differs from the
last stored row. Sampling every 30 minutes would otherwise write ~700 rows per sample.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from fpl_bot.domain.models import PlayerState, Snapshot

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE players (
    player_id    INTEGER PRIMARY KEY,
    web_name     TEXT NOT NULL,
    team_id      INTEGER NOT NULL,
    element_type INTEGER NOT NULL
);
CREATE TABLE snapshots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    taken_at   TEXT NOT NULL,
    event      INTEGER,
    n_players  INTEGER NOT NULL,
    n_changed  INTEGER NOT NULL
);
CREATE TABLE player_history (
    snapshot_id                  INTEGER NOT NULL REFERENCES snapshots(id),
    player_id                    INTEGER NOT NULL REFERENCES players(player_id),
    now_cost                     INTEGER NOT NULL,
    selected_by_percent          REAL,
    transfers_in_event           INTEGER,
    transfers_out_event          INTEGER,
    cost_change_event            INTEGER,
    status                       TEXT,
    chance_of_playing_next_round INTEGER,
    news                         TEXT NOT NULL,
    news_added                   TEXT,
    PRIMARY KEY (snapshot_id, player_id)
);
CREATE INDEX idx_history_player ON player_history(player_id, snapshot_id);
"""

_TRACKED_COLUMNS = (
    "now_cost, selected_by_percent, transfers_in_event, transfers_out_event, "
    "cost_change_event, status, chance_of_playing_next_round, news, news_added"
)
_H_COLUMNS = ", ".join("h." + c.strip() for c in _TRACKED_COLUMNS.split(","))


class Store:
    def __init__(self, path: str | Path) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path))
        self._db.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _migrate(self) -> None:
        version = self._db.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            with self._db:
                self._db.executescript(_SCHEMA)
                self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        elif version != SCHEMA_VERSION:
            raise RuntimeError(
                f"database schema version {version} is not supported (expected {SCHEMA_VERSION})"
            )

    def save_snapshot(self, snapshot: Snapshot) -> tuple[int, int]:
        """Store a snapshot. Returns ``(snapshot_id, number_of_players_that_changed)``."""
        latest = self._latest_tracked()
        changed = [p for p in snapshot.players if latest.get(p.player_id) != p.tracked()]
        with self._db:
            cursor = self._db.execute(
                "INSERT INTO snapshots (taken_at, event, n_players, n_changed) VALUES (?, ?, ?, ?)",
                (_iso(snapshot.taken_at), snapshot.event, len(snapshot.players), len(changed)),
            )
            snapshot_id = int(cursor.lastrowid)
            self._db.executemany(
                "INSERT INTO players (player_id, web_name, team_id, element_type) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(player_id) DO UPDATE SET "
                "web_name = excluded.web_name, team_id = excluded.team_id, "
                "element_type = excluded.element_type",
                [(p.player_id, p.web_name, p.team_id, p.element_type) for p in snapshot.players],
            )
            self._db.executemany(
                f"INSERT INTO player_history (snapshot_id, player_id, {_TRACKED_COLUMNS}) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(snapshot_id, p.player_id, *p.tracked()) for p in changed],
            )
        return snapshot_id, len(changed)

    def _latest_tracked(self) -> dict[int, tuple]:
        rows = self._db.execute(
            f"SELECT h.player_id, {_H_COLUMNS} "
            "FROM player_history h JOIN ("
            "  SELECT player_id, MAX(snapshot_id) AS last_id FROM player_history GROUP BY player_id"
            ") l ON h.player_id = l.player_id AND h.snapshot_id = l.last_id"
        ).fetchall()
        return {row[0]: tuple(row[1:]) for row in rows}

    def snapshot_count(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0])

    def history(self, player_id: int) -> list[tuple[datetime, PlayerState]]:
        """Every recorded state of one player, oldest first."""
        rows = self._db.execute(
            "SELECT s.taken_at, p.player_id, p.web_name, p.team_id, p.element_type, "
            + _H_COLUMNS
            + " FROM player_history h"
            " JOIN snapshots s ON s.id = h.snapshot_id"
            " JOIN players p ON p.player_id = h.player_id"
            " WHERE h.player_id = ? ORDER BY h.snapshot_id",
            (player_id,),
        ).fetchall()
        return [(datetime.fromisoformat(row[0]), PlayerState(*row[1:])) for row in rows]


def _iso(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("snapshot timestamps must be timezone-aware")
    return moment.astimezone(UTC).isoformat()
