"""Integration tests for the healthy MCP target."""

import json

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import TextContent

from mcp_sentry.targets import healthy_server


@pytest.fixture(autouse=True)
def reset_orders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        healthy_server,
        "ORDERS",
        {
            1: {"order_id": 1, "status": "pending"},
            2: {"order_id": 2, "status": "shipped"},
        },
    )


@pytest.mark.anyio
async def test_healthy_target_registers_all_tools() -> None:
    tools = await healthy_server.mcp.list_tools()

    assert {tool.name for tool in tools} == {
        "get_order",
        "list_orders",
        "update_order_status",
    }


@pytest.mark.anyio
async def test_get_order_returns_matching_order() -> None:
    result = await healthy_server.mcp.call_tool("get_order", {"order_id": 1})

    assert isinstance(result[0], TextContent)
    assert json.loads(result[0].text) == {"order_id": 1, "status": "pending"}


@pytest.mark.anyio
async def test_get_order_raises_for_unknown_order() -> None:
    with pytest.raises(ToolError, match="Order ID 99 not found"):
        await healthy_server.mcp.call_tool("get_order", {"order_id": 99})


@pytest.mark.anyio
async def test_list_orders_returns_all_orders() -> None:
    result = await healthy_server.mcp.call_tool("list_orders", {})

    assert isinstance(result, tuple)
    assert result[1] == {
        "result": [
            {"order_id": 1, "status": "pending"},
            {"order_id": 2, "status": "shipped"},
        ]
    }


@pytest.mark.anyio
async def test_list_orders_filters_by_status() -> None:
    result = await healthy_server.mcp.call_tool("list_orders", {"status": "shipped"})

    assert isinstance(result, tuple)
    assert result[1] == {"result": [{"order_id": 2, "status": "shipped"}]}


@pytest.mark.anyio
async def test_update_order_status_updates_existing_order() -> None:
    result = await healthy_server.mcp.call_tool(
        "update_order_status",
        {"order_id": 1, "status": "delivered"},
    )

    assert isinstance(result[0], TextContent)
    assert json.loads(result[0].text) == {"order_id": 1, "status": "delivered"}
    assert healthy_server.ORDERS[1]["status"] == "delivered"


@pytest.mark.anyio
async def test_update_order_status_rejects_invalid_status() -> None:
    with pytest.raises(ToolError, match="Invalid status: lost"):
        await healthy_server.mcp.call_tool(
            "update_order_status",
            {"order_id": 1, "status": "lost"},
        )

    assert healthy_server.ORDERS[1]["status"] == "pending"


@pytest.mark.anyio
async def test_update_order_status_raises_for_unknown_order() -> None:
    with pytest.raises(ToolError, match="Order ID 99 not found"):
        await healthy_server.mcp.call_tool(
            "update_order_status",
            {"order_id": 99, "status": "shipped"},
        )
