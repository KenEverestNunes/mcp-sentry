import pytest

from mcp_sentry.client import MCPClient
from mcp_sentry.config import TARGET_CONFIGS
from mcp_sentry.fuzzing.engine import FuzzEngine


@pytest.mark.asyncio
async def test_fuzz_engine_triggers_fragile_target_crash() -> None:
    target_config = TARGET_CONFIGS["fragile"]

    async with MCPClient(target_config.command, target_config.args) as client:
        engine = FuzzEngine()
        fuzz_cases = await engine.run(client, target_config)

    assert any(case.result.success is False for case in fuzz_cases)
