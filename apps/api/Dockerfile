# syntax=docker/dockerfile:1
#
# SkillForge single-container image.
#
# Stage 1 builds the Next.js static export. Stage 2 installs the Python API and
# copies the export in at /opt/skillforge/web. The CLI's `skillforge serve`
# detects it via SKILLFORGE_WEB_DIR and serves everything from one port.
#
# Build context must be the repo root so both apps/ subdirs are visible:
#   docker build -t skillforge -f apps/api/Dockerfile .

# ---------- Stage 1: build the Web UI export ----------
FROM node:20-alpine AS web-builder
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY apps/web/ ./
# Empty NEXT_PUBLIC_API_URL = same-origin (the API serves the UI).
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build
# Result: /web/out

# ---------- Stage 2: Python runtime + API + exported UI ----------
FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the API package.
COPY apps/api/pyproject.toml apps/api/README.md ./
COPY apps/api/skillforge_api ./skillforge_api
RUN pip install --no-cache-dir .

# Install the CLI (depends on the API package, already installed above).
COPY apps/cli/pyproject.toml ./cli-pyproject.toml
COPY apps/cli/skillforge_cli ./skillforge_cli
# The CLI's pyproject declares a dependency on skillforge-api; skip deps to
# avoid reinstalling and just install the package itself.
RUN pip install --no-cache-dir --no-deps -e . \
    || (sed 's/"skillforge-api",//g' cli-pyproject.toml > pyproject.toml && pip install --no-cache-dir --no-deps .)

# Bring in the pre-built Web UI export and tell the API where to find it.
COPY --from=web-builder /web/out /opt/skillforge/web
ENV SKILLFORGE_WEB_DIR=/opt/skillforge/web \
    SKILLFORGE_AI_PROVIDER=mock \
    SKILLFORGE_API_HOST=0.0.0.0 \
    SKILLFORGE_API_PORT=8000 \
    SKILLFORGE_SKILLS_DIR=/data/skills \
    SKILLFORGE_DB_PATH=/data/skillforge.db

EXPOSE 8000

# `skillforge serve` serves the API + bundled Web UI on one port.
CMD ["skillforge", "serve", "--host", "0.0.0.0", "--port", "8000"]
