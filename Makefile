.PHONY: install lint test run

install:
	uv sync --all-extras

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy src

test:
	uv run pytest tests/ -v

run:
	uv run uvicorn mcp_sentry.api.main:app --reload
