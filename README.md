# Polymarket AI Trading Bot

An AI-powered trading bot for [Polymarket](https://polymarket.com) prediction markets. Uses Claude to analyze markets, identify mispriced outcomes, and execute trades automatically.

## How It Works

```
Scan Markets → AI Analysis (Claude) → Generate Signals → Risk Check → Execute Trades
```

1. **Market Scanner** fetches active markets from the Polymarket Gamma API
2. **AI Analyzer** sends each market to Claude, which estimates fair probabilities
3. **Signal Generator** compares Claude's estimate to the market price — if there's an edge, it generates a BUY/SELL signal
4. **Risk Manager** validates the trade against position limits, exposure caps, and daily loss limits
5. **Trader** executes the order on the Polymarket CLOB (or simulates it in dry-run mode)

## Features

- **Claude-powered analysis** — Uses Anthropic's Claude to assess prediction market probabilities
- **Dry-run mode** — Default mode simulates all trades without risking real money
- **Risk management** — Position limits, exposure caps, daily loss limits, and liquidity checks
- **Real-time data** — WebSocket feed for live price updates and order book changes
- **CLI tools** — Scripts for market scanning, balance checking, and test orders
- **Type-safe** — Full type hints throughout the codebase

## Project Structure

```
├── config/
│   └── settings.py              # Environment-based configuration
├── src/
│   ├── client.py                # Polymarket CLOB client wrapper
│   ├── markets.py               # Market discovery & scanning (Gamma API)
│   ├── trader.py                # Order execution (limit & market orders)
│   ├── positions.py             # Position tracking & P&L
│   ├── risk.py                  # Risk management engine
│   ├── websocket_feed.py        # Real-time WebSocket data
│   └── ai/
│       ├── analyzer.py          # Claude market analysis
│       └── signals.py           # Signal generation
├── scripts/
│   ├── scan_markets.py          # CLI: Browse active markets
│   ├── check_balance.py         # CLI: Wallet & position status
│   ├── place_test_order.py      # CLI: Place a test trade
│   └── run_bot.py               # CLI: Main bot loop
└── tests/
    ├── test_client.py
    └── test_markets.py
```

## Quick Start

```bash
# Clone and install
git clone https://github.com/xteo/lexi-polymarket.git
cd lexi-polymarket
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your private key and API keys

# Scan markets (no wallet needed)
python scripts/scan_markets.py

# Run the bot in dry-run mode
python scripts/run_bot.py --once
```

See **[SETUP.md](SETUP.md)** for the full setup guide including wallet creation, funding, and configuration.

## Configuration

All settings are in `.env` (see `.env.example` for the template):

| Variable | Description | Default |
|----------|-------------|---------|
| `POLYMARKET_PRIVATE_KEY` | Wallet private key | Required |
| `POLYMARKET_WALLET_ADDRESS` | Wallet public address | Required |
| `ANTHROPIC_API_KEY` | Claude API key | Required |
| `LIVE_TRADING` | Enable real trades | `false` |
| `MAX_POSITION_SIZE` | Max per-market position (USDC) | `50` |
| `MAX_TOTAL_EXPOSURE` | Max total exposure (USDC) | `200` |
| `MAX_DAILY_LOSS` | Daily loss limit (USDC) | `25` |
| `MIN_SIGNAL_CONFIDENCE` | Min AI confidence for signals | `0.7` |
| `SCAN_INTERVAL` | Seconds between scan cycles | `60` |

## Safety

- **Dry-run by default** — No real trades unless `LIVE_TRADING=true` or `--live` flag
- **Confirmation required** — Live trading prompts for "YES" confirmation
- **Risk limits** — Hard caps on position size, total exposure, and daily loss
- **Liquidity checks** — Won't trade in thin markets

## Tech Stack

- **Python 3.11+** with asyncio
- **py-clob-client** — Official Polymarket Python SDK
- **anthropic** — Claude API for AI analysis
- **rich** — Beautiful CLI output
- **web3.py** — Blockchain interactions
- **websockets** — Real-time market data

## APIs Used

| API | Base URL | Purpose |
|-----|----------|---------|
| CLOB API | `clob.polymarket.com` | Orders, order book, prices |
| Gamma API | `gamma-api.polymarket.com` | Market metadata, listings |
| Data API | `data-api.polymarket.com` | Positions, trade history |
| WebSocket | `ws-subscriptions-clob.polymarket.com` | Real-time updates |

## License

Private repository. Not for redistribution.
