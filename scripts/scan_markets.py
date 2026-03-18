#!/usr/bin/env python3
"""CLI: Scan and display active Polymarket markets.

Usage:
    python scripts/scan_markets.py [--limit N] [--min-volume N] [--category CAT] [--search QUERY]
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table

from config.settings import PolymarketConfig, Settings, WalletConfig
from src.client import PolymarketClient
from src.markets import MarketScanner

console = Console()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Scan Polymarket markets")
    parser.add_argument("--limit", type=int, default=25, help="Number of markets to fetch")
    parser.add_argument("--min-volume", type=float, default=0, help="Minimum 24h volume")
    parser.add_argument("--min-liquidity", type=float, default=0, help="Minimum liquidity")
    parser.add_argument("--category", type=str, default=None, help="Filter by category")
    parser.add_argument("--search", type=str, default=None, help="Search by keyword")
    args = parser.parse_args()

    # Use partial settings (no wallet/API key needed for read-only)
    settings = Settings.load_partial()

    # Create a minimal client (market scanning uses Gamma API directly)
    wallet = WalletConfig(private_key="dummy", address="0x0")
    pm_config = PolymarketConfig.from_env()
    client = PolymarketClient(wallet, pm_config)
    scanner = MarketScanner(client)

    console.print("\n[bold blue]Polymarket Market Scanner[/bold blue]\n")

    # Fetch markets
    if args.search:
        console.print(f"Searching for: [yellow]{args.search}[/yellow]\n")
        raw_markets = await scanner.search_markets(args.search, limit=args.limit)
    else:
        raw_markets = await scanner.fetch_active_markets(limit=args.limit)

    # Filter
    markets = scanner.filter_markets(
        raw_markets,
        min_volume=args.min_volume,
        min_liquidity=args.min_liquidity,
        category=args.category,
    )

    if not markets:
        console.print("[yellow]No markets found matching your criteria.[/yellow]")
        return

    # Display
    table = Table(title=f"Active Markets ({len(markets)} found)")
    table.add_column("#", style="dim", width=4)
    table.add_column("Question", style="bold", max_width=50)
    table.add_column("Category", style="cyan", width=12)
    table.add_column("YES Price", justify="right", style="green", width=10)
    table.add_column("Volume", justify="right", style="yellow", width=12)
    table.add_column("Liquidity", justify="right", style="blue", width=12)
    table.add_column("End Date", style="dim", width=12)

    for i, m in enumerate(markets, 1):
        yes_price = f"{m.outcome_prices[0]:.2%}" if m.outcome_prices else "N/A"
        volume = f"${m.volume:,.0f}" if m.volume else "N/A"
        liquidity = f"${m.liquidity:,.0f}" if m.liquidity else "N/A"
        end_date = m.end_date[:10] if m.end_date else "N/A"

        table.add_row(
            str(i),
            m.question[:50],
            m.category or "—",
            yes_price,
            volume,
            liquidity,
            end_date,
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(markets)} markets sorted by 24h volume[/dim]\n")


if __name__ == "__main__":
    asyncio.run(main())
