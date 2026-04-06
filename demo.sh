#!/usr/bin/env bash
# demo.sh — One-command Dendrite demo launcher
#
# Usage:
#   ./demo.sh          # Seed data + start API on port 8181
#   ./demo.sh seed     # Only seed data (no API)
#   ./demo.sh api      # Only start API (assumes data exists)
#   ./demo.sh cli      # Interactive CLI walkthrough
#   ./demo.sh test     # Run full test suite
#   ./demo.sh clean    # Remove demo database

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DENDRITE_DB="${DENDRITE_DB:-/tmp/dendrite-demo.db}"
export PORT="${PORT:-8181}"

cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

banner() {
    echo ""
    echo -e "${BOLD}${CYAN}  ╔═══════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}  ║     🧠 Dendrite — Knowledge Synthesis    ║${NC}"
    echo -e "${BOLD}${CYAN}  ╚═══════════════════════════════════════════╝${NC}"
    echo ""
}

check_deps() {
    local missing=0
    for cmd in python3 dendrite; do
        if ! command -v "$cmd" &>/dev/null; then
            echo -e "${RED}Missing: $cmd${NC}"
            missing=1
        fi
    done
    if [ $missing -eq 1 ]; then
        echo -e "${DIM}Install dendrite: pip install -e '.[dev]'${NC}"
        exit 1
    fi
}

seed() {
    echo -e "${CYAN}Seeding demo database...${NC}"
    python3 scripts/seed-demo.py
    echo ""
}

start_api() {
    echo -e "${CYAN}Starting API server...${NC}"
    echo -e "${DIM}  Database: $DENDRITE_DB${NC}"
    echo -e "${DIM}  API:      http://localhost:$PORT${NC}"
    echo -e "${DIM}  Docs:     http://localhost:$PORT/docs${NC}"
    echo -e "${DIM}  Press Ctrl+C to stop${NC}"
    echo ""
    python3 api_bridge.py
}

cli_walkthrough() {
    echo -e "${CYAN}CLI Walkthrough${NC}"
    echo ""

    echo -e "${BOLD}1. List all neurons:${NC}"
    dendrite list
    echo ""

    echo -e "${BOLD}2. Semantic search — 'how does knowledge self-organize?':${NC}"
    dendrite ask "how does knowledge self-organize?" --top 3
    echo ""

    echo -e "${BOLD}3. Explore the concept 'activation':${NC}"
    dendrite explore "activation" --depth 2
    echo ""

    echo -e "${BOLD}4. Network statistics:${NC}"
    dendrite stats
    echo ""

    echo -e "${BOLD}5. Knowledge graph visualization:${NC}"
    dendrite graph --max-nodes 10
    echo ""

    echo -e "${GREEN}CLI walkthrough complete.${NC}"
}

run_tests() {
    echo -e "${CYAN}Running test suite...${NC}"
    python3 -m pytest tests/ -v --tb=short
}

clean() {
    if [ -f "$DENDRITE_DB" ]; then
        rm -f "$DENDRITE_DB"
        echo -e "${GREEN}Removed: $DENDRITE_DB${NC}"
    else
        echo -e "${DIM}No database to clean: $DENDRITE_DB${NC}"
    fi
}

# --- Main ---

banner
check_deps

case "${1:-full}" in
    seed)
        seed
        ;;
    api)
        start_api
        ;;
    cli)
        if [ ! -f "$DENDRITE_DB" ]; then
            seed
        fi
        cli_walkthrough
        ;;
    test)
        run_tests
        ;;
    clean)
        clean
        ;;
    full|"")
        seed
        start_api
        ;;
    *)
        echo "Usage: $0 [seed|api|cli|test|clean|full]"
        echo ""
        echo "  seed   — Seed demo data only"
        echo "  api    — Start API server only"
        echo "  cli    — Interactive CLI walkthrough"
        echo "  test   — Run full test suite (160 tests)"
        echo "  clean  — Remove demo database"
        echo "  full   — Seed + start API (default)"
        exit 1
        ;;
esac
