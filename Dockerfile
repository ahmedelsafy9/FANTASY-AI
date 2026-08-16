# syntax=docker/dockerfile:1
#
# Production image for the Fantasy-AI FastAPI backend.
#
# The real backend lives at "back final/Fantasy-AI/" in this repo (NOT
# at the repository root) — this Dockerfile is written to build from
# the repo root as its context (matching fly.toml's default [build]
# behavior) but pulls everything FROM that nested directory explicitly.
#
# REQUIRED BUILD-CONTEXT CONTENT (not committed to git — see
# back final/Fantasy-AI/.gitignore):
#   back final/Fantasy-AI/models/best_model.joblib
#   back final/Fantasy-AI/models/best_model_metadata.json
#   back final/Fantasy-AI/data/processed/vaastav_features.csv
# These MUST exist on the machine running `docker build` / `fly deploy`
# before building — produce them by running the pipeline locally
# (scripts.run_feature_engineering, scripts.run_training) or restoring
# them from wherever they're normally kept. The build will still
# succeed without them, but the API will start in a permanent
# "not_ready" (503) state — see AppState/build_app_state.

FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (better layer caching: this layer is only
# invalidated when requirements.txt changes, not on every code change).
COPY ["back final/Fantasy-AI/requirements.txt", "requirements.txt"]
RUN python -m venv .venv \
    && .venv/bin/pip install --upgrade pip \
    && .venv/bin/pip install -r requirements.txt


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8080 \
    FANTASY_AI_ENV=production

WORKDIR /app

COPY --from=builder /app/.venv .venv/

# Application code only — no tests, scripts, docs, git metadata, or
# frontend. Paths are chosen so src/config/settings.py's dynamically
# resolved project root (parents[2] of settings.py) lands on /app,
# matching the app's own data/models path resolution unmodified.
COPY ["back final/Fantasy-AI/src", "src"]

# Runtime artifacts required at startup (see header note above). If
# these are absent from the build context, .dockerignore does NOT
# exclude them — an empty/missing directory just means the API starts
# in a degraded/not_ready state rather than failing the build, which
# is intentional (matches build_app_state's existing graceful-startup
# behavior for a missing model).
COPY ["back final/Fantasy-AI/models", "models"]
COPY ["back final/Fantasy-AI/data/processed", "data/processed"]

# Runs as a non-root user.
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Fly.io does not auto-inject $PORT the way some other platforms do —
# the app listens on whatever this is set to, and fly.toml's
# [http_service].internal_port MUST match. Both default to 8080; if
# you override one via a Fly secret/env var, update the other too.
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
