"""
main.py – CLI entry point for the Institutional Microstructure Intelligence System.

Usage:
    python main.py run --symbol NVDA              # start live analysis loop
    python main.py chat --symbol NVDA             # interactive chatbot mode
    python main.py demo --symbol AAPL --ticks 50  # offline demo with sample feed
    python main.py dashboard                       # launch Streamlit dashboard

Environment:
    Copy .env.example → .env and configure API keys before running with live feeds.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

app = typer.Typer(
    name="microstructure",
    help="Institutional Microstructure Intelligence System — Phase 1",
    add_completion=False,
)
console = Console()


def _print_banner() -> None:
    console.print(Panel(
        Text.from_markup(
            "[bold cyan]Institutional Microstructure Intelligence System[/bold cyan]\n"
            "[dim]Phase 1 – Research Prototype | Paper-Only | Compliance-Aware[/dim]\n"
            "[dim]Evidence first. Risk second. Execution last.[/dim]"
        ),
        border_style="cyan",
    ))


@app.command()
def demo(
    symbol: str = typer.Option("AAPL", "--symbol", "-s", help="Ticker symbol"),
    ticks: int = typer.Option(20, "--ticks", "-t", help="Number of ticks to process"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full feature vector"),
) -> None:
    """Run an offline demonstration using the sample (synthetic) feed."""
    _print_banner()

    from src.data_intake.sample_feed import SampleFeedAdapter
    from src.orchestrator import Orchestrator

    console.print(f"\n[bold]Running demo for [cyan]{symbol}[/cyan] ({ticks} ticks)[/bold]\n")

    feed = SampleFeedAdapter(symbol=symbol, base_price=185.0, interval_ms=0)
    orch = Orchestrator(symbol)

    async def _run():
        tick = 0
        async for snapshot, trades in feed.stream(max_ticks=ticks):
            result = orch.process(snapshot, trades)
            state = orch.latest_state
            features = orch.latest_features

            disp_colour = {
                "paper_trade_approved": "green",
                "watchlist": "yellow",
                "research_approved": "blue",
                "risk_veto": "red",
                "data_insufficient": "yellow",
                "blocked": "red",
                "human_review": "orange1",
                "rejected": "dim",
            }.get(result.disposition, "white")

            console.print(
                f"[dim]Tick {tick+1:3d}[/dim] | "
                f"Mid [bold]${state.mid_price:.2f}[/bold] | "
                f"OBI [{'+' if state.book_imbalance >= 0 else ''}{state.book_imbalance:.3f}] | "
                f"Spread ×{state.spread_multiple:.1f} | "
                f"Regime [italic]{result.dna_regime}[/italic] | "
                f"Footprint [italic]{result.inst_footprint_label}[/italic] ({result.inst_footprint_prob:.0%}) | "
                f"Disposition [{disp_colour}]{result.disposition.replace('_', ' ').upper()}[/{disp_colour}]"
            )
            if verbose and features:
                console.print(
                    f"         Absorption={features.absorption_score:.2f} "
                    f"Accum={features.accumulation_score:.2f} "
                    f"Distrib={features.distribution_score:.2f} "
                    f"InstProb={features.institutional_footprint_prob:.2f} "
                    f"RSI={features.rsi_14:.1f}"
                )
            tick += 1

        orch.close()
        console.print(f"\n[dim]Audit log written to: {__import__('src.config', fromlist=['AUDIT_LOG_DIR']).AUDIT_LOG_DIR}[/dim]")

    asyncio.run(_run())


@app.command()
def chat(
    symbol: str = typer.Option("AAPL", "--symbol", "-s", help="Ticker symbol"),
) -> None:
    """Interactive chatbot research session (offline, sample feed)."""
    _print_banner()

    from src.data_intake.sample_feed import SampleFeedAdapter
    from src.orchestrator import Orchestrator

    feed = SampleFeedAdapter(symbol=symbol, base_price=185.0)
    orch = Orchestrator(symbol)

    # Warm up with 5 ticks so the pipeline has context
    async def _warmup():
        tick = 0
        async for snap, trades in feed.stream(max_ticks=5):
            orch.process(snap, trades)
            tick += 1

    asyncio.run(_warmup())

    console.print(
        f"\n[bold green]Chat session started for [cyan]{symbol}[/cyan].[/bold green] "
        "Type [bold]'exit'[/bold] or [bold]'quit'[/bold] to end.\n"
    )

    while True:
        try:
            user_input = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user_input.lower() in {"exit", "quit", "q"}:
            break
        if not user_input:
            continue

        response = orch.chat(user_input)
        console.print(f"\n[bold cyan]System >[/bold cyan]\n{response.text}\n")

    orch.close()
    console.print("\n[dim]Session ended. Audit log saved.[/dim]")


@app.command()
def dashboard() -> None:
    """Launch the Streamlit research dashboard."""
    _print_banner()
    console.print("\n[bold]Launching Streamlit dashboard…[/bold]")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "src/dashboard/app.py"],
        check=True,
    )


if __name__ == "__main__":
    app()
