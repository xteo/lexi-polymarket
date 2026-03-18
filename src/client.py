"""Polymarket CLOB client wrapper.

Provides a clean interface around the py-clob-client SDK with
automatic credential derivation, reconnection handling, and logging.
"""

import logging
from typing import Any

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

from config.settings import PolymarketConfig, WalletConfig

logger = logging.getLogger(__name__)


class PolymarketClient:
    """Wrapper around the Polymarket CLOB client for EOA wallets."""

    def __init__(self, wallet: WalletConfig, config: PolymarketConfig) -> None:
        self._wallet = wallet
        self._config = config
        self._client: ClobClient | None = None
        self._creds: ApiCreds | None = None

    @property
    def client(self) -> ClobClient:
        """Get the underlying CLOB client, initializing if needed."""
        if self._client is None:
            self.connect()
        assert self._client is not None
        return self._client

    def connect(self) -> None:
        """Initialize the CLOB client and derive API credentials."""
        logger.info("Connecting to Polymarket CLOB at %s", self._config.host)

        self._client = ClobClient(
            self._config.host,
            key=self._wallet.private_key,
            chain_id=self._config.chain_id,
            signature_type=0,  # EOA mode
            funder=self._wallet.address,
        )

        # Derive or create API credentials from wallet signature
        self._creds = self._client.create_or_derive_api_creds()
        self._client.set_api_creds(self._creds)

        logger.info("Connected and authenticated as %s", self._wallet.address)

    def reconnect(self) -> None:
        """Force reconnection (e.g. after an error)."""
        logger.warning("Reconnecting to Polymarket CLOB...")
        self._client = None
        self._creds = None
        self.connect()

    # ── Market Data ────────────────────────────────────────────────

    def get_markets(self, next_cursor: str = "") -> dict[str, Any]:
        """Fetch a page of active markets."""
        return self.client.get_markets(next_cursor=next_cursor)

    def get_market(self, condition_id: str) -> dict[str, Any]:
        """Fetch a single market by condition ID."""
        return self.client.get_market(condition_id=condition_id)

    def get_order_book(self, token_id: str) -> dict[str, Any]:
        """Get the order book for a specific token."""
        return self.client.get_order_book(token_id=token_id)

    def get_midpoint(self, token_id: str) -> float:
        """Get the midpoint price for a token."""
        mid = self.client.get_midpoint(token_id=token_id)
        return float(mid)

    def get_price(self, token_id: str, side: str) -> float:
        """Get the best price for a token on a given side (BUY/SELL)."""
        price = self.client.get_price(token_id=token_id, side=side)
        return float(price)

    # ── Orders ─────────────────────────────────────────────────────

    def post_order(self, signed_order: Any, order_type: Any) -> dict[str, Any]:
        """Submit a signed order to the CLOB."""
        return self.client.post_order(signed_order, order_type)

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an open order."""
        return self.client.cancel(order_id=order_id)

    def cancel_all_orders(self) -> dict[str, Any]:
        """Cancel all open orders."""
        return self.client.cancel_all()

    def get_orders(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Get open orders, optionally filtered."""
        return self.client.get_orders(**kwargs)

    # ── Account ────────────────────────────────────────────────────

    def get_balance_allowance(self, asset_type: int = 0) -> dict[str, Any]:
        """Get USDC balance and allowance.

        asset_type: 0 = USDC collateral, 1 = conditional tokens
        """
        return self.client.get_balance_allowance(asset_type=asset_type)

    # ── Order Building ─────────────────────────────────────────────

    def create_market_order(self, order_args: Any) -> Any:
        """Build and sign a market order."""
        return self.client.create_market_order(order_args)

    def create_limit_order(self, order_args: Any) -> Any:
        """Build and sign a limit order."""
        return self.client.create_order(order_args)
