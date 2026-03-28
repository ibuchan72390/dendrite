"""Dendrite main orchestrator — coordinates storage, analysis, and activation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from dendrite.analyzer import (
    build_similarity_matrix,
    extract_concepts,
    find_related,
)
from dendrite.storage import Neuron, Storage, Synapse, new_id
from dendrite.synapse import (
    ActivationResult,
    TraversalRecord,
    activate,
    consolidate,
    decay,
)


@dataclass
class NetworkMap:
    """Subgraph returned by explore()."""

    seed_concept: str
    neurons: list[Neuron]
    synapses: list[Synapse]


@dataclass
class NetworkStats:
    neuron_count: int
    synapse_count: int
    avg_degree: float
    most_connected: list[tuple[Neuron, int]]
    concept_distribution: dict[str, int]


SIMILARITY_THRESHOLD = 0.1  # Minimum cosine sim to create a synapse


class Dendrite:
    """
    Main class for the Dendrite knowledge network.

    All state lives in the Storage instance; Dendrite is a thin orchestration layer.
    """

    def __init__(self, db_path: str = ":memory:", reindex_interval: int = 10):
        self.storage = Storage(db_path)
        self.reindex_interval = reindex_interval

    def close(self):
        self.storage.close()

    # ------------------------------------------------------------------
    # add
    # ------------------------------------------------------------------

    def add(self, content: str, title: Optional[str] = None) -> Neuron:
        """
        1. Create and store the neuron.
        2. Extract concepts.
        3. Increment write counter; trigger full reindex every reindex_interval writes.
        4. Return the neuron.

        TF-IDF similarity is NOT recomputed on every add — use `reindex()` or
        wait for the automatic background trigger every `reindex_interval` writes.
        """
        now = time.time()
        neuron = Neuron(
            id=new_id(),
            content=content,
            title=title,
            created_at=now,
            accessed_at=now,
            access_count=0,
        )

        # Extract concepts before saving so they're persisted immediately
        concepts = extract_concepts(content, top_n=8)
        neuron.concepts = concepts

        self.storage.add_neuron(neuron)

        write_count = self.storage.increment_write_count()
        if write_count % self.reindex_interval == 0:
            self.reindex()

        return neuron

    def reindex(self) -> int:
        """
        Full TF-IDF reindex: recompute pairwise cosine similarity for all neurons
        and rebuild the synapse table from scratch.

        Returns the number of synapses created.
        """
        all_neurons = self.storage.get_all_neurons()
        if len(all_neurons) < 2:
            return 0

        texts = [n.content for n in all_neurons]
        sim_matrix = build_similarity_matrix(texts)
        n = len(all_neurons)

        self.storage.delete_all_synapses()

        count = 0
        for i in range(n):
            for j in range(i + 1, n):
                sim = sim_matrix[i, j]
                if sim > SIMILARITY_THRESHOLD:
                    synapse = Synapse(
                        source_id=all_neurons[i].id,
                        target_id=all_neurons[j].id,
                        weight=float(sim),
                        traversal_count=0,
                        last_traversed=None,
                    )
                    self.storage.upsert_synapse(synapse)
                    count += 1

        return count

    # ------------------------------------------------------------------
    # ask
    # ------------------------------------------------------------------

    def ask(
        self,
        query: str,
        top_k: int = 5,
        activation_threshold: float = 0.15,
        activation_depth: int = 3,
    ) -> list[tuple[ActivationResult, list[ActivationResult]]]:
        """
        1. Vectorize query against corpus.
        2. Find top_k most similar neurons.
        3. Run activation spreading from each seed.
        4. Log traversals for consolidation.
        5. Return list of (seed_result, activation_path).
        """
        all_neurons = self.storage.get_all_neurons()
        if not all_neurons:
            return []

        corpus_texts = [n.content for n in all_neurons]

        if len(all_neurons) == 1:
            # Trivial case
            scores = [(0, 1.0)]
        else:
            scores = find_related(query, corpus_texts, top_k=top_k)

        all_traversals: list[TraversalRecord] = []
        results: list[tuple[ActivationResult, list[ActivationResult]]] = []

        for idx, score in scores:
            if score <= 0:
                continue
            seed_neuron = all_neurons[idx]
            # Touch the neuron (increment access count)
            self.storage.get_neuron(seed_neuron.id, increment_access=True)

            seed_result = ActivationResult(
                neuron_id=seed_neuron.id,
                score=score,
                depth=0,
                path=[seed_neuron.id],
            )

            activation, traversals = activate(
                self.storage,
                seed_neuron.id,
                threshold=activation_threshold,
                depth=activation_depth,
                seed_score=score,
            )
            all_traversals.extend(traversals)
            results.append((seed_result, activation))

        # Consolidate traversals
        if all_traversals:
            consolidate(self.storage, all_traversals)

        # Sort by seed score descending
        results.sort(key=lambda x: -x[0].score)
        return results

    # ------------------------------------------------------------------
    # explore
    # ------------------------------------------------------------------

    def explore(self, concept: str, depth: int = 3) -> NetworkMap:
        """
        1. Find neurons containing concept.
        2. BFS through connections up to depth hops.
        3. Return NetworkMap.
        """
        concept_lower = concept.lower()
        all_neurons = self.storage.get_all_neurons()

        # Seed: neurons whose concepts list contains the term, or content mentions it
        seeds = [
            n for n in all_neurons
            if concept_lower in [c.lower() for c in n.concepts]
            or concept_lower in n.content.lower()
        ]

        if not seeds:
            return NetworkMap(seed_concept=concept, neurons=[], synapses=[])

        visited_ids: set[str] = set()
        frontier = list(seeds)

        for _ in range(depth):
            next_frontier: list[Neuron] = []
            for neuron in frontier:
                if neuron.id in visited_ids:
                    continue
                visited_ids.add(neuron.id)
                synapses = self.storage.get_synapses_for_neuron(neuron.id)
                for s in synapses:
                    neighbor_id = s.target_id if s.source_id == neuron.id else s.source_id
                    if neighbor_id not in visited_ids:
                        neighbor = self.storage.get_neuron(neighbor_id, increment_access=False)
                        if neighbor:
                            next_frontier.append(neighbor)
            frontier = next_frontier

        # Collect all neurons in the subgraph
        all_ids = visited_ids | {n.id for n in frontier}
        subgraph_neurons = [n for n in all_neurons if n.id in all_ids]

        # Collect synapses within the subgraph
        subgraph_synapses: list[Synapse] = []
        seen_edges: set[tuple[str, str]] = set()
        for n in subgraph_neurons:
            for s in self.storage.get_synapses_for_neuron(n.id):
                edge = (min(s.source_id, s.target_id), max(s.source_id, s.target_id))
                if edge not in seen_edges and s.source_id in all_ids and s.target_id in all_ids:
                    seen_edges.add(edge)
                    subgraph_synapses.append(s)

        return NetworkMap(
            seed_concept=concept,
            neurons=subgraph_neurons,
            synapses=subgraph_synapses,
        )

    # ------------------------------------------------------------------
    # stats
    # ------------------------------------------------------------------

    def stats(self) -> NetworkStats:
        all_neurons = self.storage.get_all_neurons()
        n_neurons = len(all_neurons)
        n_synapses = self.storage.count_synapses()

        if n_neurons == 0:
            return NetworkStats(
                neuron_count=0,
                synapse_count=0,
                avg_degree=0.0,
                most_connected=[],
                concept_distribution={},
            )

        avg_degree = (2 * n_synapses) / n_neurons if n_neurons else 0.0

        neurons_by_id = {n.id: n for n in all_neurons}
        most_connected_raw = self.storage.get_most_connected_neurons(limit=5)
        most_connected = [
            (neurons_by_id[nid], deg)
            for nid, deg in most_connected_raw
            if nid in neurons_by_id
        ]

        concept_distribution = self.storage.get_concept_distribution()

        return NetworkStats(
            neuron_count=n_neurons,
            synapse_count=n_synapses,
            avg_degree=avg_degree,
            most_connected=most_connected,
            concept_distribution=concept_distribution,
        )

    # ------------------------------------------------------------------
    # consolidate
    # ------------------------------------------------------------------

    def run_consolidation(self) -> int:
        """
        Boost weights of edges that have been traversed recently.
        Returns number of synapses updated.
        """
        all_synapses = self.storage.get_all_synapses()
        traversed = [
            TraversalRecord(source_id=s.source_id, target_id=s.target_id)
            for s in all_synapses
            if s.traversal_count > 0
        ]
        return consolidate(self.storage, traversed)

    def run_decay(self, days: float = 1.0) -> int:
        """Apply temporal decay to all synapse weights. Returns number updated."""
        return decay(self.storage, days)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def get_neuron(self, neuron_id: str) -> Optional[Neuron]:
        return self.storage.get_neuron(neuron_id)

    def get_all_neurons(self) -> list[Neuron]:
        return self.storage.get_all_neurons()

    def get_all_synapses(self) -> list[Synapse]:
        return self.storage.get_all_synapses()

    def get_neurons_by_id(self, ids: list[str]) -> dict[str, Neuron]:
        result = {}
        for nid in ids:
            n = self.storage.get_neuron(nid, increment_access=False)
            if n:
                result[nid] = n
        return result
