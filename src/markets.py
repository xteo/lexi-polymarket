"""Market discovery and scanning.

Fetches active markets from the Gamma API and CLOB,
with filtering by volume, liquidity, and category.
"""

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

from src.client import PolymarketClient

logger = logging.getLogger(__name__)

GAMMA_API = "https://gamma-api.polymarket.com"


@dataclass
class MarketInfo:
    """Parsed market data for display and analysis."""

    condition_id: str
    question: str
    description: str
    category: str
    end_date: str
    tokens: list[dict[str, Any]]
    volume: float
    liquidity: float
    active: bool
    outcomes: list[str]
    outcome_prices: list[float]

    @property
    def midpoint(self) -> float | None:
        """Return the YES token midpoint price if available."""
        if self.outcome_prices:
            return self.outcome_prices[0]
        return None


class MarketScanner:
    """Discovers and filters Polymarket markets."""

    def __init__(self, client: PolymarketClient) -> None:
        self._client = client

    # ── Gamma API (market metadata) ───────────────────────────────

    async def fetch_active_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        order: str = "volume24hr",
        ascending: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch active markets from the Gamma API.

        Args:
            limit: Max markets to return.
            offset: Pagination offset.
            order: Sort field (volume24hr, liquidity, startDate, endDate).
            ascending: Sort direction.
        """
        params = {
            "limit": limit,
            "offset": offset,
            "order": order,
            "ascending": str(ascending).lower(),
            "active": "true",
            "closed": "false",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GAMMA_API}/markets", params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()
                logger.info("Fetched %d markets from Gamma API", len(data))
                return data

    async def fetch_events(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Fetch events (groups of related markets) from Gamma API."""
        params = {
            "limit": limit,
            "offset": offset,
            "active": "true",
            "closed": "false",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GAMMA_API}/events", params=params) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def search_markets(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search markets by keyword."""
        params = {
            "limit": limit,
            "active": "true",
            "closed": "false",
        }

        # Gamma API supports text search via the query parameter
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GAMMA_API}/markets",
                params={**params, "tag": query},
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    # ── CLOB API (order book data) ────────────────────────────────

    def get_order_book(self, token_id: str) -> dict[str, Any]:
        """Get the full order book for a token via CLOB."""
        return self._client.get_order_book(token_id)

    def get_midpoint(self, token_id: str) -> float:
        """Get the midpoint price for a token."""
        return self._client.get_midpoint(token_id)

    # ── Filtering ─────────────────────────────────────────────────

    def parse_market(self, raw: dict[str, Any]) -> MarketInfo:
        """Parse raw Gamma API market data into a MarketInfo."""
        tokens = raw.get("tokens", [])
        outcomes = [t.get("outcome", "?") for t in tokens]
        prices = [float(t.get("price", 0)) for t in tokens]

        return MarketInfo(
            condition_id=raw.get("conditionId", raw.get("condition_id", "")),
            question=raw.get("question", ""),
            description=raw.get("description", ""),
            category=raw.get("category", ""),
            end_date=raw.get("endDate", raw.get("end_date_iso", "")),
            tokens=tokens,
            volume=float(raw.get("volume", raw.get("volume24hr", 0)) or 0),
            liquidity=float(raw.get("liquidity", 0) or 0),
            active=raw.get("active", True),
            outcomes=outcomes,
            outcome_prices=prices,
        )

    def filter_markets(
        self,
        markets: list[dict[str, Any]],
        min_volume: float = 0,
        min_liquidity: float = 0,
        category: str | None = None,
    ) -> list[MarketInfo]:
        """Parse and filter markets by volume, liquidity, and category."""
        results: list[MarketInfo] = []
        for raw in markets:
            info = self.parse_market(raw)
            if info.volume < min_volume:
                continue
            if info.liquidity < min_liquidity:
                continue
            if category and info.category.lower() != category.lower():
                continue
            results.append(info)
        return results
