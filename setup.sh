#!/usr/bin/env bash
# One-command setup for Linux / macOS. Re-runnable.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> System packages (espeak-ng, ffmpeg)"
if command -v apt-get >/dev/null; then
  sudo apt-get update -qq && sudo apt-get install -y espeak-ng ffmpeg python3-venv
elif command -v brew >/dev/null; then
  brew install espeak-ng ffmpeg
elif command -v dnf >/dev/null; then
  sudo dnf install -y espeak-ng ffmpeg python3
else
  echo "Install espeak-ng and ffmpeg manually, then re-run." >&2
fi

echo "==> Ollama"
if ! command -v ollama >/dev/null; then
  if [[ "$(uname)" == "Darwin" ]]; then
    brew install ollama
  else
    curl -fsSL https://ollama.com/install.sh | sh
  fi
fi
if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null; then
  (ollama serve >/dev/null 2>&1 &) ; sleep 3
fi

echo "==> Python environment"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
[[ -f .env ]] || cp .env.example .env

echo "==> Models (one-time download)"
.venv/bin/python download_models.py "$@"

echo
echo "Done. Start with: ./run.sh   then open http://127.0.0.1:8000"
