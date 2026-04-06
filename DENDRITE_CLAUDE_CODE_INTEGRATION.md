# Dendrite x Claude Code Integration

## Table of Contents

1. [What is Dendrite](#what-is-dendrite)
2. [Architecture Overview](#architecture-overview)
3. [How Dendrite Works](#how-dendrite-works)
4. [Integration Architecture](#integration-architecture)
5. [Benefits to Claude Code](#benefits-to-claude-code)
6. [MCP Server Integration](#mcp-server-integration)
7. [Hook Integration](#hook-integration)
8. [Skill Integration](#skill-integration)
9. [Comparison: Dendrite vs Built-in Memory](#comparison-dendrite-vs-built-in-memory)
10. [Known Limitations & Roadmap](#known-limitations--roadmap)

---

## What is Dendrite

Dendrite is a **neural-inspired knowledge synthesis system** that organizes information into an interconnected graph of neurons (knowledge fragments) linked by synaptic connections scored by semantic similarity. It provides Claude Code with a persistent, self-organizing knowledge layer that grows stronger with use.

**Core metaphor:** Every piece of knowledge is a neuron. When two neurons share concepts, a synapse forms between them with strength proportional to their similarity. When you query the network, relevant neurons activate and spread activation through connected paths — just like biological neural networks.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code Session                       │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │  Hooks   │  │  Skills  │  │   MCP    │  │  CLAUDE.md     │  │
│  │ (events) │  │ (/cmds)  │  │ (tools)  │  │  (context)     │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────────────┘  │
│       │              │              │                             │
│       └──────────────┴──────────────┘                            │
│                      │                                           │
│              ┌───────▼───────┐                                   │
│              │  Dendrite MCP │                                   │
│              │    Server     │                                   │
│              └───────┬───────┘                                   │
│                      │                                           │
└──────────────────────┼───────────────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  Dendrite Core  │
              │                 │
              │  ┌───────────┐  │
              │  │ Analyzer  │  │   TF-IDF vectorization
              │  │ (NLP)     │  │   Concept extraction
              │  └─────┬─────┘  │   Cosine similarity
              │        │        │
              │  ┌─────▼─────┐  │
              │  │  Storage  │  │   SQLite (WAL mode)
              │  │  (CRUD)   │  │   Neurons + Synapses
              │  └─────┬─────┘  │
              │        │        │
              │  ┌─────▼─────┐  │
              │  │  Synapse   │  │   Activation spreading
              │  │  Engine    │  │   Consolidation
              │  └───────────┘  │   Decay
              │                 │
              └─────────────────┘
```

---

## How Dendrite Works

### 1. Knowledge Storage (Neurons)

Each piece of knowledge is stored as a **neuron** with:
- Unique ID (8-char hex)
- Content (the knowledge text)
- Optional title
- Auto-extracted concepts (top terms by TF-IDF score)
- Access metadata (created_at, accessed_at, access_count)

```bash
dendrite add "Claude Code hooks run deterministic commands at lifecycle events"
# → Neuron created with concepts: [hooks, deterministic, commands, lifecycle, events]
```

### 2. Automatic Connection (Synapses)

When neurons are added and reindexed, dendrite computes **TF-IDF cosine similarity** between all pairs. Pairs above the similarity threshold (0.1) form synaptic connections with weight equal to their similarity score.

```
"Claude Code hooks run at lifecycle events"  ──[0.73]──  "Hooks execute on SessionStart"
                                              ──[0.45]──  "MCP servers provide tools"
                                              ──[0.12]──  "Skills are invocable workflows"
```

### 3. Neural Query (Activation Spreading)

Querying the network works in three stages:

1. **Vectorize** the query against the corpus using TF-IDF
2. **Find** the top-K most similar neurons (seeds)
3. **Spread** activation from seeds through synaptic connections via BFS

Each hop through the graph attenuates the signal by `weight × 0.7` (hop decay). This means strongly connected, nearby neurons get high activation scores while distant, weakly connected ones fade out.

```bash
dendrite ask "how do hooks work?"
# → Activates "hooks" neurons → spreads to connected "lifecycle" → "SessionStart" → etc.
```

### 4. Hebbian Learning (Consolidation)

"Neurons that fire together, wire together." When a query traverses certain paths, those edges are **consolidated** — their weights get boosted by 1.1x (capped at 1.0). This means frequently useful connections grow stronger over time.

### 5. Temporal Decay

Unused connections weaken over time: `weight × 0.95^days`. This prevents stale connections from dominating and ensures the network reflects current relevance. Extremely decayed synapses (< 0.01) could be pruned in future versions.

---

## Integration Architecture

Dendrite integrates with Claude Code through **four layers**:

### Layer 1: MCP Server (Primary — Tool Access)

An MCP server exposes dendrite operations as tools Claude can call directly:

| Tool | Description | When Used |
|------|-------------|-----------|
| `dendrite_add` | Store new knowledge | After learning something worth persisting |
| `dendrite_ask` | Semantic search with activation spreading | When recalling related knowledge |
| `dendrite_explore` | BFS from a concept | When exploring a topic area |
| `dendrite_stats` | Network statistics | When assessing knowledge coverage |
| `dendrite_consolidate` | Strengthen traversed paths | Periodically to maintain the network |
| `dendrite_reindex` | Rebuild all connections | After batch additions |

### Layer 2: Hooks (Automatic — Event-Driven)

Hooks trigger dendrite operations at key lifecycle points:

| Hook | Action | Purpose |
|------|--------|---------|
| `SessionStart` | `dendrite ask "<project context>"` | Pre-load relevant knowledge |
| `PostToolUse(Edit\|Write)` | `dendrite add "<summary of change>"` | Auto-capture knowledge from edits |
| `PreCompact` | `dendrite add "<session learnings>"` | Persist insights before context loss |
| `Stop` | `dendrite consolidate` | Strengthen paths used in this session |

### Layer 3: Skills (Explicit — User Commands)

Custom slash commands for direct interaction:

| Skill | Usage | Action |
|-------|-------|--------|
| `/remember` | `/remember "API rate limits are 100/min"` | Add neuron with the given knowledge |
| `/recall` | `/recall "rate limits"` | Search dendrite and inject context |
| `/synthesize` | `/synthesize "authentication"` | Explore concept, generate summary |
| `/knowledge` | `/knowledge` | Show network stats and top concepts |

### Layer 4: CLAUDE.md Augmentation (Context — Dynamic)

A hook can inject dendrite-sourced context into CLAUDE.md dynamically:

```bash
# SessionStart hook: inject relevant knowledge
dendrite ask "$(basename $PWD)" --json | jq -r '.[0:3] | .[].content' >> .claude/rules/dendrite-context.md
```

---

## Benefits to Claude Code

### 1. Associative Memory (vs Flat File Memory)

**Claude Code's built-in memory** is a flat file system: `MEMORY.md` index + individual `.md` files. It requires manual organization, linear search, and explicit retrieval.

**Dendrite** is a **graph**. Knowledge self-organizes through semantic similarity. Querying one concept activates related concepts automatically — you don't need to know what file the knowledge is in.

| Scenario | Flat Memory | Dendrite |
|----------|------------|----------|
| "What do I know about auth?" | Search MEMORY.md for "auth" keyword | `dendrite ask "auth"` → activates auth → spreads to session tokens → spreads to JWT → spreads to middleware |
| Adding knowledge | Decide which file, update index | `dendrite add "..."` → auto-connected to related neurons |
| Stale knowledge | Manual cleanup | Automatic decay weakens unused connections |
| Cross-topic discovery | Manual cross-referencing | Activation spreading finds non-obvious connections |

### 2. Self-Strengthening Knowledge

Traditional memory is static — what you write is what you get. Dendrite's consolidation means **frequently accessed knowledge paths become stronger**. The system literally learns what's important from usage patterns.

**Example:** If Claude repeatedly queries "deployment" and the path goes deployment → Docker → ECS → ALB, those connections strengthen. Next time, querying "deployment" immediately surfaces the full infrastructure context.

### 3. Organic Knowledge Decay

Built-in memory has no notion of staleness. Old entries persist forever unless manually deleted. Dendrite applies **temporal decay** — connections weaken over time unless reinforced through use. This means:

- Yesterday's hotfix context naturally fades
- Core architectural knowledge stays strong (because it's queried often)
- No manual cleanup needed

### 4. Cross-Session Knowledge Transfer

Each Claude Code session starts with limited context. Dendrite provides a **persistent knowledge substrate** that spans sessions:

```
Session 1: Learn about caching strategy → dendrite stores it
Session 2: Work on API → query "performance" → caching strategy surfaces
Session 3: Debug slow queries → "caching" neurons are already strong
```

### 5. Multi-Agent Knowledge Sharing

In a Gas Town multi-agent setup, dendrite provides a **shared knowledge graph**:

- **Polecats** (workers) add knowledge as they implement features
- **Witnesses** can query the graph to understand system state
- **Mayor** has full network visibility for coordination
- All agents build on each other's knowledge

### 6. Concept Discovery

Because dendrite uses activation spreading rather than keyword matching, it can surface **non-obvious connections**:

```bash
dendrite ask "why is the API slow?"
# May activate: "API" → "middleware" → "auth validation" → "database queries"
#                                                          → "connection pooling"
# Revealing that auth middleware's database queries are the bottleneck
```

This is something flat keyword search cannot do.

### 7. Quantifiable Knowledge Network

`dendrite stats` provides concrete metrics about knowledge coverage:

```json
{
  "neuron_count": 150,
  "synapse_count": 420,
  "avg_degree": 5.6,
  "most_connected": [
    {"title": "API Architecture", "connections": 23},
    {"title": "Auth Flow", "connections": 18}
  ],
  "top_concepts": [["api", 34], ["auth", 28], ["database", 22]]
}
```

This lets you see knowledge gaps, over-documented areas, and the network's overall health.

---

## MCP Server Integration

### Architecture

The MCP server wraps dendrite's CLI as a stdio-based MCP server that Claude Code can call directly.

### Configuration

Add to `.claude/settings.json` or `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "dendrite": {
      "type": "stdio",
      "command": "python3",
      "args": ["/path/to/dendrite_mcp_server.py"],
      "environmentVariables": {
        "DENDRITE_DB": "/path/to/project.dendrite.db"
      },
      "alwaysAllow": [
        "dendrite_ask",
        "dendrite_explore",
        "dendrite_stats"
      ]
    }
  }
}
```

### MCP Server Implementation

See `dendrite_mcp_server.py` for the full implementation. The server exposes these tools:

```python
# Tools provided to Claude Code:
dendrite_add(content, title=None)     # Store knowledge
dendrite_ask(query, top_k=5)          # Semantic search + activation
dendrite_explore(concept, depth=3)     # Concept exploration
dendrite_stats()                       # Network statistics
dendrite_consolidate(decay_days=0)     # Strengthen & maintain
dendrite_reindex()                     # Rebuild connections
dendrite_show(neuron_id)               # Get specific neuron
dendrite_list()                        # List all neurons
```

---

## Hook Integration

### SessionStart — Context Priming

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "dendrite ask \"$(basename $PWD)\" --json --top 3 | python3 -c \"import sys,json; [print(f'[dendrite] {r[\"title\"]}: {r[\"content\"][:100]}') for r in json.load(sys.stdin)]\" 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

### PostToolUse — Auto-Capture

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "echo '{\"learned\": true}'"
          }
        ]
      }
    ]
  }
}
```

### Stop — Session Consolidation

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "dendrite consolidate --json 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

---

## Skill Integration

### /remember Skill

```yaml
---
name: remember
description: Store knowledge in dendrite's neural network
argument-hint: "<knowledge to remember>"
allowed-tools: Bash
user-invocable: true
---

Store the following knowledge in dendrite:

```bash
dendrite add "$ARGUMENTS" --json
```

Confirm what was stored and what connections were made.
```

### /recall Skill

```yaml
---
name: recall
description: Search dendrite for relevant knowledge
argument-hint: "<query>"
allowed-tools: Bash
user-invocable: true
---

Search dendrite for knowledge related to: $ARGUMENTS

```bash
dendrite ask "$ARGUMENTS" --json --top 5
```

Present the results clearly, showing confidence scores and activation paths.
```

### /synthesize Skill

```yaml
---
name: synthesize
description: Explore a concept in dendrite and synthesize findings
argument-hint: "<concept>"
allowed-tools: Bash
user-invocable: true
---

Explore the concept "$ARGUMENTS" in dendrite's knowledge network:

```bash
dendrite explore "$ARGUMENTS" --json --depth 3
```

Synthesize the connected neurons into a coherent summary.
```

---

## Comparison: Dendrite vs Built-in Memory

| Feature | Claude Code Memory | Dendrite |
|---------|-------------------|----------|
| **Structure** | Flat files (MEMORY.md + topic files) | Graph (neurons + weighted synapses) |
| **Organization** | Manual (user decides file structure) | Automatic (TF-IDF similarity) |
| **Search** | Linear keyword match on MEMORY.md index | Semantic similarity + activation spreading |
| **Discovery** | Only explicit cross-references | Automatic through graph traversal |
| **Staleness** | Manual cleanup | Automatic temporal decay |
| **Learning** | Static once written | Consolidation strengthens used paths |
| **Multi-session** | Yes (persistent files) | Yes (persistent SQLite) |
| **Multi-agent** | Separate per agent | Shared graph across agents |
| **Overhead** | ~0 (just file reads) | Minimal (SQLite + numpy) |
| **Capacity** | ~200 lines in MEMORY.md | Thousands of neurons, quadratic synapses |
| **Best for** | Rules, preferences, workflow guidance | Accumulated technical knowledge, patterns |

### When to use which

- **Use Claude Code Memory for:** User preferences, coding standards, project rules, workflow instructions. Things that are prescriptive and stable.
- **Use Dendrite for:** Accumulated knowledge, learned patterns, cross-cutting insights, debugging history, architectural understanding. Things that emerge from work and evolve over time.

**They complement each other.** Memory tells Claude *how* to work. Dendrite tells Claude *what it knows*.

---

## Known Limitations & Roadmap

### Current Limitations

1. **O(n^2) reindex** — Full TF-IDF reindex is quadratic in neuron count. Incremental updates planned.
2. **Reindex destroys traversal history** — `delete_all_synapses()` wipes consolidation data. Needs traversal-preserving reindex.
3. **No synapse pruning** — Decayed synapses approach zero weight but are never removed. Cleanup threshold planned.
4. **ASCII-only tokenizer** — Unicode content loses information. Multi-language tokenizer planned.
5. **No foreign key constraints** — Synapses can reference deleted neurons. Schema migration needed.
6. **Single-process writes** — SQLite WAL allows concurrent reads but only one writer at a time.

### Roadmap

- **Incremental reindex** — Only recompute similarity for new/changed neurons
- **Synapse pruning** — Remove synapses below configurable weight threshold
- **Embedding upgrade** — Replace TF-IDF with sentence transformers for better semantic similarity
- **Dendrite MCP server** — Full MCP server for native Claude Code tool integration
- **Webhook notifications** — Notify when knowledge graph changes significantly
- **Graph export** — Export to standard graph formats (DOT, GEXF) for visualization
- **Neuron versioning** — Track content changes over time
