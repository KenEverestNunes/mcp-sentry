"""Integration tests for the fragile MCP target."""

import pytest

from mcp_sentry.client import MCPClient


@pytest.mark.asyncio
async def test_get_order_reports_key_error_for_missing_order() -> None:
    client = MCPClient(
        "uv",
        ["run", "python", "-m", "mcp_sentry.targets.fragile_server"],
    )

    async with client:
        result = await client.call_tool("get_order", {"order_id": 99})

    assert result.success is False
    exception_details = f"{result.error or ''}\n{result.raw_exception_text or ''}"
    assert "Error executing tool get_order: 99" in exception_details


@pytest.mark.asyncio
async def test_parse_order_note_reports_index_error_without_colon() -> None:
    client = MCPClient(
        "uv",
        ["run", "python", "-m", "mcp_sentry.targets.fragile_server"],
    )

    async with client:
        result = await client.call_tool(
            "parse_order_note",
            {"order_id": 1, "note": "no colon"},
        )

    assert result.success is False
    exception_details = f"{result.error or ''}\n{result.raw_exception_text or ''}"
    assert "Error executing tool parse_order_note: list index out of range" in exception_details
