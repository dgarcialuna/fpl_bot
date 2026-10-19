# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 David García Luna
import httpx
import pytest

from fpl_bot.data.client import BASE_URL, FplApiError, FplClient


class FakeTime:
    """Deterministic clock: sleeping advances time instead of waiting."""

    def __init__(self):
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(handler, ft, **kwargs):
    http = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    return FplClient(http=http, clock=ft.clock, sleep=ft.sleep, **kwargs)


def test_returns_json_on_success():
    ft = FakeTime()
    client = make_client(lambda r: httpx.Response(200, json={"ok": True}), ft)
    assert client.get_json("/x/") == {"ok": True}
    assert ft.sleeps == []


def test_retries_on_429_and_5xx_then_succeeds():
    ft = FakeTime()
    responses = iter([httpx.Response(429), httpx.Response(503), httpx.Response(200, json=[1])])
    client = make_client(lambda r: next(responses), ft, min_interval=0)
    assert client.get_json("/x/") == [1]
    assert ft.sleeps == [1.0, 2.0]  # exponential backoff: 2**0, 2**1


def test_honours_retry_after_header():
    ft = FakeTime()
    responses = iter(
        [httpx.Response(429, headers={"Retry-After": "10"}), httpx.Response(200, json=1)]
    )
    client = make_client(lambda r: next(responses), ft, min_interval=0)
    assert client.get_json("/x/") == 1
    assert ft.sleeps == [10.0]


def test_gives_up_after_max_retries():
    ft = FakeTime()
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500)

    client = make_client(handler, ft, min_interval=0, max_retries=2)
    with pytest.raises(FplApiError, match="3 attempts"):
        client.get_json("/x/")
    assert len(calls) == 3


def test_does_not_retry_client_errors():
    ft = FakeTime()
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404)

    client = make_client(handler, ft, min_interval=0)
    with pytest.raises(FplApiError, match="404"):
        client.get_json("/missing/")
    assert len(calls) == 1


def test_retries_on_non_json_200():
    ft = FakeTime()
    responses = iter(
        [httpx.Response(200, text="<html>updating</html>"), httpx.Response(200, json=5)]
    )
    client = make_client(lambda r: next(responses), ft, min_interval=0)
    assert client.get_json("/x/") == 5


def test_retries_on_network_error():
    ft = FakeTime()
    state = {"n": 0}

    def handler(request):
        state["n"] += 1
        if state["n"] == 1:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json=9)

    client = make_client(handler, ft, min_interval=0)
    assert client.get_json("/x/") == 9


def test_spaces_requests_by_min_interval():
    ft = FakeTime()
    client = make_client(lambda r: httpx.Response(200, json=1), ft, min_interval=2.0)
    client.get_json("/a/")
    client.get_json("/b/")
    assert ft.sleeps == [2.0]


def test_bootstrap_is_cached_within_ttl_and_refreshed_after():
    ft = FakeTime()
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"n": len(calls)})

    client = make_client(handler, ft, min_interval=0, bootstrap_ttl=60)
    assert client.bootstrap() == {"n": 1}
    ft.now += 30
    assert client.bootstrap() == {"n": 1}
    ft.now += 31
    assert client.bootstrap() == {"n": 2}
    assert len(calls) == 2
