"""Click CLI entry points for Dendrite."""

from __future__ import annotations

import json
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
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON")
@click.pass_context
def add(ctx: click.Context, content: str, title: str | None, as_json: bool) -> None:
    """Add a new neuron (note) to the network."""
    d = get_dendrite(ctx)
    try:
        neuron = d.add(content, title=title)
        synapses = d.storage.get_synapses_for_neuron(neuron.id)
        n_synapses = len(synapses)

        if as_json:
            print(json.dumps({
                "id": neuron.id,
                "title": neuron.display_title(),
                "content": neuron.content,
                "concepts": neuron.concepts,
                "connections_created": n_synapses,
            }))
        else:
            console.print()
            panel = display.render_neuron(neuron, synapses)
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
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON")
@click.pass_context
def list_neurons(ctx: click.Context, as_json: bool) -> None:
    """List all neurons in the network."""
    d = get_dendrite(ctx)
    try:
        neurons = d.get_all_neurons()
        synapses = d.get_all_synapses()

        if as_json:
            # Build a connection count per neuron
            conn_count: dict[str, int] = {}
            for s in synapses:
                conn_count[s.source_id] = conn_count.get(s.source_id, 0) + 1
                conn_count[s.target_id] = conn_count.get(s.target_id, 0) + 1

            result = []
            for n in neurons:
                result.append({
                    "id": n.id,
                    "title": n.display_title(),
                    "content": n.content,
                    "concepts": n.concepts,
                    "access_count": n.access_count,
                    "connections": conn_count.get(n.id, 0),
                })
            print(json.dumps(result))
        else:
            display.render_neuron_list(neurons, synapses)
    finally:
        d.close()


# ---------------------------------------------------------------------------
# dendrite show
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("neuron_id")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON")
@click.pass_context
def show(ctx: click.Context, neuron_id: str, as_json: bool) -> None:
    """Show a single neuron with its connections."""
    d = get_dendrite(ctx)
    try:
        neuron = d.get_neuron(neuron_id)
        if neuron is None:
            if as_json:
                print(json.dumps({"error": f"Neuron '{neuron_id}' not found."}))
                sys.exit(1)
            console.print(f"[red]Neuron '{neuron_id}' not found.[/red]")
            sys.exit(1)
        synapses = d.storage.get_synapses_for_neuron(neuron_id)

        if as_json:
            connections = []
            for s in sorted(synapses, key=lambda x: -x.weight):
                neighbor_id = s.target_id if s.source_id == neuron_id else s.source_id
                neighbor = d.storage.get_neuron(neighbor_id, increment_access=False)
                connections.append({
                    "target_id": neighbor_id,
                    "target_title": neighbor.display_title() if neighbor else neighbor_id,
                    "weight": round(s.weight, 4),
                })
            print(json.dumps({
                "id": neuron.id,
                "title": neuron.display_title(),
                "content": neuron.content,
                "concepts": neuron.concepts,
                "access_count": neuron.access_count,
                "connections": connections,
            }))
        else:
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
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON")
@click.pass_context
def ask(ctx: click.Context, query: str, top: int, depth: int, threshold: float, as_json: bool) -> None:
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

        if as_json:
            output = []
            for rank, (seed, activation) in enumerate(results, start=1):
                neuron = neurons_by_id.get(seed.neuron_id)
                activation_path = []
                for a in activation:
                    n = neurons_by_id.get(a.neuron_id)
                    if n:
                        activation_path.append(n.display_title())
                output.append({
                    "rank": rank,
                    "id": seed.neuron_id,
                    "title": neuron.display_title() if neuron else seed.neuron_id,
                    "confidence": round(seed.score, 4),
                    "content": neuron.content if neuron else "",
                    "concepts": neuron.concepts if neuron else [],
                    "activation_path": activation_path,
                })
            print(json.dumps(output))
        else:
            display.render_ask_results(results, neurons_by_id, query)
    finally:
        d.close()


# ---------------------------------------------------------------------------
# dendrite explore
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("concept")
@click.option("--depth", "-d", default=3, help="How many hops to follow.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON")
@click.pass_context
def explore(ctx: click.Context, concept: str, depth: int, as_json: bool) -> None:
    """Explore the network from a concept, following synaptic paths."""
    d = get_dendrite(ctx)
    try:
        net_map = d.explore(concept, depth=depth)

        if as_json:
            print(json.dumps({
                "concept": concept,
                "neurons": [{"id": n.id, "title": n.display_title()} for n in net_map.neurons],
                "synapses": [
                    {
                        "source_id": s.source_id,
                        "target_id": s.target_id,
                        "weight": round(s.weight, 4),
                    }
                    for s in net_map.synapses
                ],
            }))
            return

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
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON")
@click.pass_context
def graph(ctx: click.Context, max_nodes: int, as_json: bool) -> None:
    """Show ASCII knowledge graph of the entire network."""
    d = get_dendrite(ctx)
    try:
        neurons = d.get_all_neurons()
        synapses = d.get_all_synapses()

        if as_json:
            # Build degree map
            degree: dict[str, int] = {}
            for s in synapses:
                degree[s.source_id] = degree.get(s.source_id, 0) + 1
                degree[s.target_id] = degree.get(s.target_id, 0) + 1

            print(json.dumps({
                "neurons": [
                    {"id": n.id, "title": n.display_title(), "degree": degree.get(n.id, 0)}
                    for n in neurons
                ],
                "synapses": [
                    {
                        "source_id": s.source_id,
                        "target_id": s.target_id,
                        "source_title": next((n.display_title() for n in neurons if n.id == s.source_id), s.source_id),
                        "target_title": next((n.display_title() for n in neurons if n.id == s.target_id), s.target_id),
                        "weight": round(s.weight, 4),
                    }
                    for s in synapses
                ],
            }))
        else:
            display.render_graph(neurons, synapses, max_neurons=max_nodes)
    finally:
        d.close()


# ---------------------------------------------------------------------------
# dendrite stats
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON")
@click.pass_context
def stats(ctx: click.Context, as_json: bool) -> None:
    """Show network statistics."""
    d = get_dendrite(ctx)
    try:
        s = d.stats()
        if as_json:
            top_concepts = sorted(s.concept_distribution.items(), key=lambda x: -x[1])[:10]
            print(json.dumps({
                "neuron_count": s.neuron_count,
                "synapse_count": s.synapse_count,
                "avg_degree": round(s.avg_degree, 4),
                "most_connected": [
                    {"id": neuron.id, "title": neuron.display_title(), "connections": deg}
                    for neuron, deg in s.most_connected
                ],
                "top_concepts": [[concept, count] for concept, count in top_concepts],
            }))
        else:
            display.render_stats(s)
    finally:
        d.close()


# ---------------------------------------------------------------------------
# dendrite consolidate
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--decay-days", default=0.0, help="Apply N days of decay before consolidating.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON")
@click.pass_context
def consolidate(ctx: click.Context, decay_days: float, as_json: bool) -> None:
    """Run consolidation to strengthen frequently traversed connections."""
    d = get_dendrite(ctx)
    try:
        n_decayed = 0
        if decay_days > 0:
            n_decayed = d.run_decay(days=decay_days)
            if not as_json:
                console.print(f"[dim]Decay applied to {n_decayed} synapses ({decay_days} days).[/dim]")
        n_boosted = d.run_consolidation()
        if as_json:
            print(json.dumps({
                "synapses_consolidated": n_boosted,
                "synapses_decayed": n_decayed,
            }))
        else:
            console.print(f"[green]Consolidation complete.[/green] {n_boosted} synapses strengthened.")
    finally:
        d.close()
