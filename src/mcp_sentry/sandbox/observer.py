import asyncio
from docker.errors import APIError, NotFound
from mcp_sentry.models.schemas import ObserverReport
from mcp_sentry.sandbox.docker_runner import ContainerHandle


class Observer:
    async def watch(self, handle: ContainerHandle, timeout_s: float = 15.0) -> ObserverReport:
        peak_memory_mb = 0.0
        peak_cpu_percent = 0.0
        exit_code = None
        timed_out = True
        poll_interval = 0.5
        elapsed = 0.0

        try:
            while elapsed < timeout_s:
                try:
                    stats = await asyncio.to_thread(handle.container.stats, stream=False)
                    cpu_percent, memory_mb = self._parse_stats(stats)
                    peak_memory_mb = max(peak_memory_mb, memory_mb)
                    peak_cpu_percent = max(peak_cpu_percent, cpu_percent)
                except (ValueError, KeyError):
                    pass  # malformed/incomplete stats response, e.g. container still starting up; skip this sample

                await asyncio.to_thread(handle.container.reload)
                if handle.container.status != "running":
                    exit_code = handle.container.attrs["State"]["ExitCode"]
                    timed_out = False
                    break

                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
        except NotFound:
            # container exited and was auto-removed before we could poll it
            try:
                result = await asyncio.to_thread(handle.container.wait)
                exit_code = result.get("StatusCode")
                timed_out = False
            except NotFound:
                pass  # gone before we could even get the exit code

        stderr_tail = ""
        try:
            logs = await asyncio.to_thread(handle.container.logs, stderr=True, tail=10)
            stderr_tail = logs.decode("utf-8") if logs else ""
        except APIError:
            pass  # container already gone or being removed (auto_remove race); no logs to capture

        crashed = exit_code is not None and exit_code != 0

        return ObserverReport(
            crashed=crashed,
            exit_code=exit_code,
            timed_out=timed_out,
            peak_memory_mb=peak_memory_mb,
            peak_cpu_percent=peak_cpu_percent,
            stderr_tail=stderr_tail,
        )

    @staticmethod
    def _parse_stats(stats: dict) -> tuple[float, float]:
        cpu_delta = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            stats["cpu_stats"]["system_cpu_usage"]
            - stats["precpu_stats"]["system_cpu_usage"]
        )
        num_cpus = stats["cpu_stats"].get("online_cpus", 1)

        cpu_percent = 0.0
        if system_delta > 0 and cpu_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * num_cpus * 100.0

        memory_mb = stats["memory_stats"]["usage"] / (1024 * 1024)
        return cpu_percent, memory_mb