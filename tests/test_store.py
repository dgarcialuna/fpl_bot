# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 David García Luna
from datetime import UTC, datetime, timedelta

import pytest

from fpl_bot.data.parsing import parse_bootstrap
from fpl_bot.data.store import Store


@pytest.fixture
def store():
    with Store(":memory:") as s:
        yield s


def test_first_snapshot_stores_every_player(store, bootstrap_payload, t0):
    _, changed = store.save_snapshot(parse_bootstrap(bootstrap_payload, t0))
    assert changed == 2
    assert len(store.history(1)) == 1


def test_identical_snapshot_stores_no_new_player_rows(store, bootstrap_payload, t0):
    store.save_snapshot(parse_bootstrap(bootstrap_payload, t0))
    _, changed = store.save_snapshot(parse_bootstrap(bootstrap_payload, t0 + timedelta(minutes=30)))
    assert changed == 0
    assert store.snapshot_count() == 2  # the sample itself is still recorded
    assert len(store.history(1)) == 1


def test_only_changed_players_are_written(store, payload_factory, t0):
    store.save_snapshot(parse_bootstrap(payload_factory(), t0))
    later = payload_factory({1: {"transfers_in_event": 5000}})
    _, changed = store.save_snapshot(parse_bootstrap(later, t0 + timedelta(minutes=30)))
    assert changed == 1
    assert len(store.history(1)) == 2
    assert len(store.history(2)) == 1


def test_price_drop_and_injury_news_are_captured(store, payload_factory, t0):
    store.save_snapshot(parse_bootstrap(payload_factory(), t0))
    later = payload_factory({1: {"now_cost": 74, "cost_change_event": -1, "status": "i"}})
    store.save_snapshot(parse_bootstrap(later, t0 + timedelta(hours=24)))
    history = store.history(1)
    assert [state.now_cost for _, state in history] == [75, 74]
    assert history[-1][1].status == "i"
    assert history[-1][0] == t0 + timedelta(hours=24)


def test_timestamps_must_be_timezone_aware(store, bootstrap_payload):
    naive = datetime(2026, 10, 19, 12, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        store.save_snapshot(parse_bootstrap(bootstrap_payload, naive))


def test_database_persists_on_disk(tmp_path, bootstrap_payload):
    path = tmp_path / "nested" / "fpl.db"
    taken = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    with Store(path) as s:
        s.save_snapshot(parse_bootstrap(bootstrap_payload, taken))
    with Store(path) as s:
        assert s.snapshot_count() == 1
        _, changed = s.save_snapshot(parse_bootstrap(bootstrap_payload, taken + timedelta(hours=1)))
        assert changed == 0  # state was remembered across connections


def test_unsupported_schema_version_is_refused(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    raw.execute("PRAGMA user_version = 99")
    raw.close()
    with pytest.raises(RuntimeError, match="schema version 99"):
        Store(path)
