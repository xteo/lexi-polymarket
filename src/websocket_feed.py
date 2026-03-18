"""Real-time WebSocket market data feed.

Subscribes to Polymarket WebSocket for live price updates,
order book changes, and trade notifications.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/"


class Channel(str, Enum):
    MARKET = "market"
    BOOK = "book"
    TRADES = "trades"
    TICKER = "ticker"
    USER = "user"


@dataclass
class WSMessage:
    """Parsed WebSocket message."""

    channel: str
    event: str
    data: dict[str, Any]
    timestamp: str | None = None


MessageHandler = Callable[[WSMessage], Any]


class WebSocketFeed:
    """Manages WebSocket connections to Polymarket."""

    def __init__(self) -> None:
        self._ws: ClientConnection | None = None
        self._handlers: dict[str, list[MessageHandler]] = {}
        self._subscriptions: list[dict[str, Any]] = []
        self._running = False
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0

    def on(self, channel: str, handler: MessageHandler) -> None:
        """Register a handler for a channel."""
        if channel not in self._handlers:
            self._handlers[channel] = []
        self._handlers[channel].append(handler)

    def subscribe_market(self, token_id: str) -> None:
        """Subscribe to market-level updates for a token."""
        self._subscriptions.append({
            "type": "subscribe",
            "channel": Channel.MARKET.value,
            "assets_ids": [token_id],
        })

    def subscribe_book(self, token_id: str) -> None:
        """Subscribe to order book updates for a token."""
        self._subscriptions.append({
            "type": "subscribe",
            "channel": Channel.BOOK.value,
            "assets_ids": [token_id],
        })

    def subscribe_trades(self, token_id: str) -> None:
        """Subscribe to trade notifications for a token."""
        self._subscriptions.append({
            "type": "subscribe",
            "channel": Channel.TRADES.value,
            "assets_ids": [token_id],
        })

    def subscribe_ticker(self, token_id: str) -> None:
        """Subscribe to ticker updates (last price, volume)."""
        self._subscriptions.append({
            "type": "subscribe",
            "channel": Channel.TICKER.value,
            "assets_ids": [token_id],
        })

    async def _send_subscriptions(self) -> None:
        """Send all pending subscriptions."""
        if not self._ws:
            return
        for sub in self._subscriptions:
            await self._ws.send(json.dumps(sub))
            logger.debug("Sent subscription: %s", sub)

    async def _dispatch(self, raw: str) -> None:
        """Parse and dispatch a WebSocket message to handlers."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Failed to parse WS message: %s", raw[:200])
            return

        # Handle different message formats
        channel = data.get("channel", data.get("type", "unknown"))
        event = data.get("event", data.get("type", "message"))

        msg = WSMessage(
            channel=channel,
            event=event,
            data=data.get("data", data),
            timestamp=data.get("timestamp"),
        )

        handlers = self._handlers.get(channel, []) + self._handlers.get("*", [])
        for handler in handlers:
            try:
                result = handler(msg)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error("Handler error on channel %s: %s", channel, e)

    async def connect(self) -> None:
        """Connect to the WebSocket and start receiving messages."""
        self._running = True
        delay = self._reconnect_delay

        while self._running:
            try:
                logger.info("Connecting to Polymarket WebSocket...")
                async with websockets.connect(WS_URL) as ws:
                    self._ws = ws
                    delay = self._reconnect_delay  # Reset on successful connect
                    logger.info("WebSocket connected")

                    await self._send_subscriptions()

                    async for message in ws:
                        if not self._running:
                            break
                        await self._dispatch(str(message))

            except websockets.ConnectionClosed as e:
                logger.warning("WebSocket closed: %s", e)
            except Exception as e:
                logger.error("WebSocket error: %s", e)

            if self._running:
                logger.info("Reconnecting in %.1fs...", delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._max_reconnect_delay)

        self._ws = None

    async def disconnect(self) -> None:
        """Gracefully disconnect."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("WebSocket disconnected")
