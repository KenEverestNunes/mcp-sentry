"""FastAPI application entry point for MCP-Sentry."""

from mcp_sentry.api.app import HealthResponse, app

__all__ = ["app", "HealthResponse"]
