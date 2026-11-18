#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null; then
  (ollama serve >/dev/null 2>&1 &) ; sleep 3
fi
exec .venv/bin/uvicorn app.server:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
