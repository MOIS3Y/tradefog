"""Bounded public HTTP transport with process-local provider cooldown."""

import asyncio
import math
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from loguru import logger

from tradefog.market.contracts import MarketFailure


class MarketTransport:
    """Share a connection pool, concurrency budget and provider cooldowns."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        """Use an injected, lifespan-owned client without private headers."""
        self.client = client
        self.slots = asyncio.Semaphore(8)
        self.cooldowns: dict[str, float] = {}

    def check_cooldown(self, provider: str) -> None:
        """Reject locally while the upstream requested pause is active."""
        delay = self.cooldowns.get(provider, 0) - time.monotonic()
        if delay > 0:
            raise MarketFailure(
                "market_rate_limited",
                "Market source is cooling down",
                503,
                math.ceil(delay),
            )

    def cool_down(self, provider: str, seconds: int) -> None:
        """Extend a pause without shortening an existing provider deadline."""
        self.cooldowns[provider] = max(
            self.cooldowns.get(provider, 0),
            time.monotonic() + seconds,
        )

    async def get(
        self,
        provider: str,
        url: str,
        params: dict[str, str | int],
    ) -> dict[str, Any]:
        """Perform one bounded request; never retry inside the HTTP call."""
        self.check_cooldown(provider)
        started = time.monotonic()
        outcome = "ok"
        acquired = False
        try:
            await asyncio.wait_for(self.slots.acquire(), timeout=1)
            acquired = True
            self.check_cooldown(provider)
            async with asyncio.timeout(12):
                response = await self.client.get(url, params=params)
            retry = retry_after(response.headers.get("Retry-After"))
            if response.status_code in (403, 429):
                delay = max(retry, 600 if response.status_code == 403 else 60)
                self.cool_down(provider, delay)
                self.check_cooldown(provider)
            if response.is_error:
                if retry:
                    self.cool_down(provider, retry)
                raise MarketFailure(
                    "market_unavailable",
                    "Market source is unavailable",
                    503,
                    retry,
                )
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("Expected object")
            if payload.get("retCode") in (10006, 10429):
                self.cool_down(provider, max(60, retry))
                self.check_cooldown(provider)
            if payload.get("retCode") != 0:
                raise MarketFailure(
                    "market_rejected",
                    "Market source rejected the request",
                )
            result = payload.get("result")
            if not isinstance(result, dict):
                raise TypeError("Missing result")
            return result
        except (TimeoutError, httpx.TimeoutException) as error:
            outcome = "timeout"
            raise MarketFailure(
                "market_timeout",
                "Market request timed out",
                504,
            ) from error
        except httpx.RequestError as error:
            outcome = "connection_error"
            raise MarketFailure(
                "market_unavailable",
                "Market source is unavailable",
                503,
            ) from error
        except (ValueError, TypeError) as error:
            outcome = "invalid_response"
            raise MarketFailure(
                "market_invalid_response",
                "Invalid market response",
            ) from error
        except MarketFailure as error:
            outcome = error.code
            raise
        finally:
            if acquired:
                self.slots.release()
            logger.debug(
                "Market provider={} outcome={} duration_ms={:.0f}",
                provider,
                outcome,
                (time.monotonic() - started) * 1000,
            )


def retry_after(value: str | None) -> int:
    """Read delta-seconds or an HTTP date without trusting malformed headers."""
    if value is None:
        return 0
    try:
        return max(0, math.ceil(float(value)))
    except (ValueError, OverflowError):
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=UTC)
            return max(
                0, math.ceil((date - datetime.now(UTC)).total_seconds())
            )
        except (ValueError, TypeError, OverflowError):
            return 0
