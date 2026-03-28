"""Click CLI entry points for Dendrite."""

from __future__ import annotations

import os
import sys

import click
from rich.console import Console
from rich.text import Text

from dendrite.core import Dendrite
from dendrite import display

console = Console()

DEFAULT_DB = os.path.expanduser("~/.dendrite.db")


def get_dendrite(ctx: click.Context) -> Dendrite:
    db_path = ctx.obj.get("db_path", DEFAULT_DB)
    return Dendrite(db_path=db_path)


@click.group()
@click.option(
    "--db",
    default=DEFAULT_DB,
    envvar="DENDRITE_DB",
    help="Path to the SQLite database file.",
    show_default=True,
)
@click.pass_context
def cli(ctx: click.Context, db: str) -> None:
    """Dendrite — neural-inspired knowledge synthesis."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db


# ---------------------------------------------------------------------------
# dendrite add
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("content")
@click.option("--title", "-t", default=None, help="Optional title for the neuron.")
@click.pass_context
def add(ctx: click.Context, content: str, title: str | None) -> None:
    """Add a new neuron (note) to the network."""
    d = get_dendrite(ctx)
    try:
        neuron = d.add(content, title=title)
        n_synapses = len(d.storage.get_synapses_for_neuron(neuron.id))

        console.print()
        panel = display.render_neuron(neuron, d.storage.get_synapses_for_neuron(neuron.id))
        console.print(panel)

        if n_synapses:
            console.print(
                f"[dim]  ↳ Created [green]{n_synapses}[/green] synaptic connections[/dim]\n"
            )
        else:
            console.print("[dim]  ↳ No connections yet (first neuron or no similar content)[/dim]\n")
    finally:
        d.close()


# ---------------------------------------------------------------------------
# dendrite list
# ---------------------------------------------------------------------------

@cli.command("list")
@click.pass_context
def list_neurons(ctx: click.Context) -> None:
    """List all neurons in the network."""
    d = get_dendrite(ctx)
    try:
        neurons = d.get_all_neurons()
        synapses = d.get_all_synapses()
        display.render_neuron_list(neurons, synapses)
    finally:
        d.close()


# ---------------------------------------------------------------------------
# dendrite show
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("neuron_id")
@click.pass_context
def show(ctx: click.Context, neuron_id: str) -> None:
    """Show a single neuron with its connections."""
    d = get_dendrite(ctx)
    try:
        neuron = d.get_neuron(neuron_id)
        if neuron is None:
            console.print(f"[red]Neuron '{neuron_id}' not found.[/red]")
            sys.exit(1)
        synapses = d.storage.get_synapses_for_neuron(neuron_id)
        console.print()
        console.print(display.render_neuron(neuron, synapses))

        if synapses:
            console.print("[dim]Connected to:[/dim]")
            for s in sorted(synapses, key=lambda x: -x.weight)[:10]:
                neighbor_id = s.target_id if s.source_id == neuron_id else s.source_id
                neighbor = d.storage.get_neuron(neighbor_id, increment_access=False)
                bar = display._weight_bar(s.weight)
                label = neighbor.display_title()[:50] if neighbor else neighbor_id
                edge_text = Text()
                edge_text.append(f"  {bar} ", style=display._weight_color(s.weight))
                edge_text.append(f"[{neighbor_id}] ", style="dim")
                edge_text.append(label, style="dim white")
                console.print(edge_text)
        console.print()
    finally:
        d.close()


# ---------------------------------------------------------------------------
# dendrite ask
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("query")
@click.option("--top", "-k", default=5, help="Number of top results.")
@click.option("--depth", "-d", default=3, help="Activation spreading depth.")
@click.option("--threshold", "-t", default=0.15, help="Minimum synapse weight for activation.")
@click.pass_context
def ask(ctx: click.Context, query: str, top: int, depth: int, threshold: float) -> None:
    """Ask a question — find and activate relevant neurons."""
    d = get_dendrite(ctx)
    try:
        results = d.ask(query, top_k=top, activation_threshold=threshold, activation_depth=depth)
        all_ids = set()
        for seed, activation in results:
            all_ids.add(seed.neuron_id)
            for a in activation:
                all_ids.add(a.neuron_id)

        neurons_by_id = d.get_neurons_by_id(list(all_ids))
        display.render_ask_results(results, neurons_by_id, query)
    finally:
        d.close()


# ---------------------------------------------------------------------------
# dendrite explore
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("concept")
@click.option("--depth", "-d", default=3, help="How many hops to follow.")
@click.pass_context
def explore(ctx: click.Context, concept: str, depth: int) -> None:
    """Explore the network from a concept, following synaptic paths."""
    d = get_dendrite(ctx)
    try:
        net_map = d.explore(concept, depth=depth)
        if not net_map.neurons:
            console.print(f"[dim]No neurons found containing concept '{concept}'.[/dim]")
            return

        console.print()
        console.rule(Text(f'Exploring: "{concept}"', style="bold magenta"))
        console.print(
            f"\n[dim]Found [green]{len(net_map.neurons)}[/green] neurons within "
            f"{depth} hops, [green]{len(net_map.synapses)}[/green] connections[/dim]\n"
        )
        display.render_graph(net_map.neurons, net_map.synapses)
    finally:
        d.close()


# ---------------------------------------------------------------------------
# dendrite graph
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--max-nodes", default=20, help="Maximum neurons to show.")
@click.pass_context
def graph(ctx: click.Context, max_nodes: int) -> None:
    """Show ASCII knowledge graph of the entire network."""
    d = get_dendrite(ctx)
    try:
        neurons = d.get_all_neurons()
        synapses = d.get_all_synapses()
        display.render_graph(neurons, synapses, max_neurons=max_nodes)
    finally:
        d.close()


# ---------------------------------------------------------------------------
# dendrite stats
# ---------------------------------------------------------------------------

@cli.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """Show network statistics."""
    d = get_dendrite(ctx)
    try:
        s = d.stats()
        display.render_stats(s)
    finally:
        d.close()


# ---------------------------------------------------------------------------
# dendrite consolidate
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--decay-days", default=0.0, help="Apply N days of decay before consolidating.")
@click.pass_context
def consolidate(ctx: click.Context, decay_days: float) -> None:
    """Run consolidation to strengthen frequently traversed connections."""
    d = get_dendrite(ctx)
    try:
        if decay_days > 0:
            n_decayed = d.run_decay(days=decay_days)
            console.print(f"[dim]Decay applied to {n_decayed} synapses ({decay_days} days).[/dim]")
        n_boosted = d.run_consolidation()
        console.print(f"[green]Consolidation complete.[/green] {n_boosted} synapses strengthened.")
    finally:
        d.close()
