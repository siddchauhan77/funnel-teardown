"""
FunnelTeardown AI — CLI Entry Point
Usage: python3 teardown.py "Brand Name" [--founder "Name"] [--url "site.com"] [--from-cache] [--agent N]
"""
import argparse
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # Must run before agent imports so API keys are in os.environ

from rich.console import Console
from rich.table import Table

from agents.brand_resolver import resolve_brand
from agents.touchpoint_mapper import map_touchpoints
from agents.journey_mapper import map_journey
from report.html_renderer import render_html
from state.teardown_state import TeardownState, slug_for
from utils.cost_tracker import CostTracker

OUTPUT_DIR = Path("output")
console = Console()


def run_teardown(brand_name: str, hints: dict,
                 from_cache: bool = False, start_agent: int = 1) -> None:
    """Run the full teardown pipeline for a brand."""
    start_time = time.time()
    tracker = CostTracker()

    # Load or create state
    state = None
    if from_cache:
        state = TeardownState.load(brand_name)
        if state is None:
            console.print(f"[yellow]No cache found for '{brand_name}'. Starting fresh.[/yellow]")
    if state is None:
        state = TeardownState.new(brand_name, hints=hints)

    # Agent 1: Brand Resolver
    if start_agent <= 1:
        with console.status("[bold blue]Agent 1: Resolving brand...[/bold blue]"):
            resolve_brand(state, tracker)
        state.save()
        cost1 = CostTracker.format_usd(tracker.agent_cost("brand_resolver"))
        console.print(
            f"[green]✓[/green] Brand resolved: {state.funnel_map.brand.name} "
            f"({state.funnel_map.brand.website}) "
            f"[{state.funnel_map.brand.confidence} confidence] "
            f"[dim]{cost1}[/dim]"
        )

    # Agent 2: Touchpoint Mapper
    if start_agent <= 2:
        with console.status("[bold blue]Agent 2: Mapping touchpoints...[/bold blue]"):
            map_touchpoints(state, tracker)
        state.save()
        n_touchpoints = len(state.funnel_map.touchpoints)
        cost2 = CostTracker.format_usd(tracker.agent_cost("touchpoint_mapper"))
        console.print(
            f"[green]✓[/green] Touchpoints found: {n_touchpoints} channels "
            f"[dim]{cost2}[/dim]"
        )

    # Agent 3: Journey & Offers Mapper
    if start_agent <= 3:
        with console.status("[bold blue]Agent 3: Mapping funnel journey (Claude)...[/bold blue]"):
            map_journey(state, tracker)
        n_steps = len(state.funnel_map.journey_steps)
        n_offers = len(state.funnel_map.offers)
        cost3 = CostTracker.format_usd(tracker.agent_cost("journey_mapper"))
        console.print(
            f"[green]✓[/green] Funnel mapped: {n_steps} steps, {n_offers} offers "
            f"[dim]{cost3}[/dim]"
        )

    # Finalize metadata
    duration = time.time() - start_time
    state.funnel_map.run_metadata.timestamp = datetime.now().isoformat()
    state.funnel_map.run_metadata.total_cost_usd = tracker.total_cost()
    state.funnel_map.run_metadata.agent_costs = tracker.agent_costs_dict()
    state.funnel_map.run_metadata.model_used = tracker.models_used_dict()
    state.funnel_map.run_metadata.duration_seconds = duration

    # Write output
    slug = slug_for(brand_name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUTPUT_DIR / f"{slug}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "funnel_map.json"
    json_path.write_text(state.funnel_map.model_dump_json(indent=2), encoding="utf-8")

    html_path = out_dir / "teardown_report.html"
    html_path.write_text(render_html(state.funnel_map), encoding="utf-8")

    # Summary
    console.rule()
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("Total cost:", f"[bold green]{CostTracker.format_usd(tracker.total_cost())}[/bold green]")
    table.add_row("Runtime:", f"{duration:.0f}s")
    table.add_row("Output:", str(out_dir))
    table.add_row("  →", str(json_path.name))
    table.add_row("  →", str(html_path.name))
    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FunnelTeardown AI — reverse-engineer any brand's acquisition funnel"
    )
    parser.add_argument("brand", help='Brand name, e.g. "Athletic Greens"')
    parser.add_argument("--founder", help="Founder name hint")
    parser.add_argument("--url", help="Website URL hint")
    parser.add_argument("--from-cache", action="store_true",
                        help="Load cached state from .tmp/ instead of re-running Agent 1+2")
    parser.add_argument("--agent", type=int, default=1,
                        help="Start from this agent number (1-3). Use with --from-cache.")
    args = parser.parse_args()

    hints: dict = {}
    if args.founder:
        hints["founder"] = args.founder
    if args.url:
        hints["url"] = args.url

    try:
        run_teardown(
            args.brand,
            hints=hints,
            from_cache=args.from_cache,
            start_agent=args.agent
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
