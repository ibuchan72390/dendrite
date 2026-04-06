# Dendrite Demo Notes

## Quick Start

```bash
cd /gt/dendrite/crew/forge

# Option 1: Full demo (seed data + API server)
./demo.sh

# Option 2: CLI-only walkthrough (no server needed)
./demo.sh cli

# Option 3: Run tests (160 tests)
./demo.sh test
```

## Prerequisites

Already installed in this environment:
- Python 3.13 with click, rich, numpy, pytest, fastapi, uvicorn
- `dendrite` CLI at `/home/agent/.local/bin/dendrite`
- `pip install -e ".[dev]"` has been run

## Demo Flow (15–20 minutes)

### Act 1: The Problem (2 min)

**Talking point:** Claude Code has a memory system — flat files in `MEMORY.md` + topic files. It works, but:
- **Manual organization** — you decide where knowledge goes
- **Keyword search only** — no semantic understanding
- **No decay** — old info never fades, you clean up manually
- **No cross-pollination** — knowledge doesn't connect itself

*"What if Claude's memory worked like a brain instead of a filing cabinet?"*

---

### Act 2: Meet Dendrite (3 min)

Start the demo database:
```bash
./demo.sh seed
```

**Show the seeded data:**
```bash
dendrite list
dendrite stats
```

**Key callouts:**
- 18 neurons, 24 synapses — all connections formed automatically
- `avg_degree: 2.67` — each neuron connects to ~3 others on average
- Top concepts extracted by TF-IDF: claude, code, dendrite, access...

---

### Act 3: Semantic Search + Activation Spreading (5 min)

**Demo the killer feature — associative recall:**

```bash
dendrite ask "how does knowledge self-organize?"
```

**Walk through the output:**
1. **Confidence scores** — TF-IDF similarity ranks the seeds
2. **Activation paths** — show how the query "spreads" through connections
   - "Temporal Decay" → "Activation Spreading" (connected via graph concepts)
   - This is NOT keyword matching — it's graph traversal

**Try a cross-cutting query:**
```bash
dendrite ask "how do external tools integrate?" --top 3
```

**Show that dendrite finds MCP, Hooks, AND Skills** — all different integration methods — because they're semantically connected.

**Compare with flat memory:** "A keyword search for 'tools' wouldn't find 'hooks' or 'skills'. Dendrite does because the graph connects them."

---

### Act 4: Explore & Visualize (3 min)

**Explore a concept:**
```bash
dendrite explore "hooks" --depth 2
```

**Show the graph:**
```bash
dendrite graph --max-nodes 10
```

**Key callout:** The graph shows hub neurons (high degree = highly connected knowledge) and the strength of connections (bar charts). This is a visual map of knowledge topology.

---

### Act 5: The API (3 min)

**Start the server:**
```bash
./demo.sh api
```

**Open Swagger UI in browser:** `http://localhost:8181/docs`

**Live API calls:**
```bash
# Search
curl "http://localhost:8181/search?q=activation+spreading&top_k=2" | python3 -m json.tool

# Add new knowledge via API
curl -X POST http://localhost:8181/neurons \
  -H "Content-Type: application/json" \
  -d '{"content": "Dendrite can discover non-obvious connections between knowledge areas", "title": "Cross-Domain Discovery"}'

# See the new neuron
curl http://localhost:8181/stats | python3 -m json.tool
```

---

### Act 6: Claude Code Integration (2 min)

**Show the MCP server config** (no live demo needed, just show the config):
```json
{
  "mcpServers": {
    "dendrite": {
      "type": "stdio",
      "command": "python3",
      "args": ["dendrite_mcp_server.py"],
      "environmentVariables": {
        "DENDRITE_DB": "~/.dendrite.db"
      }
    }
  }
}
```

**Explain the four integration layers:**
1. **MCP Server** — Claude calls `dendrite_ask`, `dendrite_add` as tools
2. **Hooks** — SessionStart pre-loads context, Stop consolidates
3. **Skills** — `/remember`, `/recall`, `/synthesize` slash commands
4. **CLAUDE.md** — Dynamic knowledge injection

**Show the skills:**
```bash
cat .claude/skills/remember/SKILL.md
cat .claude/skills/recall/SKILL.md
```

---

### Act 7: Self-Organization Demo (2 min)

**Show consolidation and decay:**
```bash
# Query creates traversals
dendrite ask "how do hooks work with MCP servers?"

# Consolidate strengthens those paths
dendrite consolidate
# → "N synapses strengthened"

# Decay weakens unused paths
dendrite consolidate --decay-days 7
# → Shows both decay + consolidation
```

**Talking point:** "The network literally learns what's important from usage. Frequently accessed paths get stronger. Unused knowledge fades. No manual curation needed."

---

## Key Numbers for the Demo

| Metric | Value |
|--------|-------|
| Test suite | 160 tests, all passing |
| Core modules | 6 (core, storage, analyzer, synapse, cli, display) |
| Lines of production code | ~1,800 |
| Lines of test code | ~1,200 |
| Demo neurons | 18 |
| Auto-created synapses | 24 |
| Dependencies | click, rich, numpy (core) + fastapi, uvicorn (API) |
| API endpoints | 10 (health, CRUD, search, explore, graph, stats, consolidate, reindex) |
| MCP tools | 8 |
| Custom skills | 4 (/remember, /recall, /synthesize, /knowledge) |

## Anticipated Questions

**Q: How does this differ from RAG (Retrieval Augmented Generation)?**
A: RAG is query→retrieve→generate. Dendrite adds a graph layer: query→activate→*spread*→retrieve. The spreading finds connections that pure similarity search misses. Plus consolidation/decay make the retrieval surface evolve with usage.

**Q: Why not use embeddings from an LLM instead of TF-IDF?**
A: TF-IDF is the v0.1 approach — zero external dependencies, runs offline, sub-second. LLM embeddings are on the roadmap and would be a drop-in replacement for the analyzer layer. The graph structure and activation spreading work the same regardless of the similarity backend.

**Q: How does it scale?**
A: Current bottleneck is O(n^2) reindex. For hundreds of neurons this is instant. For thousands, incremental reindex (planned) would only recompute affected pairs. The SQLite backend with WAL mode handles concurrent reads well.

**Q: Can multiple agents share the same graph?**
A: Yes — SQLite WAL allows concurrent readers. Multiple Claude Code sessions can query simultaneously. Writes are serialized but fast (single INSERT). This is the intended multi-agent use case in Gas Town.

**Q: What if I want to use this today?**
A: `pip install -e .` and start using the CLI. The MCP server config drops into `settings.json` and gives Claude direct access to the graph. The skills work immediately when placed in `.claude/skills/`.

## Cleanup

```bash
./demo.sh clean
```
