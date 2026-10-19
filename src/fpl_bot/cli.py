# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 David García Luna
"""Command line entry point: ``fpl-bot snapshot``."""

from __future__ import annotations

import argparse
import logging
import os
import time

from fpl_bot.collector import collect_once
from fpl_bot.data.client import FplApiError, FplClient
from fpl_bot.data.parsing import SchemaError
from fpl_bot.data.store import Store

log = logging.getLogger("fpl_bot")

MIN_LOOP_INTERVAL = 300  # seconds; sampling faster than this is impolite and adds little


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fpl-bot", description="Unofficial FPL assistant")
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot", help="record the current price/injury state of all players")
    snap.add_argument(
        "--db",
        default=os.environ.get("FPL_BOT_DB", "data/fpl_bot.db"),
        help="SQLite file (default: $FPL_BOT_DB or data/fpl_bot.db)",
    )
    snap.add_argument("--loop", action="store_true", help="keep sampling until interrupted")
    snap.add_argument(
        "--interval",
        type=int,
        default=1800,
        help=f"seconds between samples with --loop (minimum {MIN_LOOP_INTERVAL})",
    )
    return parser


def run_snapshot(db: str, loop: bool, interval: int) -> int:
    interval = max(interval, MIN_LOOP_INTERVAL)
    with FplClient() as client, Store(db) as store:
        while True:
            try:
                result = collect_once(client, store)
                log.info(
                    "snapshot %d: GW %s, %d players, %d changed",
                    result.snapshot_id,
                    result.event,
                    result.n_players,
                    result.n_changed,
                )
            except (FplApiError, SchemaError) as exc:
                log.error("snapshot failed: %s", exc)
                if not loop:
                    return 1
            if not loop:
                return 0
            time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "snapshot":
            return run_snapshot(args.db, args.loop, args.interval)
    except KeyboardInterrupt:
        return 130
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
