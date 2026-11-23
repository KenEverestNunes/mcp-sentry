import docker
import pytest
from mcp_sentry.config.target_configs import TARGET_CONFIGS
from mcp_sentry.session import SessionOrchestrator


def _docker_is_available() -> bool:
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


@pytest.mark.asyncio
@pytest.mark.skipif(not _docker_is_available(), reason="Docker daemon not running locally")
async def test_session_orchestrator_catches_fragile_critical_verdict() -> None:
    orchestrator = SessionOrchestrator()
    config = TARGET_CONFIGS["fragile"]
    image = "mcp-sentry/fragile:local"

    report = await orchestrator.run(config=config, image=image, timeout_s=30.0)

    assert report.target_name == "fragile"
    assert len(report.verdicts) > 0
    assert report.observer_report is not None

    severities = [v.severity for v in report.verdicts]
    assert "critical" in severities

    critical_verdicts = [v for v in report.verdicts if v.severity == "critical"]
    critical_reasons = [r for v in critical_verdicts for r in v.reasons]

    assert any(
        "target crashed on input" in r
        or "target froze / exceeded timeout" in r
        or "response contains a configured leak pattern" in r
        for r in critical_reasons
    )

