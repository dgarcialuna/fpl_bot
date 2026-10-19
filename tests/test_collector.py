# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 David García Luna
from datetime import timedelta

import httpx

from fpl_bot.collector import collect_once
from fpl_bot.data.client import BASE_URL, FplClient
from fpl_bot.data.store import Store


def test_collect_once_end_to_end(payload_factory, t0):
    payloads = iter([payload_factory(), payload_factory({1: {"transfers_in_event": 9000}})])

    def handler(request):
        assert request.url.path.endswith("/bootstrap-static/")
        return httpx.Response(200, json=next(payloads))

    http = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    client = FplClient(http=http, min_interval=0, bootstrap_ttl=0)
    with Store(":memory:") as store:
        first = collect_once(client, store, now=t0)
        second = collect_once(client, store, now=t0 + timedelta(minutes=30))
    assert (first.event, first.n_players, first.n_changed) == (7, 2, 2)
    assert (second.n_players, second.n_changed) == (2, 1)
    assert second.snapshot_id > first.snapshot_id
