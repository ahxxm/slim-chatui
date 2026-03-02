#!/usr/bin/env bash
export HATCH_BUILD_HOOKS_ENABLE=false
export CORS_ALLOW_ORIGIN="*"
export WEBUI_AUTH=false
PORT="${PORT:-8080}"
BACKEND_DIR="$(cd "$(dirname "$0")" && pwd)"
rm -f "$BACKEND_DIR/data/webui.db"
uv run --directory "$BACKEND_DIR" uvicorn open_webui.main:app --port "$PORT" --host 0.0.0.0 --forwarded-allow-ips '*' --reload
