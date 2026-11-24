import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from mcp_sentry.config.target_configs import TARGET_CONFIGS
from mcp_sentry.models.schemas import RunRecord, RunRequest
from mcp_sentry.session import SessionOrchestrator

router = APIRouter(prefix="/runs", tags=["runs"])
logger = logging.getLogger(__name__)

RUNS: dict[str, RunRecord] = {}
_RUN_LOCK = asyncio.Lock()
_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()


async def _execute_run(run_id: str, target: str) -> None:
    try:
        record = RUNS[run_id]
        record.status = "running"
        orchestrator = SessionOrchestrator()
        config = TARGET_CONFIGS[target]
        image = f"mcp-sentry/{target}:local"
        report = await orchestrator.run(config=config, image=image)
        record.status = "completed"
        record.report = report
    except Exception as exc:
        record.status = "failed"
        logger.exception("Run %s failed: %s", run_id, exc)
        if hasattr(exc, "exceptions"):
            sub_msgs = "; ".join(f"{type(e).__name__}: {e}" for e in exc.exceptions)
            record.error = f"{type(exc).__name__}: {sub_msgs}"
        else:
            record.error = f"{type(exc).__name__}: {exc}"
    finally:
        if _RUN_LOCK.locked():
            _RUN_LOCK.release()


@router.post("", response_model=RunRecord, status_code=200)
async def create_run(req: RunRequest) -> RunRecord:
    if req.target not in TARGET_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown target '{req.target}'. Allowed targets: {list(TARGET_CONFIGS.keys())}",
        )

    if _RUN_LOCK.locked():
        raise HTTPException(
            status_code=409,
            detail="A fuzzing run is already in progress.",
        )

    await _RUN_LOCK.acquire()

    run_id = str(uuid.uuid4())
    record = RunRecord(run_id=run_id, status="pending")
    RUNS[run_id] = record

    task = asyncio.create_task(_execute_run(run_id, req.target))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    return record


@router.get("/{run_id}", response_model=RunRecord)
async def get_run(run_id: str) -> RunRecord:
    record = RUNS.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return record


@router.get("", response_model=list[RunRecord])
async def list_runs() -> list[RunRecord]:
    return list(RUNS.values())
