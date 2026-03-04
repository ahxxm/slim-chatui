#!/usr/bin/env bash
export SKIP_FRONTEND_BUILD=true
export CORS_ALLOW_ORIGIN="*"
export WEBUI_AUTH=false
PORT="${PORT:-8080}"
BACKEND_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ "$1" == "--fresh" ]]; then
    rm -f "$BACKEND_DIR/data/webui.db"
fi

uv run --directory "$BACKEND_DIR" uvicorn open_webui.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --timeout-keep-alive 75 \
    --forwarded-allow-ips '*' \
    --reload
