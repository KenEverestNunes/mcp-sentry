import asyncio
import re
from docker.errors import APIError, NotFound
from mcp_sentry.models.schemas import ObserverReport
from mcp_sentry.sandbox.docker_runner import ContainerHandle

ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
MAX_STDERR_BYTES = 4096


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
                stats = await asyncio.to_thread(handle.container.stats, stream=False)
                cpu_percent, memory_mb = self._parse_stats(stats)
                peak_memory_mb = max(peak_memory_mb, memory_mb)
                peak_cpu_percent = max(peak_cpu_percent, cpu_percent)

                await asyncio.to_thread(handle.container.reload)
                if handle.container.status != "running":
                    exit_code = handle.container.attrs["State"]["ExitCode"]
                    timed_out = False
                    break

                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
        except (NotFound, APIError):
            # container exited or stopped
            try:
                result = await asyncio.to_thread(handle.container.wait, timeout=1)
                exit_code = result.get("StatusCode")
                timed_out = False
            except (NotFound, APIError, Exception):
                pass

        stderr_tail = ""
        try:
            logs = await asyncio.to_thread(handle.container.logs, stderr=True, tail=20)
            if logs:
                # Bound size to avoid memory exhaustion
                raw_text = logs[:MAX_STDERR_BYTES].decode("utf-8", errors="replace")
                # Sanitize ANSI control sequences to prevent terminal / log injection
                stderr_tail = ANSI_ESCAPE_PATTERN.sub("", raw_text)
        except (NotFound, APIError):
            pass

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
        cpu_stats = stats.get("cpu_stats", {})
        precpu_stats = stats.get("precpu_stats", {})

        total_cpu = cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        pre_total_cpu = precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        cpu_delta = total_cpu - pre_total_cpu

        system_cpu = cpu_stats.get("system_cpu_usage", 0)
        pre_system_cpu = precpu_stats.get("system_cpu_usage", 0)
        system_delta = system_cpu - pre_system_cpu

        num_cpus = cpu_stats.get("online_cpus", 1)

        cpu_percent = 0.0
        if system_delta > 0 and cpu_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * num_cpus * 100.0

        memory_stats = stats.get("memory_stats", {})
        memory_usage = memory_stats.get("usage", 0)
        memory_mb = memory_usage / (1024 * 1024)

        return cpu_percent, memory_mb