# syntax=docker/dockerfile:1
ARG BUILD_HASH=dev-build

######## Frontend (arch-independent, run natively on build host) ########
FROM --platform=$BUILDPLATFORM node:24-alpine AS build
ARG BUILD_HASH

WORKDIR /app

RUN apk add --no-cache git

COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps

COPY . .
ENV APP_BUILD_HASH=${BUILD_HASH}
RUN npm run build

######## Backend ########
FROM python:3.12-alpine AS base

RUN apk add --no-cache bash

ENV PYTHONUNBUFFERED=1
ENV ENV=prod \
    PORT=8080

WORKDIR /app/backend

COPY ./package.json ./LICENSE ./README.md ./pyproject.toml /app/
COPY ./backend .
COPY --from=build /app/build /app/build

# Precompile bytecode makes startup much faster, 3s->1s.
# At the cost of increased Docker image compressed size, 
# +7M gzip or +6M zstd at default levels.
RUN pip3 install --no-cache-dir uv && \
    uv pip compile --no-header --all-extras /app/pyproject.toml -o /tmp/requirements.txt && \
    uv pip install --system --no-cache-dir -r /tmp/requirements.txt && \
    pip3 uninstall -y uv pip && \
    rm /tmp/requirements.txt && \
    python3 -m compileall -q /usr/local/lib/python3.12/site-packages/ && \
    mkdir -p /app/backend/data

EXPOSE 8080

HEALTHCHECK CMD python3 -c "import urllib.request,json,sys;r=urllib.request.urlopen('http://localhost:${PORT:-8080}/health');sys.exit(0 if json.load(r).get('status') else 1)"

ARG BUILD_HASH
ENV WEBUI_BUILD_VERSION=${BUILD_HASH}
ENV DOCKER=true

CMD ["bash", "start.sh"]