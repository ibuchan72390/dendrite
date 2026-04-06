# Using Dendrite with Claude Code

Dendrite gives Claude Code a **graph-based knowledge layer** that persists across sessions, self-organizes through use, and surfaces connections that flat-file memory can't find. This guide walks you through setting it up and getting real value from it.

## Why Dendrite in Claude Code?

Claude Code already has a built-in memory system (flat `.md` files in `~/.claude/projects/`). It works, but it has limits:

- **You organize it.** You decide which file to put knowledge in, and you maintain the index.
- **Keyword search only.** If you search for "auth", you won't find the note you titled "session tokens."
- **Nothing fades.** Last month's hotfix notes sit next to core architecture docs with equal weight.
- **No cross-pollination.** Knowledge about caching and knowledge about API performance don't know about each other unless you manually link them.

Dendrite solves all four:

| Problem | Dendrite's Answer |
|---------|-------------------|
| Manual organization | Auto-connects knowledge by semantic similarity |
| Keyword-only search | TF-IDF + activation spreading finds related concepts across hops |
| No staleness signal | Temporal decay weakens unused connections; consolidation strengthens active ones |
| No cross-pollination | Graph traversal discovers non-obvious connections automatically |

**They're complementary.** Use Claude Code's memory for rules and preferences ("always use 2-space indent"). Use Dendrite for accumulated knowledge ("the auth middleware hits the DB twice per request").

---

## Setup

### Step 1: Install Dendrite

```bash
git clone https://github.com/ibuchan72390/dendrite.git
cd dendrite
pip install -e ".[dev]"
```

Verify:
```bash
dendrite stats
# → neuron_count: 0, synapse_count: 0
```

### Step 2: Choose Your Integration Level

Dendrite plugs into Claude Code at three levels. Pick what fits your workflow — you can always add more later.

| Level | What It Does | Effort |
|-------|-------------|--------|
| **Skills only** | `/remember`, `/recall` slash commands | Copy 4 folders |
| **Skills + Hooks** | Auto-consolidate on session end, context priming on start | Edit settings.json |
| **Full MCP** | Claude calls dendrite tools directly, no slash commands needed | Add MCP server config |

---

## Level 1: Skills (5 minutes)

Copy the skill definitions into your project:

```bash
# From the dendrite repo
cp -r .claude/skills/remember  /path/to/your/project/.claude/skills/
cp -r .claude/skills/recall    /path/to/your/project/.claude/skills/
cp -r .claude/skills/synthesize /path/to/your/project/.claude/skills/
cp -r .claude/skills/knowledge /path/to/your/project/.claude/skills/
```

Or copy them to `~/.claude/skills/` for global access across all projects.

Now in any Claude Code session you can:

```
/remember "The payments API rate-limits at 100 req/min per merchant"
```
Claude stores it as a neuron, extracts concepts (`payments`, `api`, `rate`, `limits`, `merchant`), and auto-connects it to related knowledge.

```
/recall "rate limits"
```
Claude searches the graph with activation spreading, returning the most relevant neurons plus how they connect.

```
/synthesize "authentication"
```
Claude explores all knowledge connected to "authentication" within 3 hops and writes a synthesis.

```
/knowledge
```
Shows your knowledge network's health: neuron count, connections, top concepts, hub neurons.

### What this looks like in practice

```
You:     /remember "Redis cache TTL is 300s for product listings, 60s for cart"

Claude:  Stored in dendrite:
         ID: a3f8c912
         Concepts: redis, cache, ttl, product, listings, cart
         Connections created: 2 (linked to "API response caching" and "Cart service architecture")

You:     /recall "why is checkout slow?"

Claude:  Top results from dendrite:
         #1 "Cart service architecture" (confidence: 0.34)
            → activation path: Cart → Redis cache TTL → Product listings
         #2 "Database connection pooling" (confidence: 0.28)
            → activation path: Database → Cart service → Checkout flow
         
         Based on the knowledge graph, the checkout slowness likely traces 
         through the cart service. The 60s Redis TTL for cart data means 
         cache misses are more frequent than for product listings (300s TTL).
```

The key insight: you asked about "checkout" and dendrite found "Redis cache TTL" through graph traversal. A keyword search for "checkout" would have missed it entirely.

---

## Level 2: Skills + Hooks (10 minutes)

Add these to your project's `.claude/settings.json` (or `~/.claude/settings.json` for global):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "dendrite ask \"$(basename $PWD)\" --json --top 3 2>/dev/null | python3 -c \"import sys,json; data=json.load(sys.stdin); [print(f'[dendrite] {r[\\\"title\\\"]}: {r[\\\"content\\\"][:120]}') for r in data]\" 2>/dev/null || true"
          }
        ]
      }
    ],
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

**What this does:**

- **SessionStart**: When you open a Claude Code session, dendrite automatically searches for knowledge related to your current project directory and injects the top 3 results as context. Claude starts every session with relevant background.
- **Stop**: When a session ends, dendrite runs consolidation — strengthening the synaptic paths that were traversed during the session. Knowledge that was actually useful becomes easier to find next time.

Over time, this creates a flywheel: use dendrite → knowledge strengthens → better results next session → more use.

### Optional: PreCompact hook

If you have long sessions that hit context compaction, add this to preserve knowledge before it's lost:

```json
{
  "hooks": {
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Session compacting — consolidating dendrite knowledge' && dendrite consolidate --json 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

---

## Level 3: Full MCP Server (15 minutes)

This is the most powerful integration. Instead of slash commands, Claude calls dendrite tools directly — deciding on its own when to store or retrieve knowledge.

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "dendrite": {
      "type": "stdio",
      "command": "python3",
      "args": ["/absolute/path/to/dendrite/dendrite_mcp_server.py"],
      "environmentVariables": {
        "DENDRITE_DB": "/absolute/path/to/your-project.dendrite.db"
      },
      "alwaysAllow": [
        "dendrite_ask",
        "dendrite_explore",
        "dendrite_stats",
        "dendrite_list",
        "dendrite_show"
      ]
    }
  }
}
```

**Important:** Use absolute paths. The `alwaysAllow` list lets Claude query dendrite without asking for permission each time. Write operations (`dendrite_add`, `dendrite_consolidate`, `dendrite_reindex`) still require approval.

### Available MCP Tools

| Tool | What Claude Does With It |
|------|-------------------------|
| `dendrite_add` | Stores knowledge it learns during a session |
| `dendrite_ask` | Recalls relevant knowledge when working on a problem |
| `dendrite_explore` | Maps out everything known about a concept area |
| `dendrite_show` | Looks up a specific neuron by ID |
| `dendrite_list` | Reviews all stored knowledge |
| `dendrite_stats` | Checks network health and coverage |
| `dendrite_consolidate` | Strengthens frequently-used knowledge paths |
| `dendrite_reindex` | Rebuilds all connections after bulk additions |

### What this looks like in practice

With MCP, you don't need to explicitly call `/remember` or `/recall`. Claude uses the tools naturally:

```
You:     Can you figure out why the webhook handler is timing out?

Claude:  [calls dendrite_ask("webhook timeout handler")]
         
         Found relevant context in dendrite:
         - "Webhook handler retries 3x with exponential backoff" (confidence: 0.41)
         - "External payment provider has 30s timeout" (confidence: 0.28)
           → activation path: payment provider → webhook → retry logic
         
         Based on the knowledge graph, the timeout is likely hitting the 
         payment provider's 30s limit combined with the 3x retry. Let me 
         check the handler code...
         
         [reads the file, finds the issue]
         
         [calls dendrite_add("Webhook handler fix: payment provider timeout 
         was 30s but handler retry backoff could exceed it. Fixed by capping 
         total retry duration to 25s.")]
         
         Stored the fix context for future reference. The knowledge graph 
         now connects this to the existing payment provider and retry logic neurons.
```

Claude is building institutional knowledge as it works. The next time anyone asks about webhooks, timeouts, or the payment provider, this context surfaces automatically.

---

## Database Per Project vs Global

You have two strategies:

**Per-project database** (recommended for most teams):
```bash
export DENDRITE_DB=/path/to/project/.dendrite.db
```
Each project builds its own knowledge graph. Context stays relevant and focused.

**Global database** (good for solo developers):
```bash
export DENDRITE_DB=~/.dendrite.db
```
One graph across all projects. Cross-project insights emerge (e.g., a caching pattern you used in Project A surfaces when you hit a similar problem in Project B).

---

## Practical Patterns

### Pattern 1: Onboarding Accelerator

When a new team member starts on a codebase, seed dendrite with architectural knowledge:

```bash
dendrite add "Auth flow: JWT issued by /auth/login, verified by middleware in src/middleware/auth.ts, tokens expire after 1h" --title "Auth Flow"
dendrite add "Database: PostgreSQL 15, migrations in db/migrations/, connection pool max 20" --title "Database Setup"
dendrite add "Deployment: GitHub Actions → ECR → ECS Fargate, staging auto-deploys on merge to main" --title "Deployment Pipeline"
dendrite reindex
```

Now every new Claude Code session starts with relevant context from the knowledge graph. The team member can ask Claude about any aspect, and dendrite surfaces related context they didn't know to ask about.

### Pattern 2: Debugging Memory

After resolving tricky bugs, store the diagnosis:

```
/remember "OrderService timeout was caused by N+1 query in getOrderItems — fixed with eager loading in PR #847"
```

Six months later, when a similar timeout appears:

```
/recall "service timeout"
```

Dendrite surfaces the OrderService fix because "timeout" and "service" activate the right neurons. You've preserved debugging intuition as institutional knowledge.

### Pattern 3: Architecture Decision Records

Store decisions with their reasoning:

```
/remember "Chose Redis over Memcached for session storage because we need pub/sub for real-time invalidation across pods"
/remember "API versioning uses URL path (/v1/, /v2/) not headers, because our API gateway doesn't support header-based routing"
```

When someone later asks "why don't we use header-based API versioning?", dendrite surfaces the decision and the constraint that drove it.

### Pattern 4: Cross-Session Continuity

Working on a multi-day feature:

**Day 1:**
```
/remember "Refactoring payment module: splitting PaymentService into PaymentProcessor and PaymentValidator, started with processor"
```

**Day 2 (new session, SessionStart hook fires):**
```
[dendrite] Payment module refactor: splitting PaymentService into PaymentProcessor and PaymentValidator...
```

Claude picks up where you left off without you having to re-explain the context.

---

## Maintaining the Knowledge Graph

### Periodic maintenance

Run consolidation with decay to keep the graph healthy:

```bash
# Strengthen used paths, decay unused ones (7 days)
dendrite consolidate --decay-days 7

# Check network health
dendrite stats
```

### Reindex after bulk additions

If you've added many neurons without querying in between:

```bash
dendrite reindex
```

This rebuilds all synaptic connections based on current TF-IDF similarity.

### Monitor network health

```bash
dendrite stats --json
```

Watch for:
- **Low avg_degree (< 1.0):** Knowledge is fragmented. Add more related content or reindex.
- **High neuron count, low synapse count:** Content is too diverse. Consider narrowing the scope.
- **Top concepts dominated by generic terms:** Neurons may need more specific content.

---

## Troubleshooting

**"dendrite: command not found"**
```bash
pip install -e /path/to/dendrite
```

**MCP server not connecting**
- Verify the path in `settings.json` is absolute
- Test manually: `DENDRITE_DB=/tmp/test.db python3 /path/to/dendrite_mcp_server.py`
- Check Claude Code logs for MCP connection errors

**Skills not appearing in `/` menu**
- Skills must be in `.claude/skills/<name>/SKILL.md`
- The `user-invocable: true` frontmatter field must be set
- Restart Claude Code after adding skills

**Empty results from queries**
- Run `dendrite stats` to verify neurons exist
- Run `dendrite reindex` to rebuild connections
- Check that content has enough meaningful terms (stopwords and very short words are filtered)

**Hooks not firing**
- Verify `.claude/settings.json` syntax (JSON must be valid)
- Hooks fail silently by default — add logging: `command": "dendrite consolidate --json 2>>/tmp/dendrite-hook.log || true"`
- SessionStart hooks only fire on `startup`, not `resume` — check the matcher

---

## Further Reading

- [DENDRITE_CLAUDE_CODE_INTEGRATION.md](./DENDRITE_CLAUDE_CODE_INTEGRATION.md) — Deep technical architecture, algorithm details, and full comparison tables
- [README.md](./README.md) — CLI usage, API endpoints, Docker setup
- [DEMO_NOTES.md](./DEMO_NOTES.md) — Demo script and presenter notes
