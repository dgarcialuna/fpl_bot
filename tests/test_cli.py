# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 David García Luna
import pytest

from fpl_bot import cli
from fpl_bot.data.client import FplApiError


def test_parser_defaults_and_loop_flag():
    args = cli.build_parser().parse_args(["snapshot", "--db", "x.db", "--loop"])
    assert (args.command, args.db, args.loop, args.interval) == ("snapshot", "x.db", True, 1800)


def test_command_is_required():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])


def test_single_run_returns_1_when_api_is_down(monkeypatch, tmp_path):
    def boom(client, store, **kwargs):
        raise FplApiError("down")

    monkeypatch.setattr(cli, "collect_once", boom)
    assert cli.main(["snapshot", "--db", str(tmp_path / "t.db")]) == 1


def test_loop_survives_a_failed_sample_and_enforces_minimum_interval(monkeypatch, tmp_path):
    calls = {"n": 0}
    slept: list[float] = []

    def flaky(client, store, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise FplApiError("blip")
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "collect_once", flaky)
    monkeypatch.setattr(cli.time, "sleep", slept.append)
    code = cli.main(["snapshot", "--db", str(tmp_path / "t.db"), "--loop", "--interval", "5"])
    assert code == 130
    assert calls["n"] == 2
    assert slept == [cli.MIN_LOOP_INTERVAL]
