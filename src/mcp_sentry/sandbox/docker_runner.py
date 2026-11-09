import asyncio
from dataclasses import dataclass, field
import docker
from docker.errors import APIError, ImageNotFound, NotFound


class SandboxStartError(Exception):
    """Raised when a sandboxed container fails to start."""


@dataclass
class ContainerHandle:
    container: object  # the Docker SDK's Container object
    socket: object      # the attached stdio socket
    watchdog: asyncio.Task = field(default=None, repr=False)


class DockerSandbox:
    def __init__(self) -> None:
        self.client = docker.from_env()

    async def start(self, image: str) -> ContainerHandle:
        try:
            container = await asyncio.to_thread(
                self.client.containers.run,
                image,
                detach=True,
                stdin_open=True,
                tty=False,
                mem_limit="256m",
                nano_cpus=500_000_000,
                network_disabled=True,
                auto_remove=True,
            )
        except (APIError, ImageNotFound) as exc:
            raise SandboxStartError(
                f"Failed to start container for image {image!r}: {exc}"
            ) from exc

        socket = await asyncio.to_thread(
            container.attach_socket,
            params={"stdin": 1, "stdout": 1, "stream": 1},
        )

        handle = ContainerHandle(container=container, socket=socket)
        handle.watchdog = asyncio.create_task(self._kill_after_timeout(handle, timeout=15))
        return handle

    async def _kill_after_timeout(self, handle: ContainerHandle, timeout: float) -> None:
        await asyncio.sleep(timeout)
        try:
            await asyncio.to_thread(handle.container.kill)
        except NotFound:
            pass  # already stopped normally, nothing to kill

    async def stop(self, handle: ContainerHandle) -> None:
        handle.watchdog.cancel()
        try:
            await asyncio.to_thread(handle.container.stop)
        except NotFound:
            return
        for _ in range(20):
            try:
                await asyncio.to_thread(self.client.containers.get, handle.container.id)
            except NotFound:
                return
            await asyncio.sleep(0.25)