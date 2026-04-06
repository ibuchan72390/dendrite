# Dendrite

Neural-inspired knowledge synthesis engine. Each note is a **neuron**; shared concepts create **synaptic connections** scored by TF-IDF cosine similarity. Querying activates neurons and spreads through high-strength connections. Consolidation strengthens frequently traversed paths; decay weakens unused links over time.

Dendrite works standalone as a CLI/API, and as a **knowledge layer for Claude Code** — giving Claude persistent, self-organizing memory that grows stronger with use.

## Documentation

- **[Claude Code Integration Guide](./CLAUDE_CODE_GUIDE.md)** — Setup instructions and practical patterns for using Dendrite with Claude Code (MCP server, hooks, skills)
- **[Architecture & Technical Reference](./DENDRITE_CLAUDE_CODE_INTEGRATION.md)** — Deep dive on how Dendrite works, integration architecture, and comparison with built-in memory
- **[Demo Notes](./DEMO_NOTES.md)** — Presenter notes and demo walkthrough script

## Install

```bash
pip install -e ".[dev]"
```

## Usage

```bash
dendrite add "The mitochondria is the powerhouse of the cell"
dendrite add "Cells produce ATP through oxidative phosphorylation" --title "ATP Production"
dendrite ask "how does the brain get energy?"
dendrite explore "energy"
dendrite graph
dendrite stats
dendrite consolidate
dendrite list
dendrite show <id>
```

## Run tests

```bash
pytest -v
```

## Docker / API

The Rust HTTP API defaults to port **8181** (avoids conflict with Gas Town dashboard on 8080).

### Starting the API

```bash
# Start the API (default port 8181)
docker compose up

# Use a custom port
API_PORT=9090 docker compose up

# Check health
curl http://localhost:8181/health
```

**Port forwarding in container environments:** When running inside a Docker
network or VM, bind to the host explicitly:

```bash
# Map container port to host (already done by docker-compose)
# Host: http://localhost:8181  →  Container: 0.0.0.0:8181

# Override host-side port only (container still listens on 8181 internally)
API_PORT=9090 docker compose up   # access via localhost:9090
```

The `PORT` environment variable controls which port the API listens on inside
the container. `API_PORT` in docker-compose sets both the host-side mapping and
the container's `PORT` together, keeping them in sync.

### API Endpoints

All endpoints return JSON.

#### `GET /health`

Returns `{"status": "ok"}` when the service is up.

```bash
curl http://localhost:8181/health
```

#### `POST /neurons`

Add a new neuron (knowledge fragment).

```bash
curl -X POST http://localhost:8181/neurons \
  -H "Content-Type: application/json" \
  -d '{"content": "The mitochondria is the powerhouse of the cell"}'

# With an optional title
curl -X POST http://localhost:8181/neurons \
  -H "Content-Type: application/json" \
  -d '{"content": "Cells produce ATP through oxidative phosphorylation", "title": "ATP Production"}'
```

#### `GET /neurons`

List all neurons.

```bash
curl http://localhost:8181/neurons
```

#### `GET /neurons/:id`

Get a specific neuron by ID.

```bash
curl http://localhost:8181/neurons/42
```

#### `GET /search?q=...&top_k=N`

Semantic search across neurons (wraps `dendrite ask`).

| Query param | Required | Description |
|-------------|----------|-------------|
| `q`         | yes      | Search query |
| `top_k`     | no       | Number of results to return (default: CLI default) |

```bash
curl "http://localhost:8181/search?q=how+does+the+brain+get+energy"

# Limit results
curl "http://localhost:8181/search?q=energy&top_k=5"
```

#### `GET /explore/:concept`

Activate a concept and spread through synaptic connections (wraps `dendrite explore`).

```bash
curl http://localhost:8181/explore/energy
```

#### `GET /graph`

Return the full neuron graph (nodes and weighted edges).

```bash
curl http://localhost:8181/graph
```

#### `GET /stats`

Return aggregate statistics about the knowledge base.

```bash
curl http://localhost:8181/stats
```

#### `POST /consolidate`

Trigger consolidation: strengthens frequently traversed paths, decays unused links.

```bash
curl -X POST http://localhost:8181/consolidate
```

### Dev Overlay

The dev overlay mounts live Python source into the container so Python changes
take effect without rebuilding the image. Only the Rust binary needs a rebuild
when `api/src/` changes.

```bash
# Start with live Python reload (no rebuild on Python edits)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Verbose Rust tracing enabled automatically in dev mode
# RUST_LOG=debug,dendrite_api=trace
```
