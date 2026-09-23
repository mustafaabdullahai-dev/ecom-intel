"""ecom-intel — AI Ecommerce Consultant CLI.

Run a full 8-agent intelligence pass and export to the knowledge base, or
start the 24/7 APScheduler automation loop.

Usage:
    python main.py --regions "Egypt" "Dubai"          # one full run
    python main.py --regions "USA" --schedule         # run once, then start loop
    python main.py --schedule                         # scheduler only
"""

from __future__ import annotations

import argparse
import logging
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config.settings import settings
from src.scheduler import start_scheduler
from src.schemas import BusinessIntelligence
from src.workflows.orchestrator import Pipeline

console = Console()


def main() -> int:
    parser = argparse.ArgumentParser(prog="ecom-intel",
                                     description="AI Ecommerce Consultant (local LLMs).")
    parser.add_argument("--regions", nargs="+", help="Regions to scan, e.g. 'Egypt' 'Dubai'.")
    parser.add_argument("--schedule", action="store_true",
                        help="Start the 24/7 automation scheduler instead of a single run.")
    parser.add_argument("--serve", action="store_true",
                        help="Serve the FastAPI API instead of running the pipeline.")
    parser.add_argument("--dashboard", action="store_true",
                        help="Launch the Streamlit dashboard instead of running the pipeline.")
    parser.add_argument("--target", type=int, default=settings.DISCOVERY_TARGET,
                        help="Max leads per run.")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
                        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")

    if args.serve:
        import uvicorn

        console.print("[cyan]Serving API at[/cyan] "
                      f"http://{settings.API_HOST}:{settings.API_PORT}")
        uvicorn.run("src.api:app", host=settings.API_HOST, port=settings.API_PORT)
        return 0

    if args.dashboard:
        import subprocess
        import sys

        console.print("[cyan]Launching Streamlit dashboard...[/cyan]")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "src/dashboard.py"])
        return 0

    if args.schedule:
        start_scheduler()
        return 0

    if not args.regions:
        parser.error("--regions is required unless --schedule is used.")

    _print_config(args, settings)
    _confirm(args)

    pipeline = Pipeline()
    console.print("[cyan]Running 8-agent pipeline: discovery -> qualify -> deepdive"
                  " (website/marketing/social/product/sentiment/competitor) -> score"
                  " -> recommend -> store -> report[/cyan]")
    state = pipeline.graph.invoke({"regions": args.regions, "target": args.target})

    _render(state)
    sheets = state.get("records_written", False)
    console.print(
        f"[green]\nAudit report:[/green] {state.get('report_path', '')}\n"
        f"[green]Knowledge base:[/green] "
        f"{'Google Sheets updated' if sheets else 'local JSON (Google Sheets not configured)'}"
    )
    return 0


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _print_config(args, settings) -> None:
    console.print(
        Panel(
            f"Regions: [bold]{', '.join(args.regions)}[/bold]\n"
            f"Discovery target: [bold]{args.target}[/bold]\n"
            f"Sheets export: [bold]{'enabled' if settings.GOOGLE_SHEETS_ID else 'local only'}[/bold]\n"
            f"LLM routing: per-agent open-source models via Ollama",
            title="ecom-intel",
            border_style="cyan",
        )
    )


def _confirm(args) -> None:
    if args.yes:
        return
    console.print("[yellow]Make sure Ollama is running and these models are pulled:[/yellow]")
    for model in ("llama3.3:70b", "qwen2.5:72b", "deepseek-r1:70b"):
        console.print(f"  $ ollama pull {model}")
    proceed = console.input("\nContinue? [y/N] ").strip().lower()
    if proceed != "y":
        console.print("Aborted.")
        sys.exit(1)


def _render(state: dict) -> None:
    intel: list[BusinessIntelligence] = state.get("intelligence", [])
    table = Table(title="AI-Scored Ecommerce Businesses")
    table.add_column("Business", style="cyan")
    table.add_column("Region", style="magenta")
    table.add_column("Priority", style="bold")
    table.add_column("Opportunity", justify="right")
    table.add_column("Health", justify="right")
    table.add_column("Website", style="red", justify="right")
    table.add_column("Top Opportunity", style="green")
    for bi in sorted(intel, key=lambda b: b.scores.ai_opportunity, reverse=True):
        q = bi.qualification
        table.add_row(
            bi.lead.name,
            bi.lead.region,
            (q.priority.value.upper() + "★" if q and q.priority.value == "high" else
             (q.priority.value.upper() if q else "-")),
            f"{bi.scores.ai_opportunity}",
            f"{bi.scores.business_health}",
            f"{bi.scores.website}",
            bi.recommendation_plan.ai_summary[:60] if bi.recommendation_plan else "-",
        )
    console.print(table)

    if intel:
        console.print(Panel(
            "\n".join(
                f"[bold]{i.lead.name}[/bold] — {i.qualification.reason if i.qualification else ''}"
                for i in intel[:5]
            ),
            title="Why we qualify them",
            border_style="green",
        ))


if __name__ == "__main__":
    sys.exit(main())