"""SQLite storage layer for Dendrite neurons and synapses."""

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


def new_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class Neuron:
    id: str
    content: str
    title: Optional[str] = None
    concepts: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0

    def display_title(self) -> str:
        if self.title:
            return self.title
        # Auto-generate a title from first ~60 chars of content
        snippet = self.content[:60].strip()
        if len(self.content) > 60:
            snippet += "..."
        return snippet


@dataclass
class Synapse:
    source_id: str
    target_id: str
    weight: float
    traversal_count: int = 0
    last_traversed: Optional[float] = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS neurons (
    id TEXT PRIMARY KEY,
    title TEXT,
    content TEXT NOT NULL,
    concepts TEXT,
    created_at REAL,
    accessed_at REAL,
    access_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS synapses (
    source_id TEXT,
    target_id TEXT,
    weight REAL,
    traversal_count INTEGER DEFAULT 0,
    last_traversed REAL,
    PRIMARY KEY (source_id, target_id)
);
"""


class Storage:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # --- Neuron CRUD ---

    def add_neuron(self, neuron: Neuron) -> Neuron:
        self.conn.execute(
            """
            INSERT INTO neurons (id, title, content, concepts, created_at, accessed_at, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                neuron.id,
                neuron.title,
                neuron.content,
                json.dumps(neuron.concepts),
                neuron.created_at,
                neuron.accessed_at,
                neuron.access_count,
            ),
        )
        self.conn.commit()
        return neuron

    def get_neuron(self, neuron_id: str, increment_access: bool = True) -> Optional[Neuron]:
        row = self.conn.execute(
            "SELECT * FROM neurons WHERE id = ?", (neuron_id,)
        ).fetchone()
        if row is None:
            return None
        if increment_access:
            now = time.time()
            self.conn.execute(
                "UPDATE neurons SET accessed_at = ?, access_count = access_count + 1 WHERE id = ?",
                (now, neuron_id),
            )
            self.conn.commit()
        return self._row_to_neuron(row)

    def get_all_neurons(self) -> list[Neuron]:
        rows = self.conn.execute("SELECT * FROM neurons ORDER BY created_at DESC").fetchall()
        return [self._row_to_neuron(r) for r in rows]

    def update_neuron_concepts(self, neuron_id: str, concepts: list[str]) -> None:
        self.conn.execute(
            "UPDATE neurons SET concepts = ? WHERE id = ?",
            (json.dumps(concepts), neuron_id),
        )
        self.conn.commit()

    def delete_neuron(self, neuron_id: str) -> None:
        self.conn.execute("DELETE FROM neurons WHERE id = ?", (neuron_id,))
        self.conn.execute(
            "DELETE FROM synapses WHERE source_id = ? OR target_id = ?",
            (neuron_id, neuron_id),
        )
        self.conn.commit()

    def _row_to_neuron(self, row: sqlite3.Row) -> Neuron:
        concepts = json.loads(row["concepts"]) if row["concepts"] else []
        return Neuron(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            concepts=concepts,
            created_at=row["created_at"],
            accessed_at=row["accessed_at"],
            access_count=row["access_count"],
        )

    # --- Synapse CRUD ---

    def upsert_synapse(self, synapse: Synapse) -> Synapse:
        self.conn.execute(
            """
            INSERT INTO synapses (source_id, target_id, weight, traversal_count, last_traversed)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_id, target_id) DO UPDATE SET
                weight = excluded.weight,
                traversal_count = traversal_count + excluded.traversal_count,
                last_traversed = excluded.last_traversed
            """,
            (
                synapse.source_id,
                synapse.target_id,
                synapse.weight,
                synapse.traversal_count,
                synapse.last_traversed,
            ),
        )
        self.conn.commit()
        return synapse

    def get_synapse(self, source_id: str, target_id: str) -> Optional[Synapse]:
        row = self.conn.execute(
            "SELECT * FROM synapses WHERE source_id = ? AND target_id = ?",
            (source_id, target_id),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_synapse(row)

    def get_synapses_for_neuron(self, neuron_id: str) -> list[Synapse]:
        rows = self.conn.execute(
            """
            SELECT * FROM synapses
            WHERE source_id = ? OR target_id = ?
            ORDER BY weight DESC
            """,
            (neuron_id, neuron_id),
        ).fetchall()
        return [self._row_to_synapse(r) for r in rows]

    def get_outgoing_synapses(self, neuron_id: str) -> list[Synapse]:
        rows = self.conn.execute(
            "SELECT * FROM synapses WHERE source_id = ? ORDER BY weight DESC",
            (neuron_id,),
        ).fetchall()
        return [self._row_to_synapse(r) for r in rows]

    def get_all_synapses(self) -> list[Synapse]:
        rows = self.conn.execute("SELECT * FROM synapses").fetchall()
        return [self._row_to_synapse(r) for r in rows]

    def update_synapse_weight(self, source_id: str, target_id: str, weight: float) -> None:
        self.conn.execute(
            "UPDATE synapses SET weight = ? WHERE source_id = ? AND target_id = ?",
            (weight, source_id, target_id),
        )
        self.conn.commit()

    def record_traversal(self, source_id: str, target_id: str) -> None:
        now = time.time()
        self.conn.execute(
            """
            UPDATE synapses
            SET traversal_count = traversal_count + 1, last_traversed = ?
            WHERE source_id = ? AND target_id = ?
            """,
            (now, source_id, target_id),
        )
        self.conn.commit()

    def _row_to_synapse(self, row: sqlite3.Row) -> Synapse:
        return Synapse(
            source_id=row["source_id"],
            target_id=row["target_id"],
            weight=row["weight"],
            traversal_count=row["traversal_count"],
            last_traversed=row["last_traversed"],
        )

    # --- Stats helpers ---

    def count_neurons(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM neurons").fetchone()[0]

    def count_synapses(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM synapses").fetchone()[0]

    def get_most_connected_neurons(self, limit: int = 5) -> list[tuple[str, int]]:
        """Return (neuron_id, degree) tuples ordered by degree descending."""
        rows = self.conn.execute(
            """
            SELECT id,
                (SELECT COUNT(*) FROM synapses WHERE source_id = n.id OR target_id = n.id) AS degree
            FROM neurons n
            ORDER BY degree DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def get_concept_distribution(self) -> dict[str, int]:
        """Return a frequency map of all concepts across all neurons."""
        rows = self.conn.execute("SELECT concepts FROM neurons WHERE concepts IS NOT NULL").fetchall()
        dist: dict[str, int] = {}
        for row in rows:
            for concept in json.loads(row[0]):
                dist[concept] = dist.get(concept, 0) + 1
        return dist
