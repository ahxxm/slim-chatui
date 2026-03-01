# syntax=docker/dockerfile:1
ARG USE_PERMISSION_HARDENING=false
ARG BUILD_HASH=dev-build
# Override at your own risk - non-root configurations are untested
ARG UID=0
ARG GID=0

######## Frontend ########
FROM --platform=$BUILDPLATFORM node:22-alpine3.20 AS build
ARG BUILD_HASH

WORKDIR /app

RUN apk add --no-cache git

COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps

COPY . .
ENV APP_BUILD_HASH=${BUILD_HASH}
RUN npm run build

######## Backend ########
FROM python:3.12-slim-bookworm AS base

ARG USE_PERMISSION_HARDENING
ARG UID
ARG GID

ENV PYTHONUNBUFFERED=1

ENV ENV=prod \
    PORT=8080

ENV OLLAMA_BASE_URL="/ollama" \
    OPENAI_API_BASE_URL=""

ENV OPENAI_API_KEY="" \
    WEBUI_SECRET_KEY="" \
    ANONYMIZED_TELEMETRY=false

WORKDIR /app/backend

ENV HOME=/root
RUN if [ $UID -ne 0 ]; then \
    if [ $GID -ne 0 ]; then \
    addgroup --gid $GID app; \
    fi; \
    adduser --uid $UID --gid $GID --home $HOME --disabled-password --no-create-home app; \
    fi

RUN chown -R $UID:$GID /app $HOME

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git build-essential gcc netcat-openbsd curl jq \
    python3-dev zstd \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=$UID:$GID ./pyproject.toml /app/pyproject.toml
COPY --chown=$UID:$GID ./hatch_build.py /app/hatch_build.py
COPY --chown=$UID:$GID ./backend .

RUN pip3 install --no-cache-dir uv && \
    uv pip install --system --no-cache-dir '/app[all]' && \
    mkdir -p /app/backend/data && chown -R $UID:$GID /app/backend/data/

# copy built frontend files
COPY --chown=$UID:$GID --from=build /app/build /app/build
COPY --chown=$UID:$GID --from=build /app/package.json /app/package.json

EXPOSE 8080

HEALTHCHECK CMD curl --silent --fail http://localhost:${PORT:-8080}/health | jq -ne 'input.status == true' || exit 1

# Minimal, atomic permission hardening for OpenShift (arbitrary UID):
# - Group 0 owns /app and /root
# - Directories are group-writable and have SGID so new files inherit GID 0
RUN if [ "$USE_PERMISSION_HARDENING" = "true" ]; then \
    set -eux; \
    chgrp -R 0 /app /root || true; \
    chmod -R g+rwX /app /root || true; \
    find /app -type d -exec chmod g+s {} + || true; \
    find /root -type d -exec chmod g+s {} + || true; \
    fi

USER $UID:$GID

ARG BUILD_HASH
ENV WEBUI_BUILD_VERSION=${BUILD_HASH}
ENV DOCKER=true

CMD [ "bash", "start.sh"]
