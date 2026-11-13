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


@pytest.mark.anyio
async def test_call_tool_handles_empty_error_content() -> None:
    client = MCPClient()
    client._initialized = True

    class DummySession:
        async def call_tool(self, name: str, arguments: dict):
            class DummyResult:
                isError = True
                content = []
            return DummyResult()

    client.session = DummySession()
    result = await client.call_tool("test_tool", {})
    assert result.success is False
    assert result.error == "Tool execution failed with empty error content."


@pytest.mark.anyio
async def test_call_tool_handles_non_text_content() -> None:
    client = MCPClient()
    client._initialized = True

    class DummySession:
        async def call_tool(self, name: str, arguments: dict):
            class NonTextItem:
                data = "binary-blob"
                def __str__(self):
                    return "custom-binary-representation"

            class DummyResult:
                isError = True
                content = [NonTextItem()]
            return DummyResult()

    client.session = DummySession()
    result = await client.call_tool("test_tool", {})
    assert result.success is False
    assert result.error == "custom-binary-representation"

