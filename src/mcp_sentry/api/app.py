"""FastAPI application for MCP-Sentry."""

from fastapi import FastAPI
from pydantic import BaseModel

from mcp_sentry.api.runs import router as runs_router
from mcp_sentry.config.target_configs import TARGET_CONFIGS

app = FastAPI(
    title="MCP-Sentry",
    description="AI-powered MCP error monitoring and fuzzing triage.",
    version="0.1.0",
)


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
