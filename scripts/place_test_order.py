#!/usr/bin/env python3
"""CLI: Place a small test order on Polymarket.

Usage:
    python scripts/place_test_order.py --token TOKEN_ID --side BUY --amount 1.0
    python scripts/place_test_order.py --token TOKEN_ID --side BUY --price 0.50 --size 2
    python scripts/place_test_order.py --dry-run --token TOKEN_ID --side BUY --amount 1.0
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.panel import Panel

from config.settings import Settings
from src.client import PolymarketClient
from src.trader import OrderResult, Side, Trader

console = Console()


def display_result(result: OrderResult, order_type: str) -> None:
    if result.success:
        style = "green" if result.status != "DRY_RUN" else "yellow"
        console.print(Panel(
            f"[{style}]Order {result.status}[/{style}]\n\n"
            f"  Order ID: {result.order_id or 'N/A'}\n"
            f"  Type: {order_type}\n"
            f"  Response: {result.raw_response}",
            title="Order Result",
        ))
    else:
        console.print(Panel(
            f"[red]Order FAILED[/red]\n\n"
            f"  Error: {result.error}\n"
            f"  Status: {result.status}",
            title="Order Result",
        ))


def main() -> None:
    parser = argparse.ArgumentParser(description="Place a test order on Polymarket")
    parser.add_argument("--token", required=True, help="Token ID to trade")
    parser.add_argument("--side", required=True, choices=["BUY", "SELL"], help="Order side")
    parser.add_argument("--amount", type=float, help="USDC amount (for market orders)")
    parser.add_argument("--price", type=float, help="Limit price (for limit orders)")
    parser.add_argument("--size", type=float, help="Token quantity (for limit orders)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run mode (default: true)")
    parser.add_argument("--live", action="store_true", help="Enable live trading (REAL MONEY)")
    args = parser.parse_args()

    dry_run = not args.live

    # Validate arguments
    is_market_order = args.amount is not None
    is_limit_order = args.price is not None and args.size is not None

    if not is_market_order and not is_limit_order:
        console.print("[red]Specify either --amount (market order) or --price + --size (limit order)[/red]")
        sys.exit(1)

    console.print("\n[bold blue]Polymarket Test Order[/bold blue]\n")

    if dry_run:
        console.print("[yellow]DRY RUN MODE — no real orders will be placed[/yellow]\n")
    else:
        console.print("[red bold]LIVE MODE — this will place a REAL order with REAL money![/red bold]\n")

        # Safety confirmation for live trades
        confirm = input("Type 'YES' to confirm: ")
        if confirm != "YES":
            console.print("[dim]Cancelled.[/dim]")
            return

    try:
        settings = Settings.load()
    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        return

    client = PolymarketClient(settings.wallet, settings.polymarket)
    client.connect()

    trader = Trader(client, dry_run=dry_run)
    side = Side(args.side)

    if is_market_order:
        console.print(f"  Placing market order: {side.value} ${args.amount:.2f}")
        result = trader.place_market_order(
            token_id=args.token,
            side=side,
            amount=args.amount,
        )
        display_result(result, "MARKET (FOK)")

    elif is_limit_order:
        console.print(f"  Placing limit order: {side.value} {args.size:.1f} @ {args.price:.4f}")
        result = trader.place_limit_order(
            token_id=args.token,
            side=side,
            price=args.price,
            size=args.size,
        )
        display_result(result, "LIMIT (GTC)")

    console.print()


if __name__ == "__main__":
    main()
