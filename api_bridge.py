"""
Dendrite API Bridge — HTTP API for the dendrite knowledge graph.

Serves the same endpoints as the Rust API using FastAPI/uvicorn.
No Docker or Rust required — runs directly with Python.

Usage:
    python3 api_bridge.py                          # defaults: port 8181, ~/.dendrite.db
    DENDRITE_DB=/tmp/demo.db python3 api_bridge.py  # custom DB
    PORT=9090 python3 api_bridge.py                 # custom port

Interactive docs at: http://localhost:8181/docs
"""

import json
import os
import subprocess
import sys
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB_PATH = os.environ.get("DENDRITE_DB", os.path.expanduser("~/.dendrite.db"))
PORT = int(os.environ.get("PORT", "8181"))

app = FastAPI(
    title="Dendrite API",
    version="0.1.0",
    description="Neural-inspired knowledge synthesis — semantic search with activation spreading",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def run_dendrite(*args: str) -> dict | list:
    """Run dendrite CLI with --json and return parsed output."""
    env = {**os.environ, "DENDRITE_DB": DB_PATH}
    result = subprocess.run(
        ["dendrite", *args, "--json"],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip() or "dendrite error")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse dendrite output: {e}\n{result.stdout[:200]}")


class AddNeuronRequest(BaseModel):
    content: str
    title: Optional[str] = None


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/neurons", status_code=201)
def add_neuron(req: AddNeuronRequest):
    """Add a new neuron (knowledge fragment) to the network."""
    args = ["add", req.content]
    if req.title:
        args += ["--title", req.title]
    return run_dendrite(*args)


@app.get("/neurons")
def list_neurons():
    """List all neurons in the knowledge graph."""
    return run_dendrite("list")


@app.get("/neurons/{neuron_id}")
def get_neuron(neuron_id: str):
    """Get a specific neuron by ID with its connections."""
    return run_dendrite("show", neuron_id)


@app.get("/search")
def search(q: str = Query(..., description="Search query"), top_k: int = Query(5, ge=1, le=20)):
    """Semantic search with TF-IDF similarity and activation spreading."""
    return run_dendrite("ask", q, "--top", str(top_k))


@app.get("/explore/{concept}")
def explore(concept: str):
    """Explore the network from a concept, following synaptic connections."""
    return run_dendrite("explore", concept)


@app.get("/graph")
def graph():
    """Return the full knowledge graph (nodes and weighted edges)."""
    return run_dendrite("graph")


@app.get("/stats")
def stats():
    """Return network statistics: neuron count, connections, top concepts."""
    return run_dendrite("stats")


@app.post("/consolidate")
def consolidate():
    """Strengthen frequently traversed connections and apply decay."""
    return run_dendrite("consolidate")


@app.post("/reindex")
def reindex():
    """Recompute all TF-IDF similarities and rebuild synaptic connections."""
    return run_dendrite("reindex")


if __name__ == "__main__":
    import uvicorn
    print(f"\n  Dendrite API starting...")
    print(f"  Database:  {DB_PATH}")
    print(f"  API:       http://localhost:{PORT}")
    print(f"  Docs:      http://localhost:{PORT}/docs")
    print(f"  Health:    http://localhost:{PORT}/health\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
