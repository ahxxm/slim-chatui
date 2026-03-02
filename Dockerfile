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
FROM python:3.12-slim-trixie AS base

ARG USE_PERMISSION_HARDENING
ARG UID
ARG GID

ENV PYTHONUNBUFFERED=1

ENV ENV=prod \
    PORT=8080

ENV OPENAI_API_BASE_URL=""

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

COPY --chown=$UID:$GID ./package.json ./LICENSE ./README.md ./pyproject.toml ./hatch_build.py /app/
COPY --chown=$UID:$GID ./backend .
COPY --chown=$UID:$GID --from=build /app/build /app/build

RUN pip3 install --no-cache-dir uv && \
    uv pip compile --no-header --all-extras /app/pyproject.toml -o /tmp/requirements.txt && \
    uv pip install --system --no-cache-dir -r /tmp/requirements.txt && \
    pip3 uninstall -y uv pip && \
    rm /tmp/requirements.txt && \
    mkdir -p /app/backend/data && chown -R $UID:$GID /app/backend/data/

EXPOSE 8080

HEALTHCHECK CMD python3 -c "import urllib.request,json,sys;r=urllib.request.urlopen('http://localhost:${PORT:-8080}/health');sys.exit(0 if json.load(r).get('status') else 1)"

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
