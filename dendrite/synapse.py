"""Activation spreading, consolidation, and decay for the synaptic network."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dendrite.storage import Storage, Synapse


@dataclass
class ActivationResult:
    """Represents a neuron that was activated during spreading."""

    neuron_id: str
    score: float
    depth: int
    path: list[str] = field(default_factory=list)  # neuron IDs from seed to this node


@dataclass
class TraversalRecord:
    source_id: str
    target_id: str
    timestamp: float = field(default_factory=time.time)


# How much each hop attenuates the activation signal
HOP_DECAY = 0.7
# Boost factor applied during consolidation
CONSOLIDATION_BOOST = 1.1
# Daily decay factor for unused synapses
DAILY_DECAY = 0.95


def activate(
    storage: "Storage",
    seed_neuron_id: str,
    threshold: float = 0.2,
    depth: int = 3,
    seed_score: float = 1.0,
) -> tuple[list[ActivationResult], list[TraversalRecord]]:
    """
    BFS from seed_neuron_id through synaptic connections.

    Returns:
        results       — list of ActivationResult, one per reached neuron (includes seed)
        traversals    — list of TraversalRecord for every edge crossed
    """
    results: list[ActivationResult] = []
    traversals: list[TraversalRecord] = []

    # (neuron_id, current_score, current_depth, path)
    queue: deque[tuple[str, float, int, list[str]]] = deque()
    queue.append((seed_neuron_id, seed_score, 0, [seed_neuron_id]))
    visited: set[str] = set()

    while queue:
        neuron_id, score, current_depth, path = queue.popleft()

        if neuron_id in visited:
            continue
        visited.add(neuron_id)

        results.append(
            ActivationResult(
                neuron_id=neuron_id,
                score=score,
                depth=current_depth,
                path=list(path),
            )
        )

        if current_depth >= depth:
            continue

        # Get edges in both directions (synapses are stored bidirectionally but
        # we stored them directionally; treat graph as undirected for spreading)
        synapses = _get_all_edges(storage, neuron_id)

        for synapse in synapses:
            neighbor_id = (
                synapse.target_id if synapse.source_id == neuron_id else synapse.source_id
            )
            if neighbor_id in visited:
                continue
            if synapse.weight < threshold:
                continue

            next_score = score * synapse.weight * HOP_DECAY
            traversals.append(TraversalRecord(source_id=neuron_id, target_id=neighbor_id))
            queue.append((neighbor_id, next_score, current_depth + 1, path + [neighbor_id]))

    return results, traversals


def _get_all_edges(storage: "Storage", neuron_id: str) -> list["Synapse"]:
    """Return all synapses incident to neuron_id (in either direction)."""
    return storage.get_synapses_for_neuron(neuron_id)


def consolidate(storage: "Storage", traversals: list[TraversalRecord]) -> int:
    """
    Boost weights of recently traversed edges by CONSOLIDATION_BOOST.

    Returns the number of synapses updated.
    """
    # Deduplicate: only boost each directed edge once per consolidation pass
    seen: set[tuple[str, str]] = set()
    updated = 0

    for record in traversals:
        key = (record.source_id, record.target_id)
        reverse_key = (record.target_id, record.source_id)

        # Try both directions (synapses stored as source→target)
        for src, tgt in (key, reverse_key):
            if (src, tgt) in seen:
                continue
            synapse = storage.get_synapse(src, tgt)
            if synapse is None:
                continue
            seen.add((src, tgt))
            new_weight = min(synapse.weight * CONSOLIDATION_BOOST, 1.0)
            storage.update_synapse_weight(src, tgt, new_weight)
            storage.record_traversal(src, tgt)
            updated += 1

    return updated


def decay(storage: "Storage", days_since_access: float) -> int:
    """
    Multiply all synapse weights by DAILY_DECAY^days_since_access.

    Returns the number of synapses updated.
    """
    if days_since_access <= 0:
        return 0

    factor = DAILY_DECAY ** days_since_access
    all_synapses = storage.get_all_synapses()
    updated = 0

    for synapse in all_synapses:
        new_weight = synapse.weight * factor
        storage.update_synapse_weight(synapse.source_id, synapse.target_id, new_weight)
        updated += 1

    return updated
