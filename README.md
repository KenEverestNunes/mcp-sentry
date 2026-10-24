# MCP-Sentry

An MCP (Model Context Protocol) server that integrates with Sentry for AI-powered error monitoring and triage.

## Setup

```bash
uv sync --all-extras
```

## Development

```bash
make lint    # ruff + mypy
make test    # pytest
make run     # uvicorn dev server → http://localhost:8000
```

## Health Check

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```
