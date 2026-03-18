"""Position tracking and P&L calculation.

Tracks current positions, calculates unrealized P&L,
and provides position sizing utilities.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import aiohttp

from src.client import PolymarketClient

logger = logging.getLogger(__name__)

DATA_API = "https://data-api.polymarket.com"


@dataclass
class Position:
    """A single market position."""

    token_id: str
    market_question: str
    outcome: str
    size: float
    avg_price: float
    current_price: float
    unrealized_pnl: float
    side: str  # LONG or SHORT

    @property
    def market_value(self) -> float:
        return self.size * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.size * self.avg_price

    @property
    def pnl_percent(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100


@dataclass
class PortfolioSummary:
    """Aggregate portfolio metrics."""

    positions: list[Position]
    total_invested: float = 0.0
    total_market_value: float = 0.0
    total_unrealized_pnl: float = 0.0
    realized_pnl_today: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def position_count(self) -> int:
        return len(self.positions)

    @property
    def total_exposure(self) -> float:
        return sum(abs(p.market_value) for p in self.positions)


class PositionTracker:
    """Tracks positions and calculates P&L."""

    def __init__(self, client: PolymarketClient, wallet_address: str) -> None:
        self._client = client
        self._wallet = wallet_address
        self._realized_pnl: float = 0.0

    async def fetch_positions(self) -> list[dict[str, Any]]:
        """Fetch current positions from the Data API."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{DATA_API}/positions",
                params={"user": self._wallet},
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                logger.info("Fetched %d positions", len(data))
                return data

    async def get_portfolio(self) -> PortfolioSummary:
        """Build a complete portfolio summary with current prices."""
        raw_positions = await self.fetch_positions()
        positions: list[Position] = []
        total_invested = 0.0
        total_value = 0.0
        total_pnl = 0.0

        for raw in raw_positions:
            size = float(raw.get("size", 0))
            if size == 0:
                continue

            token_id = raw.get("asset", raw.get("token_id", ""))
            avg_price = float(raw.get("avgPrice", raw.get("avg_price", 0)))

            # Get current price from CLOB
            try:
                current_price = self._client.get_midpoint(token_id)
            except Exception:
                current_price = avg_price  # Fallback

            cost = size * avg_price
            value = size * current_price
            pnl = value - cost

            position = Position(
                token_id=token_id,
                market_question=raw.get("title", raw.get("question", "Unknown")),
                outcome=raw.get("outcome", "Unknown"),
                size=size,
                avg_price=avg_price,
                current_price=current_price,
                unrealized_pnl=pnl,
                side="LONG" if size > 0 else "SHORT",
            )
            positions.append(position)
            total_invested += cost
            total_value += value
            total_pnl += pnl

        return PortfolioSummary(
            positions=positions,
            total_invested=total_invested,
            total_market_value=total_value,
            total_unrealized_pnl=total_pnl,
            realized_pnl_today=self._realized_pnl,
        )

    def record_realized_pnl(self, amount: float) -> None:
        """Record realized P&L from a closed position."""
        self._realized_pnl += amount
        logger.info("Realized P&L: $%.2f (total today: $%.2f)", amount, self._realized_pnl)

    @staticmethod
    def calculate_position_size(
        balance: float,
        risk_per_trade: float,
        price: float,
        max_size: float,
    ) -> float:
        """Calculate optimal position size.

        Args:
            balance: Available USDC balance.
            risk_per_trade: Fraction of balance to risk (0.0 - 1.0).
            price: Entry price.
            max_size: Maximum position size in USDC.

        Returns:
            Position size in number of tokens.
        """
        risk_amount = balance * risk_per_trade
        size_by_risk = risk_amount / price if price > 0 else 0
        size_by_max = max_size / price if price > 0 else 0
        return min(size_by_risk, size_by_max)
