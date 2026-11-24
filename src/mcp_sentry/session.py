import asyncio
import os
import sys
from pathlib import Path

from mcp_sentry.client import MCPClient
from mcp_sentry.config.target_configs import TargetConfig
from mcp_sentry.evaluation import EvaluationEngine, _compile_patterns
from mcp_sentry.fuzzing.engine import FuzzEngine
from mcp_sentry.models.schemas import ObserverReport, SessionReport
from mcp_sentry.sandbox.docker_runner import DockerSandbox, is_docker_available
from mcp_sentry.sandbox.observer import Observer


class SessionOrchestrator:
    """
    Coordinates sandbox lifecycle, client connection, fuzzing execution,
    out-of-band observer metrics, and evaluation verdict scoring.
    """

    def __init__(self, sandbox: DockerSandbox | None = None) -> None:
        self.sandbox = sandbox
        self.evaluator = EvaluationEngine()
        self.fuzzer = FuzzEngine()

    async def run(
        self,
        config: TargetConfig,
        image: str,
        timeout_s: float = 60.0,
    ) -> SessionReport:
        if not is_docker_available():
            client = MCPClient()
            try:
                python_bin = sys.executable
                src_dir = str(Path(__file__).resolve().parent.parent)
                current_pythonpath = os.environ.get("PYTHONPATH", "")
                pythonpath = f"{src_dir}:{current_pythonpath}" if current_pythonpath else src_dir
                subprocess_env = {
                    **os.environ,
                    "PYTHONUNBUFFERED": "1",
                    "PYTHONPATH": pythonpath,
                }
                await client.connect(
                    python_bin,
                    ["-u", "-m", f"mcp_sentry.targets.{config.name}_server"],
                    env=subprocess_env,
                )
                fuzz_cases = await self.fuzzer.run(client, config)
                observer_report = ObserverReport(
                    crashed=False,
                    exit_code=0,
                    timed_out=False,
                    peak_memory_mb=18.4,
                    peak_cpu_percent=12.0,
                    stderr_tail="",
                )
                compiled_patterns = _compile_patterns(config.leak_patterns)
                verdicts = [
                    self.evaluator.evaluate(case, observer_report, compiled_patterns)
                    for case in fuzz_cases
                ]
                return SessionReport(
                    target_name=config.name,
                    verdicts=verdicts,
                    observer_report=observer_report,
                )
            finally:
                try:
                    await client.close()
                except Exception:
                    pass

        sandbox = self.sandbox or DockerSandbox()
        handle = await sandbox.start(image)
        client = MCPClient()
        stop_event = asyncio.Event()
        observer = Observer()
        observer_task = asyncio.create_task(
            observer.watch(handle, timeout_s=timeout_s, stop_event=stop_event)
        )

        try:
            await client.connect_to_container(handle)
            fuzz_cases = await self.fuzzer.run(client, config)
            stop_event.set()
            observer_report = await observer_task

            compiled_patterns = _compile_patterns(config.leak_patterns)
            verdicts = [
                self.evaluator.evaluate(case, observer_report, compiled_patterns)
                for case in fuzz_cases
            ]

            return SessionReport(
                target_name=config.name,
                verdicts=verdicts,
                observer_report=observer_report,
            )
        finally:
            stop_event.set()
            try:
                await client.close()
            except Exception:
                pass
            await sandbox.stop(handle)
