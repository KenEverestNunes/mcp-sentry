import asyncio
import pytest
from mcp_sentry.client import MCPClient
from mcp_sentry.sandbox.docker_runner import DockerSandbox
from mcp_sentry.sandbox.observer import Observer


@pytest.mark.asyncio
async def test_observer_reports_fragile_container_crash() -> None:
    sandbox = DockerSandbox()
    handle = await sandbox.start("mcp-sentry/fragile:local")
    client = MCPClient()
    observer_task = asyncio.create_task(Observer().watch(handle))

    try:
        await client.connect_to_container(handle)
        try:
            await client.call_tool(
                "parse_order_note",
                {"order_id": 1, "note": "no colon"},
            )
        except Exception:
            pass  # expected: the crash breaks the connection, Observer's report is what we're testing

        report = await observer_task
        assert report.crashed or report.stderr_tail
    finally:
        try:
            if not observer_task.done():
                observer_task.cancel()
                try:
                    await observer_task
                except asyncio.CancelledError:
                    pass
        finally:
            try:
                await client.close()
            finally:
                await sandbox.stop(handle)