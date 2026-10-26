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

## Demo Targets

The demo target servers are intended to show how MCP tools can behave in different ways: Healthy is the well-behaved baseline, Fragile is designed to crash on bad input, and Leaky is intended to expose secrets under certain input. Only Healthy is implemented today; Fragile and Leaky are planned examples and are not available yet.
