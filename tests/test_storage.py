"""Unit tests for the SQLite storage layer."""

import time

import pytest

from dendrite.storage import Neuron, Storage, Synapse, new_id


class TestNewId:
    def test_returns_string(self):
        assert isinstance(new_id(), str)

    def test_length_8(self):
        assert len(new_id()) == 8

    def test_unique(self):
        ids = {new_id() for _ in range(100)}
        assert len(ids) == 100


class TestNeuronCRUD:
    def test_add_and_retrieve(self, storage):
        neuron = Neuron(
            id=new_id(),
            content="The mitochondria is the powerhouse of the cell",
            title="Mitochondria",
            concepts=["mitochondria", "powerhouse", "cell"],
        )
        storage.add_neuron(neuron)
        retrieved = storage.get_neuron(neuron.id, increment_access=False)
        assert retrieved is not None
        assert retrieved.id == neuron.id
        assert retrieved.content == neuron.content
        assert retrieved.title == neuron.title
        assert retrieved.concepts == neuron.concepts

    def test_access_count_increment(self, storage):
        neuron = Neuron(id=new_id(), content="test content")
        storage.add_neuron(neuron)

        # Retrieve with increment_access=True three times
        storage.get_neuron(neuron.id, increment_access=True)
        storage.get_neuron(neuron.id, increment_access=True)
        storage.get_neuron(neuron.id, increment_access=True)

        retrieved = storage.get_neuron(neuron.id, increment_access=False)
        assert retrieved.access_count == 3

    def test_no_access_count_increment(self, storage):
        neuron = Neuron(id=new_id(), content="test content")
        storage.add_neuron(neuron)
        storage.get_neuron(neuron.id, increment_access=False)
        storage.get_neuron(neuron.id, increment_access=False)
        retrieved = storage.get_neuron(neuron.id, increment_access=False)
        assert retrieved.access_count == 0

    def test_get_nonexistent(self, storage):
        assert storage.get_neuron("nonexistent") is None

    def test_get_all_neurons(self, storage):
        for i in range(3):
            storage.add_neuron(Neuron(id=new_id(), content=f"content {i}"))
        neurons = storage.get_all_neurons()
        assert len(neurons) == 3

    def test_update_concepts(self, storage):
        neuron = Neuron(id=new_id(), content="test")
        storage.add_neuron(neuron)
        storage.update_neuron_concepts(neuron.id, ["concept1", "concept2"])
        retrieved = storage.get_neuron(neuron.id, increment_access=False)
        assert retrieved.concepts == ["concept1", "concept2"]

    def test_delete_neuron(self, storage):
        neuron = Neuron(id=new_id(), content="will be deleted")
        storage.add_neuron(neuron)
        # Add a synapse
        other = Neuron(id=new_id(), content="other")
        storage.add_neuron(other)
        storage.upsert_synapse(Synapse(source_id=neuron.id, target_id=other.id, weight=0.5))

        storage.delete_neuron(neuron.id)
        assert storage.get_neuron(neuron.id, increment_access=False) is None
        # Synapse should also be gone
        assert storage.get_synapse(neuron.id, other.id) is None

    def test_neuron_without_title(self, storage):
        neuron = Neuron(id=new_id(), content="No title here")
        storage.add_neuron(neuron)
        retrieved = storage.get_neuron(neuron.id, increment_access=False)
        assert retrieved.title is None

    def test_display_title_with_title(self, storage):
        neuron = Neuron(id=new_id(), content="content", title="My Title")
        storage.add_neuron(neuron)
        assert neuron.display_title() == "My Title"

    def test_display_title_without_title(self, storage):
        neuron = Neuron(id=new_id(), content="This is a short note")
        title = neuron.display_title()
        assert "This is a short note" in title


class TestSynapseCRUD:
    def test_upsert_creates_synapse(self, storage):
        n1 = Neuron(id=new_id(), content="cell energy")
        n2 = Neuron(id=new_id(), content="mitochondria atp")
        storage.add_neuron(n1)
        storage.add_neuron(n2)

        synapse = Synapse(source_id=n1.id, target_id=n2.id, weight=0.75)
        storage.upsert_synapse(synapse)

        retrieved = storage.get_synapse(n1.id, n2.id)
        assert retrieved is not None
        assert retrieved.weight == pytest.approx(0.75)

    def test_upsert_updates_weight(self, storage):
        n1 = Neuron(id=new_id(), content="a")
        n2 = Neuron(id=new_id(), content="b")
        storage.add_neuron(n1)
        storage.add_neuron(n2)

        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.5))
        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.8))

        retrieved = storage.get_synapse(n1.id, n2.id)
        assert retrieved.weight == pytest.approx(0.8)

    def test_get_synapses_for_neuron(self, storage):
        n1 = Neuron(id=new_id(), content="hub")
        n2 = Neuron(id=new_id(), content="spoke1")
        n3 = Neuron(id=new_id(), content="spoke2")
        for n in (n1, n2, n3):
            storage.add_neuron(n)

        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.5))
        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n3.id, weight=0.6))

        synapses = storage.get_synapses_for_neuron(n1.id)
        assert len(synapses) == 2

    def test_get_outgoing_synapses(self, storage):
        n1 = Neuron(id=new_id(), content="source")
        n2 = Neuron(id=new_id(), content="target1")
        n3 = Neuron(id=new_id(), content="target2")
        for n in (n1, n2, n3):
            storage.add_neuron(n)

        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.3))
        storage.upsert_synapse(Synapse(source_id=n3.id, target_id=n1.id, weight=0.4))

        outgoing = storage.get_outgoing_synapses(n1.id)
        assert len(outgoing) == 1
        assert outgoing[0].target_id == n2.id

    def test_record_traversal(self, storage):
        n1 = Neuron(id=new_id(), content="a")
        n2 = Neuron(id=new_id(), content="b")
        storage.add_neuron(n1)
        storage.add_neuron(n2)

        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.5))
        storage.record_traversal(n1.id, n2.id)
        storage.record_traversal(n1.id, n2.id)

        retrieved = storage.get_synapse(n1.id, n2.id)
        assert retrieved.traversal_count == 2
        assert retrieved.last_traversed is not None

    def test_update_synapse_weight(self, storage):
        n1 = Neuron(id=new_id(), content="a")
        n2 = Neuron(id=new_id(), content="b")
        storage.add_neuron(n1)
        storage.add_neuron(n2)

        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.4))
        storage.update_synapse_weight(n1.id, n2.id, 0.9)

        retrieved = storage.get_synapse(n1.id, n2.id)
        assert retrieved.weight == pytest.approx(0.9)

    def test_count_synapses(self, storage):
        n1 = Neuron(id=new_id(), content="a")
        n2 = Neuron(id=new_id(), content="b")
        n3 = Neuron(id=new_id(), content="c")
        for n in (n1, n2, n3):
            storage.add_neuron(n)

        storage.upsert_synapse(Synapse(source_id=n1.id, target_id=n2.id, weight=0.5))
        storage.upsert_synapse(Synapse(source_id=n2.id, target_id=n3.id, weight=0.6))
        assert storage.count_synapses() == 2

    def test_concept_distribution(self, storage):
        n1 = Neuron(id=new_id(), content="a", concepts=["energy", "cell"])
        n2 = Neuron(id=new_id(), content="b", concepts=["energy", "atp"])
        storage.add_neuron(n1)
        storage.add_neuron(n2)

        dist = storage.get_concept_distribution()
        assert dist["energy"] == 2
        assert dist["cell"] == 1
        assert dist["atp"] == 1

    def test_get_most_connected_neurons(self, storage):
        neurons = [Neuron(id=new_id(), content=f"n{i}") for i in range(4)]
        for n in neurons:
            storage.add_neuron(n)

        # Make neurons[0] a hub with 3 connections
        for i in range(1, 4):
            storage.upsert_synapse(
                Synapse(source_id=neurons[0].id, target_id=neurons[i].id, weight=0.5)
            )

        most_connected = storage.get_most_connected_neurons(limit=1)
        assert most_connected[0][0] == neurons[0].id
        assert most_connected[0][1] == 3
