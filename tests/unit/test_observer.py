from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from docker.errors import NotFound

from mcp_sentry.sandbox.observer import Observer


@pytest.fixture
def skip_observer_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def skip_sleep(_delay: float) -> None:
        pass

    monkeypatch.setattr("mcp_sentry.sandbox.observer.asyncio.sleep", skip_sleep)


def _make_stats(cpu_delta: int, memory_mb: int) -> dict:
    return {
        "cpu_stats": {
            "cpu_usage": {"total_usage": cpu_delta},
            "system_cpu_usage": 1_000_000,
            "online_cpus": 1,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 0},
            "system_cpu_usage": 0,
        },
        "memory_stats": {"usage": memory_mb * 1024 * 1024},
    }


def _make_handle() -> tuple[SimpleNamespace, MagicMock]:
    container = MagicMock()
    container.status = "running"
    container.attrs = {"State": {"ExitCode": None}}
    container.logs.return_value = b""
    container.wait.return_value = {"StatusCode": 0}
    return SimpleNamespace(container=container), container


@pytest.mark.asyncio
async def test_watch_reports_nonzero_exit_after_polling(
    skip_observer_sleep: None,
) -> None:
    handle, container = _make_handle()
    statuses = iter(["running", "exited"])

    def reload_container() -> None:
        container.status = next(statuses)
        if container.status == "exited":
            container.attrs["State"]["ExitCode"] = 23

    container.stats.side_effect = [_make_stats(100_000, 10), _make_stats(200_000, 20)]
    container.reload.side_effect = reload_container

    report = await Observer().watch(handle, timeout_s=2.0)

    assert report.crashed is True
    assert report.exit_code == 23
    assert report.timed_out is False
    assert container.stats.call_count == 2


@pytest.mark.asyncio
async def test_watch_times_out_while_container_is_running(
    skip_observer_sleep: None,
) -> None:
    handle, container = _make_handle()
    container.stats.return_value = _make_stats(100_000, 10)

    report = await Observer().watch(handle, timeout_s=1.0)

    assert report.timed_out is True
    assert report.crashed is False
    assert report.exit_code is None
    assert container.stats.call_count == 2


@pytest.mark.asyncio
async def test_watch_reports_peak_memory_and_cpu_across_polls(
    skip_observer_sleep: None,
) -> None:
    handle, container = _make_handle()
    container.stats.side_effect = [
        _make_stats(200_000, 12),
        _make_stats(700_000, 64),
        _make_stats(300_000, 32),
    ]

    report = await Observer().watch(handle, timeout_s=1.5)

    assert report.timed_out is True
    assert report.peak_memory_mb == 64.0
    assert report.peak_cpu_percent == 70.0


@pytest.mark.asyncio
async def test_watch_uses_wait_fallback_when_container_is_already_removed(
    skip_observer_sleep: None,
) -> None:
    handle, container = _make_handle()
    container.stats.side_effect = NotFound("container was removed")
    container.wait.return_value = {"StatusCode": 17}

    report = await Observer().watch(handle)

    assert container.wait.called
    assert report.crashed is True
    assert report.exit_code == 17
    assert report.timed_out is False