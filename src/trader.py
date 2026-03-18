"""Order execution engine.

Handles building, signing, and submitting orders to the Polymarket CLOB.
Supports limit and market orders with various time-in-force options.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from py_clob_client.clob_types import MarketOrderArgs, OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

from src.client import PolymarketClient

logger = logging.getLogger(__name__)


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

    def to_clob(self) -> str:
        return BUY if self == Side.BUY else SELL


class TimeInForce(str, Enum):
    GTC = "GTC"  # Good Till Cancel
    FOK = "FOK"  # Fill or Kill
    GTD = "GTD"  # Good Till Date


@dataclass
class OrderResult:
    """Result of an order submission."""

    success: bool
    order_id: str | None
    status: str
    raw_response: dict[str, Any]
    error: str | None = None


class Trader:
    """Executes trades on Polymarket."""

    def __init__(self, client: PolymarketClient, dry_run: bool = True) -> None:
        self._client = client
        self._dry_run = dry_run

    @property
    def is_live(self) -> bool:
        return not self._dry_run

    def place_market_order(
        self,
        token_id: str,
        side: Side,
        amount: float,
    ) -> OrderResult:
        """Place a market order (Fill or Kill).

        Args:
            token_id: The conditional token to trade.
            side: BUY or SELL.
            amount: Amount in USDC to spend (for BUY) or tokens to sell.
        """
        if amount <= 0:
            return OrderResult(
                success=False, order_id=None, status="REJECTED",
                raw_response={}, error="Amount must be positive",
            )

        logger.info(
            "%s market order: %s $%.2f of %s",
            "DRY RUN" if self._dry_run else "LIVE",
            side.value, amount, token_id[:16] + "...",
        )

        if self._dry_run:
            return OrderResult(
                success=True, order_id="dry-run", status="DRY_RUN",
                raw_response={"dry_run": True, "side": side.value, "amount": amount},
            )

        order_args = MarketOrderArgs(
            token_id=token_id,
            amount=amount,
            side=side.to_clob(),
        )

        try:
            signed = self._client.create_market_order(order_args)
            resp = self._client.post_order(signed, OrderType.FOK)
            order_id = resp.get("orderID", resp.get("id"))
            logger.info("Market order placed: %s", order_id)
            return OrderResult(
                success=True, order_id=order_id,
                status=resp.get("status", "SUBMITTED"), raw_response=resp,
            )
        except Exception as e:
            logger.error("Market order failed: %s", e)
            return OrderResult(
                success=False, order_id=None, status="ERROR",
                raw_response={}, error=str(e),
            )

    def place_limit_order(
        self,
        token_id: str,
        side: Side,
        price: float,
        size: float,
        tif: TimeInForce = TimeInForce.GTC,
        expiration: int | None = None,
    ) -> OrderResult:
        """Place a limit order.

        Args:
            token_id: The conditional token to trade.
            side: BUY or SELL.
            price: Limit price (0.0 - 1.0 for binary markets).
            size: Number of tokens.
            tif: Time-in-force (GTC, FOK, GTD).
            expiration: Unix timestamp for GTD orders.
        """
        if not (0.0 < price < 1.0):
            return OrderResult(
                success=False, order_id=None, status="REJECTED",
                raw_response={}, error="Price must be between 0 and 1 for binary markets",
            )

        if size <= 0:
            return OrderResult(
                success=False, order_id=None, status="REJECTED",
                raw_response={}, error="Size must be positive",
            )

        logger.info(
            "%s limit order: %s %.1f @ %.4f (%s) %s",
            "DRY RUN" if self._dry_run else "LIVE",
            side.value, size, price, tif.value, token_id[:16] + "...",
        )

        if self._dry_run:
            return OrderResult(
                success=True, order_id="dry-run", status="DRY_RUN",
                raw_response={
                    "dry_run": True, "side": side.value,
                    "price": price, "size": size, "tif": tif.value,
                },
            )

        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=side.to_clob(),
        )

        if tif == TimeInForce.GTD and expiration:
            order_args.expiration = str(expiration)

        order_type = {
            TimeInForce.GTC: OrderType.GTC,
            TimeInForce.FOK: OrderType.FOK,
            TimeInForce.GTD: OrderType.GTD,
        }[tif]

        try:
            signed = self._client.create_limit_order(order_args)
            resp = self._client.post_order(signed, order_type)
            order_id = resp.get("orderID", resp.get("id"))
            logger.info("Limit order placed: %s", order_id)
            return OrderResult(
                success=True, order_id=order_id,
                status=resp.get("status", "SUBMITTED"), raw_response=resp,
            )
        except Exception as e:
            logger.error("Limit order failed: %s", e)
            return OrderResult(
                success=False, order_id=None, status="ERROR",
                raw_response={}, error=str(e),
            )

    def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel an open order."""
        logger.info("Cancelling order %s", order_id)

        if self._dry_run:
            return OrderResult(
                success=True, order_id=order_id, status="DRY_CANCELLED",
                raw_response={"dry_run": True},
            )

        try:
            resp = self._client.cancel_order(order_id)
            return OrderResult(
                success=True, order_id=order_id, status="CANCELLED",
                raw_response=resp,
            )
        except Exception as e:
            logger.error("Cancel failed: %s", e)
            return OrderResult(
                success=False, order_id=order_id, status="ERROR",
                raw_response={}, error=str(e),
            )

    def cancel_all(self) -> OrderResult:
        """Cancel all open orders."""
        logger.info("Cancelling all orders")

        if self._dry_run:
            return OrderResult(
                success=True, order_id=None, status="DRY_CANCELLED_ALL",
                raw_response={"dry_run": True},
            )

        try:
            resp = self._client.cancel_all_orders()
            return OrderResult(
                success=True, order_id=None, status="CANCELLED_ALL",
                raw_response=resp,
            )
        except Exception as e:
            logger.error("Cancel all failed: %s", e)
            return OrderResult(
                success=False, order_id=None, status="ERROR",
                raw_response={}, error=str(e),
            )

    def get_open_orders(self, market: str | None = None) -> list[dict[str, Any]]:
        """Get open orders, optionally filtered by market."""
        kwargs: dict[str, Any] = {}
        if market:
            kwargs["market"] = market
        return self._client.get_orders(**kwargs)
