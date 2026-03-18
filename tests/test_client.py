"""Tests for the Polymarket client wrapper."""

from unittest.mock import MagicMock, patch

import pytest

from config.settings import PolymarketConfig, WalletConfig
from src.client import PolymarketClient


@pytest.fixture
def wallet() -> WalletConfig:
    return WalletConfig(
        private_key="a" * 64,
        address="0x" + "a" * 40,
    )


@pytest.fixture
def config() -> PolymarketConfig:
    return PolymarketConfig(
        host="https://clob.polymarket.com",
        chain_id=137,
    )


@pytest.fixture
def client(wallet: WalletConfig, config: PolymarketConfig) -> PolymarketClient:
    return PolymarketClient(wallet, config)


class TestPolymarketClient:
    def test_init(self, client: PolymarketClient) -> None:
        """Client initializes without connecting."""
        assert client._client is None
        assert client._creds is None

    @patch("src.client.ClobClient")
    def test_connect(
        self, mock_clob_cls: MagicMock, client: PolymarketClient
    ) -> None:
        """Client connects and derives API credentials."""
        mock_instance = MagicMock()
        mock_clob_cls.return_value = mock_instance
        mock_instance.create_or_derive_api_creds.return_value = MagicMock()

        client.connect()

        mock_clob_cls.assert_called_once()
        mock_instance.create_or_derive_api_creds.assert_called_once()
        mock_instance.set_api_creds.assert_called_once()

    @patch("src.client.ClobClient")
    def test_reconnect_resets_state(
        self, mock_clob_cls: MagicMock, client: PolymarketClient
    ) -> None:
        """Reconnect creates a fresh connection."""
        mock_instance = MagicMock()
        mock_clob_cls.return_value = mock_instance
        mock_instance.create_or_derive_api_creds.return_value = MagicMock()

        client.connect()
        client.reconnect()

        assert mock_clob_cls.call_count == 2

    @patch("src.client.ClobClient")
    def test_get_midpoint(
        self, mock_clob_cls: MagicMock, client: PolymarketClient
    ) -> None:
        """get_midpoint returns a float."""
        mock_instance = MagicMock()
        mock_clob_cls.return_value = mock_instance
        mock_instance.create_or_derive_api_creds.return_value = MagicMock()
        mock_instance.get_midpoint.return_value = "0.65"

        client.connect()
        result = client.get_midpoint("token123")

        assert result == 0.65
        mock_instance.get_midpoint.assert_called_once_with(token_id="token123")

    @patch("src.client.ClobClient")
    def test_lazy_connect(
        self, mock_clob_cls: MagicMock, client: PolymarketClient
    ) -> None:
        """Accessing .client property triggers connect."""
        mock_instance = MagicMock()
        mock_clob_cls.return_value = mock_instance
        mock_instance.create_or_derive_api_creds.return_value = MagicMock()

        _ = client.client  # Access property

        mock_clob_cls.assert_called_once()
