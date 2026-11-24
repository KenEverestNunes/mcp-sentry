"""FastAPI application for MCP-Sentry."""

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from mcp_sentry.api.runs import router as runs_router
from mcp_sentry.config.target_configs import TARGET_CONFIGS

app = FastAPI(
    title="MCP-Sentry",
    description="AI-powered MCP error monitoring and fuzzing triage.",
    version="0.1.0",
)


@app.middleware("http")
async def add_no_cache_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response: Response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health_check() -> HealthResponse:
    """Return service liveness — no external dependencies required."""
    return HealthResponse(status="ok")


@app.get("/targets", response_model=list[str], tags=["targets"])
async def get_targets() -> list[str]:
    """Return list of supported target names from TARGET_CONFIGS."""
    return list(TARGET_CONFIGS.keys())


app.include_router(runs_router)

# Mount frontend static directory at root
_frontend_dir = Path(__file__).resolve().parent.parent.parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
