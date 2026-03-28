# Dendrite

Neural-inspired knowledge synthesis CLI. Each note is a **neuron**; shared concepts create **synaptic connections** scored by TF-IDF cosine similarity. Querying activates neurons and spreads through high-strength connections. Consolidation strengthens frequently traversed paths; decay weakens unused links over time.

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
