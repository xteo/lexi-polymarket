# Polymarket Bot Setup Guide

Complete step-by-step guide to get the trading bot running. This covers wallet creation, funding, API setup, and running your first scan.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Create a Polygon Wallet](#2-create-a-polygon-wallet)
3. [Fund Your Wallet](#3-fund-your-wallet)
4. [Polymarket Account Setup](#4-polymarket-account-setup)
5. [Export Your Private Key](#5-export-your-private-key)
6. [Get an Anthropic API Key](#6-get-an-anthropic-api-key)
7. [Configure the Bot](#7-configure-the-bot)
8. [Install & Run](#8-install--run)
9. [Geographic Considerations](#9-geographic-considerations-uk)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

- **Python 3.11+** installed
- **Git** installed
- A web browser
- Some crypto or fiat money to fund the wallet ($50-100 recommended for testing)
- ~10 minutes

---

## 2. Create a Polygon Wallet

The bot needs an **EOA (Externally Owned Account)** wallet — this is a standard crypto wallet where you control the private key. Polymarket also has "Magic wallets" (created when you sign up with email), but those don't work for bot trading.

### Option A: MetaMask (Recommended)

1. Install [MetaMask](https://metamask.io/) browser extension
2. Create a new wallet — **write down your seed phrase and store it safely**
3. Add the Polygon network:
   - Open MetaMask → Settings → Networks → Add Network
   - Network Name: `Polygon Mainnet`
   - RPC URL: `https://polygon-rpc.com`
   - Chain ID: `137`
   - Currency Symbol: `POL`
   - Block Explorer: `https://polygonscan.com`
4. Switch to the Polygon network in MetaMask
5. Note your wallet address (starts with `0x...`)

### Option B: Create via Private Key (Advanced)

If you prefer not to use a browser extension:

```bash
# Install web3 first
pip install web3

# Generate a new wallet
python -c "
from web3 import Web3
acct = Web3().eth.account.create()
print(f'Address:     {acct.address}')
print(f'Private Key: {acct.key.hex()}')
print('SAVE THESE SECURELY!')
"
```

**CRITICAL: Save your private key securely. If you lose it, you lose access to all funds.**

---

## 3. Fund Your Wallet

You need two tokens on Polygon:

| Token | Purpose | Amount Needed |
|-------|---------|---------------|
| **USDC.e** | Trading on Polymarket | $50-100 for testing |
| **POL** (MATIC) | Gas fees for transactions | $1-2 worth (enough for hundreds of txns) |

### Getting USDC.e on Polygon

**Option A: Polymarket's Built-in Bridge (Easiest)**
1. Go to [polymarket.com](https://polymarket.com)
2. Connect your MetaMask wallet
3. Click "Deposit" — Polymarket has a built-in bridge from Ethereum or card purchase
4. Deposit USDC (it auto-bridges to Polygon as USDC.e)

**Option B: Buy on a CEX and Withdraw to Polygon**
1. Buy USDC on Coinbase, Binance, Kraken, etc.
2. Withdraw USDC to your wallet address
3. **Select Polygon network** when withdrawing (NOT Ethereum — much cheaper)
4. The USDC arrives as USDC.e on Polygon

**Option C: Bridge from Ethereum**
1. If you have USDC on Ethereum mainnet
2. Use the [Polygon Bridge](https://portal.polygon.technology/bridge) to bridge USDC → Polygon
3. This converts to USDC.e automatically

### Getting POL for Gas

- If you withdrew from a CEX on Polygon, you may already have POL
- Alternatively: use [Polygon's gas swap](https://wallet.polygon.technology/gas-swap/) to convert a tiny bit of USDC to POL
- You need very little — $1-2 of POL covers thousands of transactions on Polygon

### Verify Your Balance

After funding, check your balance:
```bash
# After bot setup (step 8), you can use:
python scripts/check_balance.py
```

Or check on [Polygonscan](https://polygonscan.com) by searching your wallet address.

---

## 4. Polymarket Account Setup

### Understanding Wallet Modes

Polymarket has two wallet modes:

| Mode | How it works | Bot compatible? |
|------|-------------|-----------------|
| **Email/Magic** | Polymarket creates a wallet for you | ❌ No |
| **EOA (MetaMask)** | You bring your own wallet | ✅ Yes |

### Connect Your Wallet

1. Go to [polymarket.com](https://polymarket.com)
2. Click "Log In" → "Connect Wallet"
3. Select MetaMask (or WalletConnect)
4. Approve the connection
5. You may need to sign a message to verify ownership
6. Your Polymarket account is now linked to your wallet

### Enable Trading

1. Once connected, you need to approve USDC spending
2. Go to any market and click "Buy" — you'll be prompted to approve
3. Approve the USDC allowance (this is a one-time on-chain transaction)
4. The bot will also handle this automatically via the SDK

### API Access

Polymarket's CLOB API doesn't require separate API keys in the traditional sense. Instead:

- **Authentication**: Your wallet's private key signs messages (EIP-712)
- **API credentials**: Derived from your wallet signature (the bot does this automatically)
- **No API key registration needed**: Just your private key

**Rate limits to be aware of:**
- REST API: ~100 requests/minute
- WebSocket: Reasonable usage (no hard published limit)
- Order placement: ~10 orders/second

---

## 5. Export Your Private Key

The bot needs your wallet's private key to sign orders.

### From MetaMask

1. Open MetaMask
2. Click the three dots (⋮) next to your account name
3. Select "Account Details"
4. Click "Show Private Key"
5. Enter your MetaMask password
6. Copy the private key (64 hex characters)

### Security Rules

- **NEVER** share your private key with anyone
- **NEVER** commit it to git (the `.gitignore` already excludes `.env`)
- **NEVER** paste it in a chat, email, or website
- Store it ONLY in the `.env` file on your local machine
- Consider using a dedicated wallet with limited funds for bot trading

---

## 6. Get an Anthropic API Key

The bot uses Claude for AI-powered market analysis.

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in
3. Navigate to API Keys
4. Click "Create Key"
5. Copy the key (starts with `sk-ant-`)
6. Add credit to your account ($5-10 is plenty for testing)

**Cost estimate:** Each market analysis uses ~500-1000 tokens ≈ $0.003-0.01 per analysis.

---

## 7. Configure the Bot

1. Clone the repo (if you haven't already):
   ```bash
   git clone https://github.com/xteo/lexi-polymarket.git
   cd lexi-polymarket
   ```

2. Create your `.env` file from the template:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` with your values:
   ```bash
   # Required
   POLYMARKET_PRIVATE_KEY=your_64_char_hex_key_here
   POLYMARKET_WALLET_ADDRESS=0xYourWalletAddressHere
   ANTHROPIC_API_KEY=sk-ant-your-key-here

   # Optional (defaults are fine for testing)
   LIVE_TRADING=false
   MAX_POSITION_SIZE=50
   MAX_DAILY_LOSS=25
   ```

**Important:** Leave `LIVE_TRADING=false` until you've verified everything works in dry-run mode.

---

## 8. Install & Run

### Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### First Run: Scan Markets (No Wallet Needed)

```bash
# See what's trading on Polymarket right now
python scripts/scan_markets.py

# Filter by volume
python scripts/scan_markets.py --min-volume 10000

# Search for specific topics
python scripts/scan_markets.py --search crypto
```

### Check Your Balance

```bash
python scripts/check_balance.py
```

### Place a Test Order (Dry Run)

```bash
# This won't actually trade — just simulates
python scripts/place_test_order.py \
  --token YOUR_TOKEN_ID \
  --side BUY \
  --amount 1.0 \
  --dry-run
```

### Run the Bot (Dry Run)

```bash
# AI-powered scanning + dry-run trading
python scripts/run_bot.py

# Single cycle (don't loop)
python scripts/run_bot.py --once

# Custom filters
python scripts/run_bot.py --min-volume 5000 --max-markets 5
```

### Go Live (When Ready)

```bash
# Enable live trading in .env
# LIVE_TRADING=true

# Or via CLI flag (requires confirmation)
python scripts/run_bot.py --live
```

---

## 9. Geographic Considerations (UK)

### Good News

Polymarket's primary geographic restriction targets **US-based users**. The UK is generally fine for both:
- ✅ Web UI access (polymarket.com)
- ✅ API access (CLOB, Gamma, Data APIs)

### Things to Know

- **No VPN needed** from the UK for basic access
- **Regulatory landscape**: UK's FCA hasn't specifically targeted Polymarket as of March 2026, but prediction markets exist in a regulatory grey area. This is for personal use, not financial advice.
- **API access is IP-independent**: The CLOB API authenticates via wallet signature, not IP address. Even if web UI access were restricted, API trading would still work.
- **Withdrawal**: You can withdraw USDC from Polymarket back to your wallet at any time, then off-ramp to GBP via any exchange that supports UK customers (Coinbase, Kraken, etc.)

### If You Run Into Geo Issues

1. The API endpoints (`clob.polymarket.com`, `gamma-api.polymarket.com`) are accessible globally
2. Only the web UI (`polymarket.com`) has geo-restrictions, and those target US IPs
3. If needed, a VPN to a non-US location resolves any web UI issues
4. The bot itself only uses API endpoints, so geo-restrictions don't apply

---

## 10. Troubleshooting

### "POLYMARKET_PRIVATE_KEY is required"
→ Make sure you've created a `.env` file (not just `.env.example`) and filled in your private key.

### "Failed to connect" or authentication errors
→ Check your private key is correct (64 hex chars, no `0x` prefix needed — the bot strips it automatically).
→ Make sure your wallet has been used on Polymarket at least once (connect via web UI first).

### "Insufficient balance" on orders
→ Check you have USDC.e on Polygon (not USDC on Ethereum).
→ Make sure you have POL for gas fees.
→ Run `python scripts/check_balance.py` to verify.

### "Rate limited" errors
→ The bot respects rate limits by default. If you see these, increase `SCAN_INTERVAL` in `.env`.

### Claude analysis returning HOLD on everything
→ This is normal for many markets where the price is close to fair.
→ Lower `MIN_SIGNAL_CONFIDENCE` to see more signals (but accept lower quality).
→ Markets with clearer information edges will produce stronger signals.

### WebSocket disconnections
→ The WebSocket feed auto-reconnects with exponential backoff.
→ If persistent, check your internet connection.
→ The bot works fine without WebSocket (uses REST polling).

### Import errors
→ Make sure you're running from the project root: `cd lexi-polymarket`
→ Make sure the virtual environment is activated: `source venv/bin/activate`

---

## Quick Reference

| What | Command |
|------|---------|
| Scan markets | `python scripts/scan_markets.py` |
| Check balance | `python scripts/check_balance.py` |
| Test order (dry) | `python scripts/place_test_order.py --token TOKEN --side BUY --amount 1` |
| Run bot (dry) | `python scripts/run_bot.py` |
| Run bot (live) | `python scripts/run_bot.py --live` |
| Run once | `python scripts/run_bot.py --once` |
