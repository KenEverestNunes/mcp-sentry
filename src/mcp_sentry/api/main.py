"""FastAPI application entry point for MCP-Sentry."""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="MCP-Sentry",
    description="AI-powered Sentry error monitoring via the Model Context Protocol.",
    version="0.1.0",
)

class HealthResponse(BaseModel):
    status: str

@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health_check() -> HealthResponse:
    """Return service liveness — no external dependencies required."""
    return HealthResponse(status="ok")
