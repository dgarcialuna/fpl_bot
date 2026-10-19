# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 David García Luna
"""Polite HTTP client for the public FPL API.

There is no documented rate limit, so the client assumes there may be one: it spaces requests,
backs off on 429 and 5xx, honours ``Retry-After`` and caches the big shared payload.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

log = logging.getLogger(__name__)

BASE_URL = "https://fantasy.premierleague.com/api"
DEFAULT_USER_AGENT = "fpl-bot/0.1 (+https://github.com/dgarcialuna/fpl_bot)"


class FplApiError(RuntimeError):
    """The API could not be read, after retries where retrying makes sense."""


class FplClient:
    def __init__(
        self,
        *,
        http: httpx.Client | None = None,
        min_interval: float = 1.0,
        max_retries: int = 4,
        backoff_base: float = 2.0,
        max_backoff: float = 60.0,
        bootstrap_ttl: float = 60.0,
        user_agent: str = DEFAULT_USER_AGENT,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = http or httpx.Client(
            base_url=BASE_URL, timeout=20.0, headers={"User-Agent": user_agent}
        )
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._max_backoff = max_backoff
        self._bootstrap_ttl = bootstrap_ttl
        self._clock = clock
        self._sleep = sleep
        self._last_request: float | None = None
        self._bootstrap_cache: tuple[float, Any] | None = None

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> FplClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def bootstrap(self) -> Any:
        """``bootstrap-static``: every player, team and gameweek. One call serves all users."""
        now = self._clock()
        if self._bootstrap_cache and now - self._bootstrap_cache[0] < self._bootstrap_ttl:
            return self._bootstrap_cache[1]
        data = self.get_json("/bootstrap-static/")
        self._bootstrap_cache = (self._clock(), data)
        return data

    def get_json(self, path: str) -> Any:
        last_problem = "no attempt made"
        for attempt in range(self._max_retries + 1):
            self._respect_min_interval()
            retry_after: float | None = None
            try:
                response = self._http.get(path)
            except httpx.TransportError as exc:
                last_problem = f"network error: {exc!r}"
            else:
                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError:
                        # The game sometimes serves a non-JSON page while it updates.
                        last_problem = "200 response was not valid JSON"
                elif response.status_code == 429 or response.status_code >= 500:
                    last_problem = f"HTTP {response.status_code}"
                    retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                else:
                    raise FplApiError(f"GET {path} failed with HTTP {response.status_code}")
            if attempt == self._max_retries:
                break
            delay = min(self._backoff_base**attempt, self._max_backoff)
            if retry_after is not None:
                delay = min(max(delay, retry_after), self._max_backoff)
            log.warning("GET %s: %s; retrying in %.1fs", path, last_problem, delay)
            self._sleep(delay)
        raise FplApiError(
            f"GET {path} failed after {self._max_retries + 1} attempts: {last_problem}"
        )

    def _respect_min_interval(self) -> None:
        if self._last_request is not None:
            wait = self._min_interval - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
