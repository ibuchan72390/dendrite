"""
Dendrite MCP Server — Exposes dendrite as tools for Claude Code.

This is a stdio-based MCP server that wraps dendrite's core library,
providing Claude Code with direct access to the neural knowledge graph.

Usage:
    Configure in .claude/settings.json:
    {
      "mcpServers": {
        "dendrite": {
          "type": "stdio",
          "command": "python3",
          "args": ["/path/to/dendrite_mcp_server.py"],
          "environmentVariables": {
            "DENDRITE_DB": "/path/to/project.dendrite.db"
          }
        }
      }
    }
"""

import json
import os
import sys


# Default database path
DB_PATH = os.environ.get("DENDRITE_DB", os.path.expanduser("~/.dendrite.db"))


def get_dendrite():
    """Create a Dendrite instance connected to the configured database."""
    from dendrite.core import Dendrite
    return Dendrite(db_path=DB_PATH)


# --- Tool definitions (MCP schema) ---

TOOLS = [
    {
        "name": "dendrite_add",
        "description": (
            "Store a new piece of knowledge in dendrite's neural network. "
            "The content is analyzed for concepts and automatically connected "
            "to related neurons via TF-IDF similarity. Use this when you learn "
            "something worth persisting across sessions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The knowledge to store (text content of the neuron)."
                },
                "title": {
                    "type": "string",
                    "description": "Optional short title for the neuron."
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "dendrite_ask",
        "description": (
            "Search dendrite's knowledge graph using semantic similarity and "
            "activation spreading. Returns the most relevant neurons plus "
            "activation paths showing how knowledge connects. Use this when "
            "you need to recall information or find related knowledge."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (natural language)."
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of top results to return.",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "dendrite_explore",
        "description": (
            "Explore the knowledge graph from a concept, following synaptic "
            "connections via BFS. Returns all neurons and connections within "
            "the specified depth. Use this to understand a topic area."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "concept": {
                    "type": "string",
                    "description": "The concept to explore from."
                },
                "depth": {
                    "type": "integer",
                    "description": "How many hops to follow (default: 3).",
                    "default": 3
                }
            },
            "required": ["concept"]
        }
    },
    {
        "name": "dendrite_show",
        "description": "Get a specific neuron by ID with its connections.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "neuron_id": {
                    "type": "string",
                    "description": "The neuron ID to look up."
                }
            },
            "required": ["neuron_id"]
        }
    },
    {
        "name": "dendrite_list",
        "description": "List all neurons in the knowledge graph.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "dendrite_stats",
        "description": (
            "Return network statistics: neuron count, synapse count, "
            "average degree, most connected neurons, and top concepts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "dendrite_consolidate",
        "description": (
            "Strengthen frequently traversed connections and optionally "
            "apply temporal decay. Run this periodically to maintain "
            "the network's relevance."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "decay_days": {
                    "type": "number",
                    "description": "Apply N days of decay before consolidating (default: 0).",
                    "default": 0
                }
            }
        }
    },
    {
        "name": "dendrite_reindex",
        "description": (
            "Recompute all TF-IDF similarities and rebuild synaptic "
            "connections. Run this after batch additions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
]


# --- Tool handlers ---

def handle_dendrite_add(args):
    d = get_dendrite()
    try:
        neuron = d.add(args["content"], title=args.get("title"))
        synapses = d.storage.get_synapses_for_neuron(neuron.id)
        return {
            "id": neuron.id,
            "title": neuron.display_title(),
            "concepts": neuron.concepts,
            "connections_created": len(synapses),
        }
    finally:
        d.close()


def handle_dendrite_ask(args):
    d = get_dendrite()
    try:
        results = d.ask(args["query"], top_k=args.get("top_k", 5))
        all_ids = set()
        for seed, activation in results:
            all_ids.add(seed.neuron_id)
            for a in activation:
                all_ids.add(a.neuron_id)
        neurons_by_id = d.get_neurons_by_id(list(all_ids))

        output = []
        for rank, (seed, activation) in enumerate(results, start=1):
            neuron = neurons_by_id.get(seed.neuron_id)
            activation_path = []
            for a in activation:
                n = neurons_by_id.get(a.neuron_id)
                if n:
                    activation_path.append(n.display_title())
            output.append({
                "rank": rank,
                "id": seed.neuron_id,
                "title": neuron.display_title() if neuron else seed.neuron_id,
                "confidence": round(seed.score, 4),
                "content": neuron.content if neuron else "",
                "concepts": neuron.concepts if neuron else [],
                "activation_path": activation_path,
            })
        return output
    finally:
        d.close()


def handle_dendrite_explore(args):
    d = get_dendrite()
    try:
        net_map = d.explore(args["concept"], depth=args.get("depth", 3))
        return {
            "concept": args["concept"],
            "neurons": [
                {"id": n.id, "title": n.display_title(), "concepts": n.concepts}
                for n in net_map.neurons
            ],
            "synapses": [
                {
                    "source_id": s.source_id,
                    "target_id": s.target_id,
                    "weight": round(s.weight, 4),
                }
                for s in net_map.synapses
            ],
        }
    finally:
        d.close()


def handle_dendrite_show(args):
    d = get_dendrite()
    try:
        neuron = d.get_neuron(args["neuron_id"])
        if neuron is None:
            return {"error": f"Neuron '{args['neuron_id']}' not found."}
        synapses = d.storage.get_synapses_for_neuron(args["neuron_id"])
        connections = []
        for s in sorted(synapses, key=lambda x: -x.weight):
            neighbor_id = s.target_id if s.source_id == args["neuron_id"] else s.source_id
            neighbor = d.storage.get_neuron(neighbor_id, increment_access=False)
            connections.append({
                "target_id": neighbor_id,
                "target_title": neighbor.display_title() if neighbor else neighbor_id,
                "weight": round(s.weight, 4),
            })
        return {
            "id": neuron.id,
            "title": neuron.display_title(),
            "content": neuron.content,
            "concepts": neuron.concepts,
            "access_count": neuron.access_count,
            "connections": connections,
        }
    finally:
        d.close()


def handle_dendrite_list(args):
    d = get_dendrite()
    try:
        neurons = d.get_all_neurons()
        synapses = d.get_all_synapses()
        conn_count = {}
        for s in synapses:
            conn_count[s.source_id] = conn_count.get(s.source_id, 0) + 1
            conn_count[s.target_id] = conn_count.get(s.target_id, 0) + 1
        return [
            {
                "id": n.id,
                "title": n.display_title(),
                "concepts": n.concepts,
                "connections": conn_count.get(n.id, 0),
            }
            for n in neurons
        ]
    finally:
        d.close()


def handle_dendrite_stats(args):
    d = get_dendrite()
    try:
        s = d.stats()
        top_concepts = sorted(s.concept_distribution.items(), key=lambda x: -x[1])[:10]
        return {
            "neuron_count": s.neuron_count,
            "synapse_count": s.synapse_count,
            "avg_degree": round(s.avg_degree, 4),
            "most_connected": [
                {"id": neuron.id, "title": neuron.display_title(), "connections": deg}
                for neuron, deg in s.most_connected
            ],
            "top_concepts": [[concept, count] for concept, count in top_concepts],
        }
    finally:
        d.close()


def handle_dendrite_consolidate(args):
    d = get_dendrite()
    try:
        n_decayed = 0
        decay_days = args.get("decay_days", 0)
        if decay_days > 0:
            n_decayed = d.run_decay(days=decay_days)
        n_boosted = d.run_consolidation()
        return {
            "synapses_consolidated": n_boosted,
            "synapses_decayed": n_decayed,
        }
    finally:
        d.close()


def handle_dendrite_reindex(args):
    d = get_dendrite()
    try:
        count = d.reindex()
        return {"synapses_created": count}
    finally:
        d.close()


HANDLERS = {
    "dendrite_add": handle_dendrite_add,
    "dendrite_ask": handle_dendrite_ask,
    "dendrite_explore": handle_dendrite_explore,
    "dendrite_show": handle_dendrite_show,
    "dendrite_list": handle_dendrite_list,
    "dendrite_stats": handle_dendrite_stats,
    "dendrite_consolidate": handle_dendrite_consolidate,
    "dendrite_reindex": handle_dendrite_reindex,
}


# --- MCP Protocol (JSON-RPC over stdio) ---

def send_response(id, result):
    """Send a JSON-RPC response."""
    response = {"jsonrpc": "2.0", "id": id, "result": result}
    msg = json.dumps(response)
    sys.stdout.write(f"Content-Length: {len(msg)}\r\n\r\n{msg}")
    sys.stdout.flush()


def send_error(id, code, message):
    """Send a JSON-RPC error response."""
    response = {
        "jsonrpc": "2.0",
        "id": id,
        "error": {"code": code, "message": message},
    }
    msg = json.dumps(response)
    sys.stdout.write(f"Content-Length: {len(msg)}\r\n\r\n{msg}")
    sys.stdout.flush()


def read_message():
    """Read a JSON-RPC message from stdin (Content-Length framed)."""
    headers = {}
    while True:
        line = sys.stdin.readline()
        if not line or line.strip() == "":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()

    content_length = int(headers.get("Content-Length", 0))
    if content_length == 0:
        return None

    body = sys.stdin.read(content_length)
    return json.loads(body)


def handle_request(request):
    """Process a single JSON-RPC request."""
    method = request.get("method")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        send_response(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": "dendrite",
                "version": "0.1.0",
            },
        })
    elif method == "notifications/initialized":
        pass  # No response needed for notifications
    elif method == "tools/list":
        send_response(req_id, {"tools": TOOLS})
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        handler = HANDLERS.get(tool_name)
        if handler is None:
            send_error(req_id, -32601, f"Unknown tool: {tool_name}")
            return

        try:
            result = handler(tool_args)
            send_response(req_id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2),
                    }
                ],
            })
        except Exception as e:
            send_response(req_id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"error": str(e)}),
                    }
                ],
                "isError": True,
            })
    elif method == "ping":
        send_response(req_id, {})
    else:
        if req_id is not None:
            send_error(req_id, -32601, f"Method not found: {method}")


def main():
    """Main loop: read JSON-RPC messages from stdin, dispatch to handlers."""
    while True:
        try:
            message = read_message()
            if message is None:
                break
            handle_request(message)
        except (EOFError, KeyboardInterrupt):
            break
        except Exception as e:
            sys.stderr.write(f"dendrite-mcp error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
