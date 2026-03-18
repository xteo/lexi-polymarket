"""Configuration loader for Polymarket bot."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    """Load .env file from project root."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)


_load_env()


@dataclass(frozen=True)
class WalletConfig:
    private_key: str
    address: str

    @classmethod
    def from_env(cls) -> "WalletConfig":
        pk = os.getenv("POLYMARKET_PRIVATE_KEY", "")
        addr = os.getenv("POLYMARKET_WALLET_ADDRESS", "")
        if not pk:
            raise ValueError("POLYMARKET_PRIVATE_KEY is required in .env")
        if not addr:
            raise ValueError("POLYMARKET_WALLET_ADDRESS is required in .env")
        # Normalize private key - strip 0x prefix if present
        if pk.startswith("0x"):
            pk = pk[2:]
        return cls(private_key=pk, address=addr)


@dataclass(frozen=True)
class PolymarketConfig:
    host: str
    chain_id: int

    @classmethod
    def from_env(cls) -> "PolymarketConfig":
        return cls(
            host=os.getenv("POLYMARKET_HOST", "https://clob.polymarket.com"),
            chain_id=int(os.getenv("POLYMARKET_CHAIN_ID", "137")),
        )


@dataclass(frozen=True)
class AnthropicConfig:
    api_key: str
    model: str

    @classmethod
    def from_env(cls) -> "AnthropicConfig":
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY is required in .env")
        return cls(
            api_key=key,
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        )


@dataclass(frozen=True)
class RiskConfig:
    max_position_size: float
    max_total_exposure: float
    max_daily_loss: float
    min_liquidity: float

    @classmethod
    def from_env(cls) -> "RiskConfig":
        return cls(
            max_position_size=float(os.getenv("MAX_POSITION_SIZE", "50")),
            max_total_exposure=float(os.getenv("MAX_TOTAL_EXPOSURE", "200")),
            max_daily_loss=float(os.getenv("MAX_DAILY_LOSS", "25")),
            min_liquidity=float(os.getenv("MIN_LIQUIDITY", "1000")),
        )


@dataclass(frozen=True)
class BotConfig:
    live_trading: bool
    scan_interval: int
    min_signal_confidence: float
    log_level: str

    @classmethod
    def from_env(cls) -> "BotConfig":
        return cls(
            live_trading=os.getenv("LIVE_TRADING", "false").lower() == "true",
            scan_interval=int(os.getenv("SCAN_INTERVAL", "60")),
            min_signal_confidence=float(os.getenv("MIN_SIGNAL_CONFIDENCE", "0.7")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


@dataclass(frozen=True)
class Settings:
    wallet: WalletConfig
    polymarket: PolymarketConfig
    anthropic: AnthropicConfig
    risk: RiskConfig
    bot: BotConfig

    @classmethod
    def load(cls) -> "Settings":
        """Load all settings from environment variables."""
        return cls(
            wallet=WalletConfig.from_env(),
            polymarket=PolymarketConfig.from_env(),
            anthropic=AnthropicConfig.from_env(),
            risk=RiskConfig.from_env(),
            bot=BotConfig.from_env(),
        )

    @classmethod
    def load_partial(cls) -> "Settings":
        """Load settings without requiring all keys (for read-only operations)."""
        wallet = WalletConfig(
            private_key=os.getenv("POLYMARKET_PRIVATE_KEY", ""),
            address=os.getenv("POLYMARKET_WALLET_ADDRESS", ""),
        )
        anthropic = AnthropicConfig(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        )
        return cls(
            wallet=wallet,
            polymarket=PolymarketConfig.from_env(),
            anthropic=anthropic,
            risk=RiskConfig.from_env(),
            bot=BotConfig.from_env(),
        )
