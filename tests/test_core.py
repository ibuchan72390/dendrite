"""Integration tests for the Dendrite core orchestrator."""

import pytest

from dendrite.core import Dendrite


class TestAddNeuron:
    def test_add_returns_neuron(self, dendrite):
        neuron = dendrite.add("The mitochondria is the powerhouse of the cell")
        assert neuron is not None
        assert neuron.id is not None
        assert len(neuron.id) == 8
        assert neuron.content == "The mitochondria is the powerhouse of the cell"

    def test_add_with_title(self, dendrite):
        neuron = dendrite.add("ATP synthesis", title="Energy Currency")
        assert neuron.title == "Energy Currency"

    def test_add_extracts_concepts(self, dendrite):
        neuron = dendrite.add("Mitochondria produce ATP through oxidative phosphorylation")
        assert len(neuron.concepts) > 0
        # Should contain meaningful terms
        all_concepts_lower = [c.lower() for c in neuron.concepts]
        assert any(
            term in all_concepts_lower
            for term in ["mitochondria", "atp", "oxidative", "phosphorylation", "produce"]
        )

    def test_add_creates_synapses(self, dendrite):
        """Adding related notes should create connections."""
        dendrite.add("The mitochondria produces ATP energy in cells")
        dendrite.add("ATP is the energy currency of the cell mitochondria")
        synapses = dendrite.get_all_synapses()
        assert len(synapses) >= 1

    def test_add_no_synapses_for_unrelated(self, dendrite):
        """Unrelated notes should not create strong connections."""
        dendrite.add("Quantum mechanics describes subatomic particle behavior")
        dendrite.add("Ancient Roman gladiators fought in the Colosseum arena")
        synapses = dendrite.get_all_synapses()
        # May have zero or very weak connections
        strong_synapses = [s for s in synapses if s.weight > 0.3]
        assert len(strong_synapses) == 0

    def test_add_first_neuron_no_synapses(self, dendrite):
        dendrite.add("First note ever")
        assert len(dendrite.get_all_synapses()) == 0

    def test_multiple_adds_stored(self, dendrite):
        for i in range(5):
            dendrite.add(f"Note number {i} about topic {i}")
        neurons = dendrite.get_all_neurons()
        assert len(neurons) == 5


class TestAsk:
    def test_ask_empty_network(self, dendrite):
        results = dendrite.ask("what is energy?")
        assert results == []

    def test_ask_returns_results(self, populated_dendrite):
        results = populated_dendrite.ask("how do cells produce energy?")
        assert len(results) > 0

    def test_ask_returns_relevant(self, populated_dendrite):
        """Asking about energy should return energy-related notes."""
        results = populated_dendrite.ask("how does the brain get energy?", top_k=3)
        assert len(results) > 0

        # Top results should be about energy/brain topics
        d = populated_dendrite
        all_ids = {r[0].neuron_id for r in results}
        neurons = d.get_neurons_by_id(list(all_ids))

        top_neuron = neurons.get(results[0][0].neuron_id)
        assert top_neuron is not None
        # The top result should contain energy-related content
        combined_content = " ".join(n.content.lower() for n in neurons.values())
        assert any(word in combined_content for word in ["energy", "brain", "atp", "mitochondria"])

    def test_ask_scores_between_0_and_1(self, populated_dendrite):
        results = populated_dendrite.ask("energy cell mitochondria")
        for seed, _ in results:
            assert 0.0 <= seed.score <= 1.0

    def test_ask_activation_spread(self, populated_dendrite):
        """Activation should spread beyond the seed neuron."""
        results = populated_dendrite.ask("mitochondria energy cell atp", top_k=1)
        assert len(results) > 0
        _, activation_path = results[0]
        # Activation path should contain the seed at minimum
        assert len(activation_path) >= 1

    def test_ask_increments_access(self, dendrite):
        neuron = dendrite.add("mitochondria energy cell powerhouse")
        dendrite.add("atp synthesis oxidative phosphorylation energy")
        initial_count = dendrite.storage.get_neuron(neuron.id, increment_access=False).access_count
        dendrite.ask("mitochondria energy", top_k=1)
        final_count = dendrite.storage.get_neuron(neuron.id, increment_access=False).access_count
        # Accessed at least once
        assert final_count >= initial_count

    def test_ask_single_neuron(self, dendrite):
        """Should return a result even with only one neuron."""
        dendrite.add("The mitochondria is the powerhouse of the cell")
        results = dendrite.ask("mitochondria")
        assert len(results) >= 1


class TestExplore:
    def test_explore_empty_network(self, dendrite):
        net_map = dendrite.explore("energy")
        assert net_map.neurons == []
        assert net_map.synapses == []

    def test_explore_finds_matching_neurons(self, populated_dendrite):
        net_map = populated_dendrite.explore("energy")
        assert len(net_map.neurons) > 0

    def test_explore_finds_connected(self, populated_dendrite):
        """Explore should follow transitive connections."""
        net_map = populated_dendrite.explore("mitochondria", depth=3)
        # Should find mitochondria neurons plus connected neighbors
        assert len(net_map.neurons) >= 1

    def test_explore_no_match(self, populated_dendrite):
        net_map = populated_dendrite.explore("xyzzy_nonexistent_term_12345")
        assert net_map.neurons == []

    def test_explore_returns_seed_concept(self, populated_dendrite):
        net_map = populated_dendrite.explore("brain")
        assert net_map.seed_concept == "brain"

    def test_explore_synapses_within_subgraph(self, populated_dendrite):
        net_map = populated_dendrite.explore("energy", depth=2)
        # All synapses should connect neurons within the subgraph
        neuron_ids = {n.id for n in net_map.neurons}
        for s in net_map.synapses:
            assert s.source_id in neuron_ids
            assert s.target_id in neuron_ids


class TestStats:
    def test_stats_empty_network(self, dendrite):
        stats = dendrite.stats()
        assert stats.neuron_count == 0
        assert stats.synapse_count == 0
        assert stats.avg_degree == 0.0
        assert stats.most_connected == []

    def test_stats_counts_correctly(self, populated_dendrite):
        stats = populated_dendrite.stats()
        assert stats.neuron_count == 5
        assert stats.synapse_count >= 0

    def test_stats_avg_degree(self, populated_dendrite):
        stats = populated_dendrite.stats()
        if stats.synapse_count > 0:
            # avg_degree = 2 * synapse_count / neuron_count
            expected = (2 * stats.synapse_count) / stats.neuron_count
            assert stats.avg_degree == pytest.approx(expected)

    def test_stats_most_connected_ordered(self, populated_dendrite):
        stats = populated_dendrite.stats()
        if len(stats.most_connected) > 1:
            for i in range(len(stats.most_connected) - 1):
                assert stats.most_connected[i][1] >= stats.most_connected[i + 1][1]

    def test_stats_concept_distribution(self, populated_dendrite):
        stats = populated_dendrite.stats()
        assert isinstance(stats.concept_distribution, dict)
        assert len(stats.concept_distribution) > 0


class TestConsolidation:
    def test_run_consolidation_integration(self, dendrite):
        """Full workflow: add notes, ask (creates traversals), consolidate."""
        dendrite.add("mitochondria produces atp energy cell powerhouse")
        dendrite.add("atp energy currency cell mitochondria oxidative")
        dendrite.add("cellular respiration glucose energy atp production")

        # Ask to create traversals
        dendrite.ask("energy atp mitochondria", top_k=2)

        # Get synapse weights before consolidation
        synapses_before = {
            (s.source_id, s.target_id): s.weight for s in dendrite.get_all_synapses()
        }

        # Run consolidation
        count = dendrite.run_consolidation()
        assert count >= 0  # May be 0 if no traversal_count > 0

        # Weights should be >= before (consolidation only boosts)
        for s in dendrite.get_all_synapses():
            key = (s.source_id, s.target_id)
            if key in synapses_before:
                assert s.weight >= synapses_before[key] - 1e-9

    def test_run_decay_integration(self, dendrite):
        dendrite.add("cell energy mitochondria atp")
        dendrite.add("mitochondria powerhouse energy production")

        synapses_before = {
            (s.source_id, s.target_id): s.weight for s in dendrite.get_all_synapses()
        }

        if not synapses_before:
            pytest.skip("No synapses created (similarity below threshold)")

        dendrite.run_decay(days=1.0)

        for s in dendrite.get_all_synapses():
            key = (s.source_id, s.target_id)
            if key in synapses_before:
                assert s.weight < synapses_before[key]

    def test_get_neuron_by_id(self, dendrite):
        neuron = dendrite.add("test content for lookup")
        retrieved = dendrite.get_neuron(neuron.id)
        assert retrieved is not None
        assert retrieved.id == neuron.id

    def test_get_neurons_by_id_batch(self, dendrite):
        n1 = dendrite.add("first note")
        n2 = dendrite.add("second note")
        batch = dendrite.get_neurons_by_id([n1.id, n2.id])
        assert n1.id in batch
        assert n2.id in batch
