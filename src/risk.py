"""Risk management module.

Enforces position limits, exposure caps, and daily loss limits
to prevent catastrophic losses.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from config.settings import RiskConfig
from src.positions import PortfolioSummary

logger = logging.getLogger(__name__)


@dataclass
class RiskCheck:
    """Result of a risk check."""

    allowed: bool
    reason: str
    details: dict[str, float] = field(default_factory=dict)


class RiskManager:
    """Enforces trading risk limits."""

    def __init__(self, config: RiskConfig) -> None:
        self._config = config
        self._daily_loss: float = 0.0
        self._loss_reset_date: str = ""

    def _reset_daily_loss_if_needed(self) -> None:
        """Reset daily loss counter at midnight UTC."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._loss_reset_date != today:
            self._daily_loss = 0.0
            self._loss_reset_date = today
            logger.info("Daily loss counter reset for %s", today)

    def record_loss(self, amount: float) -> None:
        """Record a realized loss (positive number = loss)."""
        self._reset_daily_loss_if_needed()
        self._daily_loss += abs(amount)
        logger.info(
            "Recorded loss: $%.2f (daily total: $%.2f / $%.2f limit)",
            abs(amount), self._daily_loss, self._config.max_daily_loss,
        )

    def check_daily_loss(self) -> RiskCheck:
        """Check if daily loss limit has been reached."""
        self._reset_daily_loss_if_needed()
        remaining = self._config.max_daily_loss - self._daily_loss

        if self._daily_loss >= self._config.max_daily_loss:
            return RiskCheck(
                allowed=False,
                reason=f"Daily loss limit reached: ${self._daily_loss:.2f} / ${self._config.max_daily_loss:.2f}",
                details={"daily_loss": self._daily_loss, "limit": self._config.max_daily_loss},
            )
        return RiskCheck(
            allowed=True,
            reason=f"Daily loss OK: ${self._daily_loss:.2f} / ${self._config.max_daily_loss:.2f} (${remaining:.2f} remaining)",
            details={"daily_loss": self._daily_loss, "remaining": remaining},
        )

    def check_position_size(self, amount: float) -> RiskCheck:
        """Check if a proposed position size is within limits."""
        if amount > self._config.max_position_size:
            return RiskCheck(
                allowed=False,
                reason=f"Position ${amount:.2f} exceeds max ${self._config.max_position_size:.2f}",
                details={"amount": amount, "limit": self._config.max_position_size},
            )
        return RiskCheck(
            allowed=True,
            reason=f"Position size OK: ${amount:.2f} / ${self._config.max_position_size:.2f}",
            details={"amount": amount, "limit": self._config.max_position_size},
        )

    def check_total_exposure(self, portfolio: PortfolioSummary, new_amount: float) -> RiskCheck:
        """Check if adding a new position would exceed total exposure limit."""
        projected = portfolio.total_exposure + new_amount
        if projected > self._config.max_total_exposure:
            return RiskCheck(
                allowed=False,
                reason=f"Total exposure ${projected:.2f} would exceed max ${self._config.max_total_exposure:.2f}",
                details={
                    "current_exposure": portfolio.total_exposure,
                    "new_amount": new_amount,
                    "projected": projected,
                    "limit": self._config.max_total_exposure,
                },
            )
        return RiskCheck(
            allowed=True,
            reason=f"Exposure OK: ${projected:.2f} / ${self._config.max_total_exposure:.2f}",
            details={"projected": projected, "limit": self._config.max_total_exposure},
        )

    def check_liquidity(self, market_liquidity: float) -> RiskCheck:
        """Check if a market has sufficient liquidity."""
        if market_liquidity < self._config.min_liquidity:
            return RiskCheck(
                allowed=False,
                reason=f"Market liquidity ${market_liquidity:.0f} below minimum ${self._config.min_liquidity:.0f}",
                details={"liquidity": market_liquidity, "min": self._config.min_liquidity},
            )
        return RiskCheck(
            allowed=True,
            reason=f"Liquidity OK: ${market_liquidity:.0f}",
            details={"liquidity": market_liquidity},
        )

    def check_trade(
        self,
        amount: float,
        market_liquidity: float,
        portfolio: PortfolioSummary,
    ) -> RiskCheck:
        """Run all risk checks for a proposed trade.

        Returns the first failing check, or a passing check if all pass.
        """
        checks = [
            self.check_daily_loss(),
            self.check_position_size(amount),
            self.check_total_exposure(portfolio, amount),
            self.check_liquidity(market_liquidity),
        ]

        for check in checks:
            if not check.allowed:
                logger.warning("Risk check FAILED: %s", check.reason)
                return check

        logger.info("All risk checks passed for $%.2f trade", amount)
        return RiskCheck(allowed=True, reason="All risk checks passed")
