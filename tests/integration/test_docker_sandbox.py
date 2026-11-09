import docker
import pytest

from mcp_sentry.sandbox.docker_runner import DockerSandbox


@pytest.mark.asyncio
async def test_docker_sandbox_starts_and_removes_container() -> None:
    sandbox = DockerSandbox()
    handle = await sandbox.start("mcp-sentry/healthy:local")

    handle.container.reload()
    assert handle.container.status in {"created", "running"}

    container_id = handle.container.id
    await sandbox.stop(handle)

    with pytest.raises(docker.errors.NotFound):
        sandbox.client.containers.get(container_id)