FROM python:3.12-slim

# Install Astral uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock /app/

# Install dependencies using frozen lockfile
RUN uv sync --frozen --no-install-project --no-dev

# Copy application source code and frontend assets
COPY src/ /app/src/
COPY frontend/ /app/frontend/
COPY README.md /app/README.md

# Install project package into the virtual environment
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:/app"
ENV PORT=8080

EXPOSE 8080

CMD ["sh", "-c", "uvicorn mcp_sentry.api.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
