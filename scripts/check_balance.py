#!/usr/bin/env python3
"""CLI: Check wallet USDC balance and open positions.

Usage:
    python scripts/check_balance.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table

from config.settings import Settings
from src.client import PolymarketClient
from src.positions import PositionTracker

console = Console()


async def main() -> None:
    console.print("\n[bold blue]Polymarket Wallet Status[/bold blue]\n")

    try:
        settings = Settings.load()
    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        console.print("[dim]Make sure your .env file is set up correctly.[/dim]")
        return

    # Connect to Polymarket
    client = PolymarketClient(settings.wallet, settings.polymarket)
    try:
        client.connect()
    except Exception as e:
        console.print(f"[red]Failed to connect: {e}[/red]")
        return

    # Get balance
    console.print(f"[dim]Wallet:[/dim] {settings.wallet.address}\n")

    try:
        balance = client.get_balance_allowance(asset_type=0)
        usdc_balance = float(balance.get("balance", 0)) / 1e6  # USDC has 6 decimals
        allowance = float(balance.get("allowance", 0)) / 1e6
        console.print(f"  USDC Balance:   [green]${usdc_balance:,.2f}[/green]")
        console.print(f"  USDC Allowance: [blue]${allowance:,.2f}[/blue]")
    except Exception as e:
        console.print(f"  [yellow]Could not fetch balance: {e}[/yellow]")

    # Get positions
    console.print()
    tracker = PositionTracker(client, settings.wallet.address)

    try:
        portfolio = await tracker.get_portfolio()

        if not portfolio.positions:
            console.print("[dim]No open positions.[/dim]")
        else:
            table = Table(title=f"Open Positions ({portfolio.position_count})")
            table.add_column("Market", style="bold", max_width=40)
            table.add_column("Outcome", style="cyan", width=8)
            table.add_column("Size", justify="right", width=8)
            table.add_column("Avg Price", justify="right", width=10)
            table.add_column("Current", justify="right", width=10)
            table.add_column("P&L", justify="right", width=10)
            table.add_column("P&L %", justify="right", width=8)

            for p in portfolio.positions:
                pnl_style = "green" if p.unrealized_pnl >= 0 else "red"
                table.add_row(
                    p.market_question[:40],
                    p.outcome,
                    f"{p.size:.1f}",
                    f"${p.avg_price:.4f}",
                    f"${p.current_price:.4f}",
                    f"[{pnl_style}]${p.unrealized_pnl:+.2f}[/{pnl_style}]",
                    f"[{pnl_style}]{p.pnl_percent:+.1f}%[/{pnl_style}]",
                )

            console.print(table)
            console.print()
            console.print(f"  Total Invested:      ${portfolio.total_invested:,.2f}")
            console.print(f"  Total Market Value:  ${portfolio.total_market_value:,.2f}")

            pnl_style = "green" if portfolio.total_unrealized_pnl >= 0 else "red"
            console.print(
                f"  Unrealized P&L:      [{pnl_style}]${portfolio.total_unrealized_pnl:+,.2f}[/{pnl_style}]"
            )

    except Exception as e:
        console.print(f"[yellow]Could not fetch positions: {e}[/yellow]")

    console.print()


if __name__ == "__main__":
    asyncio.run(main())
