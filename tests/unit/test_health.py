"""Unit tests for the health check endpoint."""

import pytest
import httpx

from mcp_sentry.api.main import app


@pytest.mark.anyio
async def test_health_returns_200() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_health_returns_ok_status() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.json() == {"status": "ok"}
