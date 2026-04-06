"""Tests for the dendrite MCP server tool handlers."""

import os
import pytest

# Set test DB before importing handlers
os.environ["DENDRITE_DB"] = ":memory:"

from dendrite_mcp_server import (
    handle_dendrite_add,
    handle_dendrite_ask,
    handle_dendrite_consolidate,
    handle_dendrite_explore,
    handle_dendrite_list,
    handle_dendrite_reindex,
    handle_dendrite_show,
    handle_dendrite_stats,
    TOOLS,
    HANDLERS,
)


class TestToolDefinitions:
    def test_all_tools_have_handlers(self):
        """Every tool definition must have a corresponding handler."""
        for tool in TOOLS:
            assert tool["name"] in HANDLERS, f"Missing handler for tool: {tool['name']}"

    def test_all_handlers_have_tools(self):
        """Every handler must have a corresponding tool definition."""
        tool_names = {t["name"] for t in TOOLS}
        for handler_name in HANDLERS:
            assert handler_name in tool_names, f"Missing tool def for handler: {handler_name}"

    def test_tool_schemas_valid(self):
        """All tool schemas must have required fields."""
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"


class TestHandlers:
    """Test MCP handlers using in-memory database.

    Note: Each handler creates its own Dendrite instance connected to :memory:,
    so state does NOT persist between handler calls. These tests verify
    individual handler behavior, not cross-handler workflows.
    """

    def test_add_returns_neuron(self):
        result = handle_dendrite_add({"content": "Test knowledge about APIs"})
        assert "id" in result
        assert result["title"] == "Test knowledge about APIs"
        assert isinstance(result["concepts"], list)
        assert "connections_created" in result

    def test_add_with_title(self):
        result = handle_dendrite_add({
            "content": "REST APIs use HTTP methods",
            "title": "REST Basics"
        })
        assert result["title"] == "REST Basics"

    def test_ask_empty_db(self):
        result = handle_dendrite_ask({"query": "anything"})
        assert result == []

    def test_explore_empty_db(self):
        result = handle_dendrite_explore({"concept": "test"})
        assert result["concept"] == "test"
        assert result["neurons"] == []

    def test_show_nonexistent(self):
        result = handle_dendrite_show({"neuron_id": "nonexistent"})
        assert "error" in result

    def test_list_empty_db(self):
        result = handle_dendrite_list({})
        assert result == []

    def test_stats_empty_db(self):
        result = handle_dendrite_stats({})
        assert result["neuron_count"] == 0
        assert result["synapse_count"] == 0

    def test_consolidate_empty_db(self):
        result = handle_dendrite_consolidate({})
        assert result["synapses_consolidated"] == 0

    def test_consolidate_with_decay(self):
        result = handle_dendrite_consolidate({"decay_days": 1.0})
        assert result["synapses_decayed"] == 0

    def test_reindex_empty_db(self):
        result = handle_dendrite_reindex({})
        assert result["synapses_created"] == 0
