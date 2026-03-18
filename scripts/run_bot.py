#!/usr/bin/env python3
"""CLI: Main bot loop — scan, analyze, signal, trade.

Usage:
    python scripts/run_bot.py                    # Dry run (default)
    python scripts/run_bot.py --live             # Live trading (REAL MONEY)
    python scripts/run_bot.py --once             # Single scan cycle
    python scripts/run_bot.py --min-volume 5000  # Custom filters
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from config.settings import Settings
from src.ai.analyzer import MarketAnalyzer
from src.ai.signals import SignalGenerator
from src.client import PolymarketClient
from src.markets import MarketScanner
from src.positions import PositionTracker
from src.risk import RiskManager
from src.trader import Side, Trader

console = Console()


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


async def run_cycle(
    scanner: MarketScanner,
    signal_gen: SignalGenerator,
    trader: Trader,
    risk_mgr: RiskManager,
    position_tracker: PositionTracker,
    min_volume: float,
    min_liquidity: float,
    max_markets: int,
) -> int:
    """Run one scan-analyze-signal-trade cycle. Returns number of trades."""
    logger = logging.getLogger(__name__)

    # 1. Scan markets
    console.print("\n[bold]Scanning markets...[/bold]")
    raw_markets = await scanner.fetch_active_markets(limit=max_markets * 2)
    markets = scanner.filter_markets(
        raw_markets,
        min_volume=min_volume,
        min_liquidity=min_liquidity,
    )
    console.print(f"  Found {len(markets)} markets matching criteria")

    if not markets:
        return 0

    # 2. Get current portfolio for risk checks
    portfolio = await position_tracker.get_portfolio()

    # 3. Analyze and generate signals
    console.print("[bold]Analyzing markets with Claude...[/bold]")
    trades_placed = 0

    for market in markets[:max_markets]:
        signal = signal_gen.generate_signal(market)

        if not signal.is_actionable:
            continue

        # 4. Risk check
        amount = 10.0  # Default position size, could be calculated
        risk_check = risk_mgr.check_trade(
            amount=amount,
            market_liquidity=market.liquidity,
            portfolio=portfolio,
        )

        if not risk_check.allowed:
            logger.warning("Risk blocked: %s — %s", market.question[:40], risk_check.reason)
            continue

        # 5. Execute trade
        side = Side.BUY if signal.direction == "BUY_YES" else Side.SELL
        token_id = signal.token_id

        if not token_id:
            logger.warning("No token ID for %s, skipping", market.question[:40])
            continue

        result = trader.place_market_order(
            token_id=token_id,
            side=side,
            amount=amount,
        )

        if result.success:
            trades_placed += 1
            console.print(
                f"  [green]{'DRY ' if not trader.is_live else ''}TRADE:[/green] "
                f"{signal.direction} ${amount:.2f} on '{market.question[:40]}' "
                f"(edge={signal.edge:+.2%}, conf={signal.confidence:.0%})"
            )

    return trades_placed


async def main() -> None:
    parser = argparse.ArgumentParser(description="Polymarket AI Trading Bot")
    parser.add_argument("--live", action="store_true", help="Enable live trading")
    parser.add_argument("--once", action="store_true", help="Run a single cycle then exit")
    parser.add_argument("--min-volume", type=float, default=1000, help="Min 24h volume filter")
    parser.add_argument("--min-liquidity", type=float, default=500, help="Min liquidity filter")
    parser.add_argument("--max-markets", type=int, default=10, help="Max markets to analyze per cycle")
    parser.add_argument("--interval", type=int, default=None, help="Override scan interval (seconds)")
    args = parser.parse_args()

    try:
        settings = Settings.load()
    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        console.print("[dim]Make sure your .env file is set up. See .env.example[/dim]")
        sys.exit(1)

    dry_run = not args.live
    setup_logging(settings.bot.log_level)

    # Banner
    mode = "[red bold]LIVE TRADING[/red bold]" if not dry_run else "[yellow]DRY RUN[/yellow]"
    console.print(f"\n[bold blue]Polymarket AI Bot[/bold blue] — {mode}\n")

    if not dry_run:
        console.print("[red]WARNING: Live trading enabled. Real money at risk![/red]")
        confirm = input("Type 'YES' to start live trading: ")
        if confirm != "YES":
            console.print("[dim]Cancelled.[/dim]")
            return

    # Initialize components
    client = PolymarketClient(settings.wallet, settings.polymarket)
    client.connect()

    scanner = MarketScanner(client)
    analyzer = MarketAnalyzer(settings.anthropic)
    signal_gen = SignalGenerator(
        analyzer,
        min_confidence=settings.bot.min_signal_confidence,
    )
    trader = Trader(client, dry_run=dry_run)
    risk_mgr = RiskManager(settings.risk)
    position_tracker = PositionTracker(client, settings.wallet.address)

    interval = args.interval or settings.bot.scan_interval
    running = True

    def handle_shutdown(signum: int, frame: object) -> None:
        nonlocal running
        console.print("\n[yellow]Shutting down gracefully...[/yellow]")
        running = False

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Main loop
    cycle = 0
    while running:
        cycle += 1
        console.rule(f"[bold]Cycle {cycle}[/bold]")

        try:
            trades = await run_cycle(
                scanner=scanner,
                signal_gen=signal_gen,
                trader=trader,
                risk_mgr=risk_mgr,
                position_tracker=position_tracker,
                min_volume=args.min_volume,
                min_liquidity=args.min_liquidity,
                max_markets=args.max_markets,
            )
            console.print(f"\n  Cycle {cycle} complete: {trades} trades placed")
        except Exception as e:
            console.print(f"\n  [red]Cycle {cycle} error: {e}[/red]")
            logging.getLogger(__name__).exception("Cycle error")

        if args.once:
            break

        # Show signal summary
        signals = signal_gen.actionable_signals
        if signals:
            table = Table(title="Actionable Signals This Session")
            table.add_column("Market", max_width=35)
            table.add_column("Direction", width=10)
            table.add_column("Edge", justify="right", width=8)
            table.add_column("Confidence", justify="right", width=10)
            for s in signals[-5:]:  # Last 5
                table.add_row(
                    s.market_question[:35],
                    s.direction,
                    f"{s.edge:+.2%}",
                    f"{s.confidence:.0%}",
                )
            console.print(table)

        console.print(f"\n[dim]Next scan in {interval}s... (Ctrl+C to stop)[/dim]")
        await asyncio.sleep(interval)

    console.print("\n[bold]Bot stopped.[/bold]\n")


if __name__ == "__main__":
    asyncio.run(main())
