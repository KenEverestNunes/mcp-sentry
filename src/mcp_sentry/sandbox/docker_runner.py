import asyncio
import atexit
from dataclasses import dataclass, field
import docker
from docker.errors import APIError, ImageNotFound, NotFound

_ACTIVE_CONTAINERS: set[object] = set()


def _cleanup_lingering_containers() -> None:
    """Best-effort cleanup handler on process termination."""
    for container in list(_ACTIVE_CONTAINERS):
        try:
            container.remove(v=True, force=True)
        except Exception:
            pass
    _ACTIVE_CONTAINERS.clear()


atexit.register(_cleanup_lingering_containers)


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
                auto_remove=False,
                labels={"managed-by": "mcp-sentry"},
            )
            _ACTIVE_CONTAINERS.add(container)
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
        except (NotFound, APIError):
            pass  # already stopped normally, nothing to kill

    async def stop(self, handle: ContainerHandle) -> None:
        if handle.watchdog:
            handle.watchdog.cancel()

        # Close attached socket if present
        if hasattr(handle.socket, "close"):
            try:
                handle.socket.close()
            except Exception:
                pass

        try:
            await asyncio.to_thread(handle.container.stop, timeout=1)
        except (NotFound, APIError):
            pass

        try:
            await asyncio.to_thread(handle.container.remove, v=True, force=True)
        except (NotFound, APIError):
            pass
        finally:
            _ACTIVE_CONTAINERS.discard(handle.container)
