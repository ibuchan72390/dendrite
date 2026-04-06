#!/usr/bin/env python3
"""
Seed the dendrite database with demo data.

This creates a compelling knowledge graph about Claude Code's architecture
that demonstrates:
  - Automatic concept extraction
  - Synapse formation via TF-IDF similarity
  - Activation spreading across connected neurons
  - Consolidation strengthening frequently used paths

Usage:
    python3 scripts/seed-demo.py                     # uses ~/.dendrite.db
    DENDRITE_DB=/tmp/demo.db python3 scripts/seed-demo.py
"""

import os
import sys

# Ensure dendrite is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dendrite.core import Dendrite

DB_PATH = os.environ.get("DENDRITE_DB", os.path.expanduser("~/.dendrite.db"))


NEURONS = [
    # Claude Code architecture
    (
        "Claude Code is a CLI tool that gives Claude direct access to your development environment "
        "through tools like Bash, Read, Edit, Write, and Grep. It runs in the terminal and can "
        "autonomously execute multi-step software engineering tasks.",
        "Claude Code Overview",
    ),
    (
        "Hooks are deterministic automation that execute shell commands at specific lifecycle points "
        "in Claude Code sessions. Available events include SessionStart, PreToolUse, PostToolUse, "
        "UserPromptSubmit, Stop, and PreCompact.",
        "Claude Code Hooks",
    ),
    (
        "MCP (Model Context Protocol) servers extend Claude Code with custom tools. They can be "
        "configured as stdio subprocesses, HTTP endpoints, or SSE streams. Claude calls MCP tools "
        "just like built-in tools, with the prefix mcp__servername__toolname.",
        "MCP Server Integration",
    ),
    (
        "Skills are reusable packaged workflows defined in .claude/skills/ directories. Each skill "
        "has a SKILL.md file with YAML frontmatter specifying name, description, allowed tools, and "
        "instructions. Users invoke skills with slash commands like /remember or /deploy.",
        "Claude Code Skills",
    ),
    (
        "Claude Code's memory system uses persistent files in ~/.claude/projects/ to store learned "
        "context across sessions. MEMORY.md serves as an index, with individual topic files loaded "
        "on demand. Memory is flat file-based with linear keyword search.",
        "Claude Code Memory System",
    ),

    # Dendrite architecture
    (
        "Dendrite is a neural-inspired knowledge synthesis system. Each piece of knowledge is stored "
        "as a neuron with unique ID, content, title, and auto-extracted concepts. Neurons are "
        "connected by synapses weighted by TF-IDF cosine similarity.",
        "Dendrite Core Architecture",
    ),
    (
        "TF-IDF (Term Frequency-Inverse Document Frequency) measures how important a word is to a "
        "document relative to a corpus. Dendrite uses a pure numpy implementation to vectorize "
        "neuron content and compute pairwise cosine similarity for synapse formation.",
        "TF-IDF Analysis Engine",
    ),
    (
        "Activation spreading is a BFS algorithm that propagates signal through the knowledge graph. "
        "Starting from seed neurons found via TF-IDF similarity, activation spreads through synaptic "
        "connections with hop decay of 0.7x per hop. This surfaces non-obvious connections.",
        "Activation Spreading Algorithm",
    ),
    (
        "Consolidation implements Hebbian learning: neurons that fire together wire together. When a "
        "query traverses synaptic paths, those edges get boosted by 1.1x (capped at 1.0). This means "
        "frequently useful knowledge paths grow stronger over time.",
        "Consolidation (Hebbian Learning)",
    ),
    (
        "Temporal decay weakens unused synaptic connections by a factor of 0.95 per day. This prevents "
        "stale knowledge from dominating the network and ensures the graph reflects current relevance. "
        "Combined with consolidation, the network self-organizes around what matters.",
        "Temporal Decay Mechanism",
    ),

    # Integration layer
    (
        "Dendrite integrates with Claude Code through four layers: MCP Server for direct tool access, "
        "Hooks for automatic event-driven operations, Skills for explicit slash commands, and CLAUDE.md "
        "augmentation for dynamic context injection.",
        "Dendrite-Claude Code Integration",
    ),
    (
        "The Dendrite MCP server exposes tools like dendrite_add, dendrite_ask, dendrite_explore, and "
        "dendrite_stats. Claude Code can call these tools directly during conversations to store and "
        "retrieve knowledge from the graph.",
        "Dendrite MCP Server",
    ),
    (
        "SessionStart hooks can query Dendrite to pre-load relevant context when a new Claude Code "
        "session begins. Stop hooks trigger consolidation to strengthen paths used during the session. "
        "This creates an automatic knowledge lifecycle.",
        "Hook-Based Knowledge Lifecycle",
    ),

    # Use cases
    (
        "In a multi-agent system like Gas Town, Dendrite provides a shared knowledge substrate. "
        "Polecats store implementation knowledge, Witnesses query it for system state, and the Mayor "
        "has full network visibility for coordination. All agents build on each other's knowledge.",
        "Multi-Agent Knowledge Sharing",
    ),
    (
        "Unlike flat-file memory which requires manual organization and keyword search, Dendrite's "
        "graph structure enables associative recall. Querying one concept activates related concepts "
        "automatically through synapse traversal, surfacing non-obvious connections.",
        "Associative Memory vs Flat Files",
    ),

    # Technical details
    (
        "Dendrite's storage layer uses SQLite in WAL (Write-Ahead Logging) mode for concurrent read "
        "access. The schema has three tables: neurons (id, content, concepts, timestamps), synapses "
        "(source, target, weight, traversal count), and metadata (write counter).",
        "SQLite Storage Layer",
    ),
    (
        "The CLI provides commands: add (store neuron), ask (semantic search), explore (BFS from "
        "concept), graph (ASCII visualization), stats (network metrics), reindex (rebuild synapses), "
        "and consolidate (strengthen used paths). All commands support --json output.",
        "CLI Command Reference",
    ),
    (
        "The HTTP API serves identical endpoints via FastAPI with Swagger docs at /docs. Endpoints "
        "include POST /neurons, GET /search, GET /explore/:concept, GET /graph, GET /stats, and "
        "POST /consolidate. CORS is enabled for browser-based access.",
        "HTTP API Endpoints",
    ),
]


def main():
    print(f"Seeding dendrite database: {DB_PATH}")

    # Remove existing DB for clean demo
    if os.path.exists(DB_PATH) and DB_PATH != ":memory:":
        os.remove(DB_PATH)
        print(f"  Removed existing database")

    d = Dendrite(db_path=DB_PATH)
    try:
        # Add all neurons
        for i, (content, title) in enumerate(NEURONS, 1):
            neuron = d.add(content, title=title)
            print(f"  [{i:2d}/{len(NEURONS)}] Added: {title} ({neuron.id})")

        # Build synaptic connections
        count = d.reindex()
        print(f"\n  Reindex complete: {count} synapses created")

        # Simulate some usage to create traversal history
        print("\n  Simulating queries to build traversal history...")
        queries = [
            "how does Claude Code integrate with external tools?",
            "what is activation spreading?",
            "how does the knowledge graph self-organize?",
            "multi-agent knowledge sharing",
        ]
        for q in queries:
            results = d.ask(q, top_k=3)
            if results:
                top = results[0]
                n = d.get_neuron(top[0].neuron_id)
                title = n.display_title()[:40] if n else "?"
                print(f"    Q: \"{q[:50]}...\"  → {title} (score={top[0].score:.3f})")

        # Consolidate to strengthen traversed paths
        boosted = d.run_consolidation()
        print(f"\n  Consolidation: {boosted} synapses strengthened")

        # Final stats
        stats = d.stats()
        print(f"\n  Final network state:")
        print(f"    Neurons:     {stats.neuron_count}")
        print(f"    Synapses:    {stats.synapse_count}")
        print(f"    Avg degree:  {stats.avg_degree:.2f}")
        print(f"    Top concepts: {', '.join(c for c, _ in sorted(stats.concept_distribution.items(), key=lambda x: -x[1])[:8])}")

        print(f"\n  Demo database ready at: {DB_PATH}")

    finally:
        d.close()


if __name__ == "__main__":
    main()
