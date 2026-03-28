"""Shared fixtures for Dendrite tests."""

import pytest

from dendrite.core import Dendrite
from dendrite.storage import Storage


@pytest.fixture
def storage():
    """In-memory SQLite storage instance."""
    s = Storage(":memory:")
    yield s
    s.close()


@pytest.fixture
def dendrite():
    """Full in-memory Dendrite instance."""
    d = Dendrite(db_path=":memory:")
    yield d
    d.close()


@pytest.fixture
def populated_dendrite():
    """Dendrite pre-loaded with biology/energy notes for integration tests."""
    d = Dendrite(db_path=":memory:")
    d.add("The mitochondria is the powerhouse of the cell", title="Mitochondria")
    d.add(
        "Cells produce ATP through oxidative phosphorylation in the mitochondria",
        title="ATP Production",
    )
    d.add(
        "The brain consumes more energy than any other organ in the body",
        title="Brain Energy",
    )
    d.add(
        "Neural networks are inspired by biological neurons in the brain",
        title="Neural Networks",
    )
    d.add(
        "Glucose is broken down during cellular respiration to release energy",
        title="Glucose Metabolism",
    )
    yield d
    d.close()
