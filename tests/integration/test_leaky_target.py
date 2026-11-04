import pytest

from mcp_sentry.client import MCPClient
from mcp_sentry.config import TARGET_CONFIGS


@pytest.mark.asyncio
async def test_leaky_target_exposes_fake_secrets() -> None:
    target = TARGET_CONFIGS["leaky"]

    async with MCPClient(target.command, target.args) as client:
        result = await client.call_tool(
            "debug_order",
            {"order_id": 1, "verbose": True},
        )

    response_content = str(result.content)
    assert result.success is True
    assert "postgres://fake:fake@localhost/fakedb" in response_content
    assert "/home/user/secret.txt" in response_content