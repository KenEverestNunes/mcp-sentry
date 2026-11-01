import pytest

from mcp_sentry.client import MCPClient, MCPConnectionError


@pytest.mark.anyio
async def test_discovers_healthy_server_tools() -> None:
    client = MCPClient(
        "uv",
        ["run", "python", "-m", "mcp_sentry.targets.healthy_server"],
    )

    async with client:
        tools = await client.discover_tools()

    assert {tool.name for tool in tools} == {
        "get_order",
        "list_orders",
        "update_order_status",
    }
    assert all(tool.input_schema for tool in tools)


@pytest.mark.anyio
async def test_connect_reports_missing_command() -> None:
    client = MCPClient("mcp-sentry-command-that-does-not-exist", [])

    with pytest.raises(MCPConnectionError, match="Could not start MCP server"):
        await client.connect()


@pytest.mark.anyio
async def test_discovery_requires_a_connection() -> None:
    client = MCPClient()

    with pytest.raises(MCPConnectionError, match="Connect to an MCP server"):
        await client.discover_tools()
