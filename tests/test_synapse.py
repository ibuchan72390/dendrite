"""Unit tests for activation spreading, consolidation, and decay."""

import time

import pytest

from dendrite.storage import Neuron, Storage, Synapse, new_id
from dendrite.synapse import (
    CONSOLIDATION_BOOST,
    DAILY_DECAY,
    HOP_DECAY,
    ActivationResult,
    TraversalRecord,
    activate,
    consolidate,
    decay,
)


def make_neuron(content: str) -> Neuron:
    return Neuron(id=new_id(), content=content)


def add_neurons_and_synapses(storage: Storage, pairs: list[tuple[str, str, float]]):
    """Helper: add neurons and connect them with given weights."""
    neuron_ids = {}
    for src_content, tgt_content, weight in pairs:
        for content in (src_content, tgt_content):
            if content not in neuron_ids:
                n = Neuron(id=new_id(), content=content)
                storage.add_neuron(n)
                neuron_ids[content] = n.id

        src_id = neuron_ids[src_content]
        tgt_id = neuron_ids[tgt_content]
        storage.upsert_synapse(Synapse(source_id=src_id, target_id=tgt_id, weight=weight))

    return neuron_ids


class TestActivationSpreading:
    def test_seed_always_activated(self, storage):
        n = make_neuron("seed neuron")
        storage.add_neuron(n)
        results, _ = activate(storage, n.id, threshold=0.2, depth=3)
        activated_ids = [r.neuron_id for r in results]
        assert n.id in activated_ids

    def test_activation_spreading_bfs(self, storage):
        """BFS should reach connected neighbors."""
        ids = add_neurons_and_synapses(
            storage,
            [
                ("seed", "neighbor1", 0.5),
                ("neighbor1", "neighbor2", 0.6),
            ],
        )
        results, traversals = activate(storage, ids["seed"], threshold=0.2, depth=3)
        activated_ids = {r.neuron_id for r in results}
        assert ids["seed"] in activated_ids
        assert ids["neighbor1"] in activated_ids
        assert ids["neighbor2"] in activated_ids

    def test_activation_threshold(self, storage):
        """Low-weight edges should not be traversed."""
        ids = add_neurons_and_synapses(
            storage,
            [("seed", "weakly_connected", 0.05)],
        )
        results, _ = activate(storage, ids["seed"], threshold=0.2, depth=3)
        activated_ids = {r.neuron_id for r in results}
        assert ids["weakly_connected"] not in activated_ids

    def test_activation_depth_limit(self, storage):
        """Activation should not go beyond max depth."""
        ids = add_neurons_and_synapses(
            storage,
            [
                ("a", "b", 0.8),
                ("b", "c", 0.8),
                ("c", "d", 0.8),
                ("d", "e", 0.8),
            ],
        )
        results, _ = activate(storage, ids["a"], threshold=0.1, depth=2)
        activated_ids = {r.neuron_id for r in results}
        assert ids["a"] in activated_ids
        assert ids["b"] in activated_ids
        assert ids["c"] in activated_ids
        # depth=2 means 2 hops max, d is 3 hops away
        assert ids["d"] not in activated_ids
        assert ids["e"] not in activated_ids

    def test_score_decays_with_depth(self, storage):
        """Each hop should reduce the activation score by HOP_DECAY × synapse weight."""
        ids = add_neurons_and_synapses(
            storage,
            [
                ("root", "level1", 1.0),
                ("level1", "level2", 1.0),
            ],
        )
        results, _ = activate(storage, ids["root"], threshold=0.0, depth=3, seed_score=1.0)
        by_id = {r.neuron_id: r for r in results}

        root_score = by_id[ids["root"]].score
        l1_score = by_id[ids["level1"]].score
        l2_score = by_id[ids["level2"]].score

        assert root_score == pytest.approx(1.0)
        assert l1_score == pytest.approx(1.0 * 1.0 * HOP_DECAY, rel=1e-3)
        assert l2_score == pytest.approx(1.0 * 1.0 * HOP_DECAY * 1.0 * HOP_DECAY, rel=1e-3)

    def test_visited_nodes_not_revisited(self, storage):
        """Cycle in graph should not cause infinite loop."""
        n1 = make_neuron("n1")
        n2 = make_neuron("n2")
        storage.add_neuron(n1)
        storage.add_neuron(n2)
        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.5))
        storage.upsert_synapse(Synapse(source_id=n2.id, target_id=n1.id, weight=0.5))

        results, _ = activate(storage, n1.id, threshold=0.1, depth=5)
        activated_ids = [r.neuron_id for r in results]
        # n1 and n2 should each appear exactly once
        assert activated_ids.count(n1.id) == 1
        assert activated_ids.count(n2.id) == 1

    def test_traversals_recorded(self, storage):
        """Traversals list should contain edges that were crossed."""
        ids = add_neurons_and_synapses(
            storage,
            [("start", "end", 0.7)],
        )
        _, traversals = activate(storage, ids["start"], threshold=0.1, depth=3)
        assert len(traversals) == 1
        assert traversals[0].source_id == ids["start"]
        assert traversals[0].target_id == ids["end"]


class TestConsolidation:
    def test_consolidation_boosts_weight(self, storage):
        n1 = make_neuron("n1")
        n2 = make_neuron("n2")
        storage.add_neuron(n1)
        storage.add_neuron(n2)
        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.5))

        traversals = [TraversalRecord(source_id=n1.id, target_id=n2.id)]
        consolidate(storage, traversals)

        updated = storage.get_synapse(n1.id, n2.id)
        assert updated.weight == pytest.approx(0.5 * CONSOLIDATION_BOOST, rel=1e-3)

    def test_consolidation_caps_at_one(self, storage):
        """Weight should never exceed 1.0 after consolidation."""
        n1 = make_neuron("n1")
        n2 = make_neuron("n2")
        storage.add_neuron(n1)
        storage.add_neuron(n2)
        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.99))

        traversals = [TraversalRecord(source_id=n1.id, target_id=n2.id)]
        consolidate(storage, traversals)

        updated = storage.get_synapse(n1.id, n2.id)
        assert updated.weight <= 1.0

    def test_consolidation_only_affects_traversed(self, storage):
        n1 = make_neuron("n1")
        n2 = make_neuron("n2")
        n3 = make_neuron("n3")
        storage.add_neuron(n1)
        storage.add_neuron(n2)
        storage.add_neuron(n3)
        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.5))
        storage.upsert_synapse(Synapse(source_id=n2.id, target_id=n3.id, weight=0.4))

        # Only traverse n1→n2
        traversals = [TraversalRecord(source_id=n1.id, target_id=n2.id)]
        consolidate(storage, traversals)

        s12 = storage.get_synapse(n1.id, n2.id)
        s23 = storage.get_synapse(n2.id, n3.id)
        assert s12.weight > 0.5
        assert s23.weight == pytest.approx(0.4)

    def test_consolidation_returns_count(self, storage):
        n1 = make_neuron("n1")
        n2 = make_neuron("n2")
        storage.add_neuron(n1)
        storage.add_neuron(n2)
        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.5))

        traversals = [TraversalRecord(source_id=n1.id, target_id=n2.id)]
        count = consolidate(storage, traversals)
        assert count == 1

    def test_consolidation_deduplicates_traversals(self, storage):
        """Same edge traversed multiple times in one pass should only boost once."""
        n1 = make_neuron("n1")
        n2 = make_neuron("n2")
        storage.add_neuron(n1)
        storage.add_neuron(n2)
        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.5))

        traversals = [
            TraversalRecord(source_id=n1.id, target_id=n2.id),
            TraversalRecord(source_id=n1.id, target_id=n2.id),
            TraversalRecord(source_id=n1.id, target_id=n2.id),
        ]
        consolidate(storage, traversals)

        updated = storage.get_synapse(n1.id, n2.id)
        # Should be boosted only once: 0.5 * 1.1 = 0.55
        assert updated.weight == pytest.approx(0.5 * CONSOLIDATION_BOOST, rel=1e-3)


class TestDecay:
    def test_decay_weakens_weights(self, storage):
        n1 = make_neuron("n1")
        n2 = make_neuron("n2")
        storage.add_neuron(n1)
        storage.add_neuron(n2)
        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.8))

        decay(storage, days_since_access=1.0)

        updated = storage.get_synapse(n1.id, n2.id)
        assert updated.weight == pytest.approx(0.8 * DAILY_DECAY, rel=1e-3)

    def test_decay_zero_days_no_change(self, storage):
        n1 = make_neuron("n1")
        n2 = make_neuron("n2")
        storage.add_neuron(n1)
        storage.add_neuron(n2)
        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.8))

        n_updated = decay(storage, days_since_access=0.0)
        assert n_updated == 0

        updated = storage.get_synapse(n1.id, n2.id)
        assert updated.weight == pytest.approx(0.8)

    def test_decay_exponential_with_days(self, storage):
        n1 = make_neuron("n1")
        n2 = make_neuron("n2")
        storage.add_neuron(n1)
        storage.add_neuron(n2)
        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=1.0))

        days = 7.0
        decay(storage, days_since_access=days)

        updated = storage.get_synapse(n1.id, n2.id)
        expected = 1.0 * (DAILY_DECAY ** days)
        assert updated.weight == pytest.approx(expected, rel=1e-3)

    def test_decay_returns_count(self, storage):
        for _ in range(3):
            n1 = make_neuron("x")
            n2 = make_neuron("y")
            storage.add_neuron(n1)
            storage.add_neuron(n2)
            storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.5))

        count = decay(storage, days_since_access=1.0)
        assert count == 3

    def test_decay_does_not_go_negative(self, storage):
        n1 = make_neuron("n1")
        n2 = make_neuron("n2")
        storage.add_neuron(n1)
        storage.add_neuron(n2)
        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.001))

        decay(storage, days_since_access=1000.0)
        updated = storage.get_synapse(n1.id, n2.id)
        assert updated.weight >= 0
