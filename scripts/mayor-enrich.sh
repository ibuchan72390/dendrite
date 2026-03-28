#!/usr/bin/env bash
# mayor-enrich.sh — Enrich gt prime context with Dendrite knowledge
#
# Usage:
#   mayor-enrich.sh [query]
#   GT_HOOK="some context" mayor-enrich.sh
#
# The query is resolved in order:
#   1. First positional argument ($1)
#   2. GT_HOOK environment variable
#   3. If neither is set, exits silently (nothing to enrich with)
#
# Environment variables:
#   DENDRITE_API_URL  — Base URL for the Dendrite API (default: http://localhost:8181)
#   DENDRITE_TOP_K    — Number of results to return (default: 5)
#
# Output: A compact context block printed to stdout, suitable for injection
# into gt prime output. Exits silently (no output, exit 0) if the API is
# unreachable or no query is available.
#
# ─── Wiring into gt prime ────────────────────────────────────────────────────
#
# Option A: mayor CLAUDE.md snippet (inline enrichment)
#   Add to mayor's CLAUDE.md or gt prime template:
#
#   ```bash
#   # Enrich context with relevant Dendrite knowledge
#   DENDRITE_CONTEXT=$(scripts/mayor-enrich.sh "$GT_HOOK" 2>/dev/null)
#   [ -n "$DENDRITE_CONTEXT" ] && echo "$DENDRITE_CONTEXT"
#   ```
#
# Option B: gt prime hook (settings.json)
#   Wire as a PostToolUse hook on Bash so it appends after each prime:
#
#   {
#     "hooks": {
#       "PostToolUse": [{
#         "matcher": "Bash",
#         "hooks": [{
#           "type": "command",
#           "command": "scripts/mayor-enrich.sh \"$GT_HOOK\""
#         }]
#       }]
#     }
#   }
#
# Option C: Direct shell sourcing in wrapper scripts
#   Any script that calls `gt prime` can prepend enrichment:
#
#   #!/usr/bin/env bash
#   gt prime
#   scripts/mayor-enrich.sh "$GT_HOOK"
#
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

DENDRITE_API_URL="${DENDRITE_API_URL:-http://localhost:8181}"
DENDRITE_TOP_K="${DENDRITE_TOP_K:-5}"

# Resolve query from arg or env
QUERY="${1:-${GT_HOOK:-}}"

# No query → nothing to enrich, exit silently
if [ -z "$QUERY" ]; then
    exit 0
fi

# Truncate long queries to keep the API request reasonable
QUERY="${QUERY:0:200}"

# URL-encode the query (replace spaces and special chars)
ENCODED_QUERY=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "$QUERY" 2>/dev/null) || {
    # Fallback: basic space encoding if python3 unavailable
    ENCODED_QUERY="${QUERY// /+}"
}

SEARCH_URL="${DENDRITE_API_URL}/search?q=${ENCODED_QUERY}&top_k=${DENDRITE_TOP_K}"

# Query the API with a short timeout; exit silently if unreachable
RESPONSE=$(curl --silent --max-time 3 --fail "$SEARCH_URL" 2>/dev/null) || exit 0

# Validate we got a non-empty JSON array
if [ -z "$RESPONSE" ] || [ "$RESPONSE" = "[]" ] || [ "$RESPONSE" = "null" ]; then
    exit 0
fi

# Format results as a compact context block
python3 - "$RESPONSE" <<'EOF'
import json
import sys

data = sys.argv[1]

try:
    results = json.loads(data)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)

if not isinstance(results, list) or not results:
    sys.exit(0)

# Limit to top 5
results = results[:5]

print("## Dendrite Context")
print()
for r in results:
    rank = r.get("rank", "?")
    title = r.get("title", r.get("id", "unknown"))
    confidence = r.get("confidence", 0)
    content = r.get("content", "").strip()

    # Truncate long content for readability
    if len(content) > 200:
        content = content[:197] + "..."

    concepts = r.get("concepts", [])
    concept_str = ", ".join(concepts[:5]) if concepts else ""

    print(f"**{rank}. {title}** (confidence: {confidence:.2f})")
    if content:
        print(f"   {content}")
    if concept_str:
        print(f"   *Concepts: {concept_str}*")
    print()
EOF
