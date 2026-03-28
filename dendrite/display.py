"""Rich-powered terminal display for Dendrite."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich import box

if TYPE_CHECKING:
    from dendrite.core import NetworkMap, NetworkStats
    from dendrite.storage import Neuron, Synapse
    from dendrite.synapse import ActivationResult

console = Console()


def render_neuron(neuron: "Neuron", synapses: list["Synapse"] | None = None) -> Panel:
    """Render a single neuron as a Rich Panel."""
    content = Text()

    # Content block
    content.append(neuron.content + "\n\n", style="white")

    # Concepts row
    if neuron.concepts:
        content.append("Concepts: ", style="dim")
        for i, concept in enumerate(neuron.concepts):
            if i > 0:
                content.append("  ", style="dim")
            content.append(f"#{concept}", style="cyan bold")
        content.append("\n")

    # Stats row
    content.append(
        f"\nCreated: {_fmt_time(neuron.created_at)}  "
        f"Accessed: {neuron.access_count}×",
        style="dim",
    )

    if synapses is not None:
        content.append(f"  Connections: {len(synapses)}", style="dim")

    title = Text()
    title.append(f"[{neuron.id}] ", style="dim")
    title.append(neuron.display_title(), style="bold yellow")

    return Panel(content, title=title, border_style="bright_black")


def render_activation_tree(
    results: list["ActivationResult"],
    neurons_by_id: dict[str, "Neuron"],
) -> Tree:
    """Render the activation spread as a Rich Tree."""
    if not results:
        return Tree(Text("No activations", style="dim"))

    seed = results[0]
    seed_neuron = neurons_by_id.get(seed.neuron_id)
    seed_label = _neuron_label(seed.neuron_id, seed_neuron, seed.score, is_seed=True)
    tree = Tree(seed_label)

    # Group by depth, build parent map
    # We'll track which tree node corresponds to which neuron_id
    nodes: dict[str, Tree] = {seed.neuron_id: tree}

    for result in results[1:]:
        parent_id = result.path[-2] if len(result.path) >= 2 else seed.neuron_id
        parent_node = nodes.get(parent_id, tree)
        neuron = neurons_by_id.get(result.neuron_id)
        label = _neuron_label(result.neuron_id, neuron, result.score)
        child = parent_node.add(label)
        nodes[result.neuron_id] = child

    return tree


def _neuron_label(
    neuron_id: str,
    neuron: "Neuron | None",
    score: float,
    is_seed: bool = False,
) -> Text:
    label = Text()
    label.append(f"[{neuron_id}] ", style="dim")
    if neuron:
        label.append(neuron.display_title()[:50], style="bold yellow" if is_seed else "yellow")
    else:
        label.append(neuron_id, style="dim")
    label.append(f"  score={score:.3f}", style="green" if score > 0.3 else "dim green")
    return label


def render_ask_results(
    results: list[tuple["ActivationResult", list["ActivationResult"]]],
    neurons_by_id: dict[str, "Neuron"],
    query: str,
) -> None:
    """Render the full output of dendrite ask."""
    console.print()
    console.rule(Text(f'Query: "{query}"', style="bold magenta"))
    console.print()

    if not results:
        console.print("[dim]No relevant neurons found.[/dim]")
        return

    for rank, (match, activation_path) in enumerate(results, 1):
        neuron = neurons_by_id.get(match.neuron_id)
        if neuron is None:
            continue

        # Header line
        header = Text()
        header.append(f"#{rank}  ", style="bold dim")
        header.append(f"[{neuron.id}] ", style="dim")
        header.append(neuron.display_title(), style="bold yellow")
        header.append(f"  confidence={match.score:.3f}", style="green bold")
        console.print(header)

        # Concepts
        if neuron.concepts:
            concept_text = Text("   Concepts: ", style="dim")
            for concept in neuron.concepts:
                concept_text.append(f"#{concept} ", style="cyan")
            console.print(concept_text)

        # Content preview
        preview = neuron.content[:200]
        if len(neuron.content) > 200:
            preview += "…"
        console.print(f"   [white]{preview}[/white]")

        # Activation path
        if len(activation_path) > 1:
            path_text = Text("   Activation path: ", style="dim")
            for i, step in enumerate(activation_path):
                if i > 0:
                    path_text.append(" → ", style="dim")
                step_neuron = neurons_by_id.get(step.neuron_id)
                label = step_neuron.display_title()[:30] if step_neuron else step.neuron_id
                path_text.append(label, style="bright_black" if i > 0 else "white")
            console.print(path_text)

        console.print()


def render_graph(
    neurons: list["Neuron"],
    synapses: list["Synapse"],
    max_neurons: int = 20,
) -> None:
    """Render an ASCII adjacency graph of the knowledge network."""
    if not neurons:
        console.print("[dim]No neurons in the network yet.[/dim]")
        return

    # Degree map
    degree: dict[str, int] = {n.id: 0 for n in neurons}
    for s in synapses:
        degree[s.source_id] = degree.get(s.source_id, 0) + 1
        degree[s.target_id] = degree.get(s.target_id, 0) + 1

    # Select top neurons by degree
    sorted_neurons = sorted(neurons, key=lambda n: -degree.get(n.id, 0))
    display_neurons = sorted_neurons[:max_neurons]
    display_ids = {n.id for n in display_neurons}

    # Filter synapses to only those within display set
    display_synapses = [
        s for s in synapses if s.source_id in display_ids and s.target_id in display_ids
    ]

    # Build adjacency dict
    adj: dict[str, list[tuple[str, float]]] = {n.id: [] for n in display_neurons}
    for s in display_synapses:
        adj[s.source_id].append((s.target_id, s.weight))
        adj[s.target_id].append((s.source_id, s.weight))

    console.print()
    console.rule(Text("Knowledge Graph", style="bold cyan"))
    console.print()

    for neuron in display_neurons:
        nid = neuron.id
        title = neuron.display_title()[:40]
        deg = degree.get(nid, 0)

        header = Text()
        header.append(f"┌─[{nid}]─ ", style="bright_black")
        header.append(title, style="bold yellow")
        header.append(f"  (degree={deg})", style="dim")
        console.print(header)

        neighbors = sorted(adj.get(nid, []), key=lambda x: -x[1])
        for i, (neighbor_id, weight) in enumerate(neighbors[:5]):
            neighbor = next((n for n in display_neurons if n.id == neighbor_id), None)
            neighbor_label = neighbor.display_title()[:35] if neighbor else neighbor_id
            bar = _weight_bar(weight)
            connector = "└──" if i == len(neighbors[:5]) - 1 else "├──"
            edge_text = Text()
            edge_text.append(f"│  {connector} ", style="bright_black")
            edge_text.append(bar, style=_weight_color(weight))
            edge_text.append(f" [{neighbor_id}] ", style="dim")
            edge_text.append(neighbor_label, style="dim white")
            console.print(edge_text)

        if not neighbors:
            console.print("│  [dim](no connections)[/dim]")
        console.print()


def _weight_bar(weight: float, width: int = 8) -> str:
    filled = round(weight * width)
    return "█" * filled + "░" * (width - filled) + f" {weight:.2f}"


def _weight_color(weight: float) -> str:
    if weight >= 0.6:
        return "bright_green"
    if weight >= 0.35:
        return "green"
    return "dim green"


def render_stats(stats: "NetworkStats") -> None:
    """Render network statistics as a Rich table."""
    console.print()
    console.rule(Text("Network Statistics", style="bold cyan"))
    console.print()

    table = Table(box=box.ROUNDED, show_header=False, border_style="bright_black")
    table.add_column("Metric", style="dim", width=28)
    table.add_column("Value", style="bold white")

    table.add_row("Neurons", str(stats.neuron_count))
    table.add_row("Synapses", str(stats.synapse_count))
    table.add_row("Avg connections / neuron", f"{stats.avg_degree:.2f}")
    table.add_row("Total concept types", str(len(stats.concept_distribution)))

    console.print(table)

    if stats.most_connected:
        console.print()
        console.print("[dim]Most connected neurons:[/dim]")
        hub_table = Table(box=box.SIMPLE, border_style="bright_black")
        hub_table.add_column("ID", style="dim", width=10)
        hub_table.add_column("Title", style="bold yellow")
        hub_table.add_column("Connections", justify="right", style="green")

        for neuron, degree in stats.most_connected:
            hub_table.add_row(neuron.id, neuron.display_title()[:50], str(degree))

        console.print(hub_table)

    if stats.concept_distribution:
        console.print()
        console.print("[dim]Top concepts:[/dim]")
        top_concepts = sorted(stats.concept_distribution.items(), key=lambda x: -x[1])[:15]
        concept_text = Text()
        for concept, count in top_concepts:
            concept_text.append(f"#{concept}", style="cyan")
            concept_text.append(f"({count}) ", style="dim")
        console.print("  ", concept_text)

    console.print()


def render_neuron_list(neurons: list["Neuron"], synapses: list["Synapse"]) -> None:
    """Render a compact table listing all neurons."""
    if not neurons:
        console.print("[dim]No neurons yet. Use `dendrite add` to create one.[/dim]")
        return

    # Count connections per neuron
    degree: dict[str, int] = {}
    for s in synapses:
        degree[s.source_id] = degree.get(s.source_id, 0) + 1
        degree[s.target_id] = degree.get(s.target_id, 0) + 1

    table = Table(box=box.ROUNDED, border_style="bright_black", show_lines=False)
    table.add_column("ID", style="dim", width=10)
    table.add_column("Title", style="bold yellow", min_width=35)
    table.add_column("Concepts", style="cyan", min_width=30)
    table.add_column("Links", justify="right", style="green", width=6)
    table.add_column("Accessed", justify="right", style="dim", width=9)

    for neuron in neurons:
        concept_str = "  ".join(f"#{c}" for c in neuron.concepts[:4])
        table.add_row(
            neuron.id,
            neuron.display_title()[:50],
            concept_str,
            str(degree.get(neuron.id, 0)),
            str(neuron.access_count),
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]{len(neurons)} neurons in the network[/dim]\n")


def _fmt_time(ts: float) -> str:
    import datetime
    dt = datetime.datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d %H:%M")
