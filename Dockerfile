FROM python:3.12-slim

# Render runs the container in UTC by default, but To-Do due dates are stored as
# the user's local (wall-clock) time. Run the container in Europe/Warsaw so
# datetime.now() matches the stored due_at and reminders fire on time.
# tzdata is required for the TZ env var to take effect on a slim image.
ENV TZ=Europe/Warsaw
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cache layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY src/ src/

# Install the project itself
RUN uv sync --frozen --no-dev

EXPOSE 8080

CMD ["sh", "-c", "uv run uvicorn --app-dir src exsize.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
