import asyncio
from unittest.mock import AsyncMock, patch

import docker
import httpx
import pytest

from mcp_sentry.api.app import app
from mcp_sentry.api.runs import RUNS, _RUN_LOCK
from mcp_sentry.evaluation.verdict import Verdict
from mcp_sentry.models.schemas import ObserverReport, SessionReport


def _docker_is_available() -> bool:
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


@pytest.fixture(autouse=True)
def clean_runs_state() -> None:
    RUNS.clear()
    if _RUN_LOCK.locked():
        _RUN_LOCK.release()


@pytest.mark.asyncio
async def test_get_targets_returns_supported_targets() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get("/targets")
        assert res.status_code == 200
        targets = res.json()
        assert "fragile" in targets
        assert "healthy" in targets
        assert "leaky" in targets


@pytest.mark.asyncio
async def test_post_runs_invalid_target_returns_400() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.post("/runs", json={"target": "nonexistent_server"})
        assert res.status_code == 400
        assert "Unknown target" in res.json()["detail"]


@pytest.mark.asyncio
async def test_get_runs_not_found_returns_404() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get("/runs/nonexistent-id")
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_api_runs_lifecycle_and_concurrency_lock() -> None:
    from mcp_sentry.models.schemas import FuzzCase, ToolCallResult

    mock_fuzz_case = FuzzCase(
        tool_name="crash_tool",
        arguments={"input": "test"},
        result=ToolCallResult(
            success=False,
            content=None,
            error="Server crashed",
            raw_exception_text="Crash error",
        ),
    )
    mock_report = SessionReport(
        target_name="fragile",
        verdicts=[
            Verdict(
                fuzz_case=mock_fuzz_case,
                passed=False,
                reasons=["target crashed on input"],
                severity="critical",
            )
        ],
        observer_report=ObserverReport(
            crashed=True,
            exit_code=1,
            timed_out=False,
            peak_memory_mb=12.5,
            peak_cpu_percent=5.0,
            stderr_tail="Crash error",
        ),
    )

    async def delayed_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        await asyncio.sleep(0.3)
        return mock_report

    with patch("mcp_sentry.api.runs.SessionOrchestrator") as mock_orchestrator_cls:
        mock_instance = mock_orchestrator_cls.return_value
        mock_instance.run = AsyncMock(side_effect=delayed_run)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            # 1. Start a run
            start_res = await client.post("/runs", json={"target": "fragile"})
            assert start_res.status_code == 200
            run_data = start_res.json()
            run_id = run_data["run_id"]
            assert run_data["status"] in {"pending", "running"}

            # 2. Immediately try to start a second run while first is active -> 409
            conflict_res = await client.post("/runs", json={"target": "healthy"})
            assert conflict_res.status_code == 409
            assert "already in progress" in conflict_res.json()["detail"]

            # 3. Poll until completed
            completed = False
            for _ in range(30):
                poll_res = await client.get(f"/runs/{run_id}")
                assert poll_res.status_code == 200
                poll_data = poll_res.json()
                if poll_data["status"] == "completed":
                    completed = True
                    assert poll_data["report"] is not None
                    verdicts = poll_data["report"]["verdicts"]
                    assert any(v["severity"] == "critical" for v in verdicts)
                    break
                if poll_data["status"] == "failed":
                    pytest.fail(f"Run failed unexpectedly: {poll_data.get('error')}")
                await asyncio.sleep(0.1)

            assert completed, "Run did not reach completed status"

            # 4. Lock should now be released, allowing new run
            next_res = await client.post("/runs", json={"target": "healthy"})
            assert next_res.status_code == 200


@pytest.mark.asyncio
@pytest.mark.skipif(not _docker_is_available(), reason="Docker daemon not running locally")
async def test_api_runs_live_docker_fragile() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        start_res = await client.post("/runs", json={"target": "fragile"})
        assert start_res.status_code == 200
        run_id = start_res.json()["run_id"]

        # Assert concurrent run is rejected
        conflict_res = await client.post("/runs", json={"target": "fragile"})
        assert conflict_res.status_code == 409

        # Poll until finished
        completed = False
        for _ in range(60):
            poll_res = await client.get(f"/runs/{run_id}")
            assert poll_res.status_code == 200
            poll_data = poll_res.json()
            if poll_data["status"] in {"completed", "failed"}:
                completed = True
                assert poll_data["status"] == "completed"
                report = poll_data["report"]
                assert report is not None
                assert any(v["severity"] == "critical" for v in report["verdicts"])
                break
            await asyncio.sleep(1.0)

        assert completed, "Fragile live run timed out before completion"
