import asyncio

from mcp_sentry.client import MCPClient
from mcp_sentry.config.target_configs import TargetConfig
from mcp_sentry.evaluation import EvaluationEngine, _compile_patterns
from mcp_sentry.fuzzing.engine import FuzzEngine
from mcp_sentry.models.schemas import SessionReport
from mcp_sentry.sandbox.docker_runner import DockerSandbox
from mcp_sentry.sandbox.observer import Observer


class SessionOrchestrator:
    """
    Coordinates sandbox lifecycle, client connection, fuzzing execution,
    out-of-band observer metrics, and evaluation verdict scoring.
    """

    def __init__(self, sandbox: DockerSandbox | None = None) -> None:
        self.sandbox = sandbox or DockerSandbox()
        self.evaluator = EvaluationEngine()
        self.fuzzer = FuzzEngine()

    async def run(
        self,
        config: TargetConfig,
        image: str,
        timeout_s: float = 60.0,
    ) -> SessionReport:
        handle = await self.sandbox.start(image)
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
            await self.sandbox.stop(handle)
