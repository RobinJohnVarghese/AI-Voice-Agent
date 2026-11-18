"""One-time model download (needs internet). After this, everything runs offline.

Usage: python download_models.py [piper voice names...]
Browse voices: https://huggingface.co/rhasspy/piper-voices
"""
import json
import subprocess
import sys

import requests
from faster_whisper import WhisperModel

from app import config

DEFAULT_VOICES = ["en_US-lessac-medium", "es_ES-davefx-medium", "fr_FR-siwis-medium",
                  "de_DE-thorsten-medium", "hi_IN-pratham-medium"]


def pull_llm():
    """Pull through Ollama's HTTP API so it also works from a container without the CLI."""
    print(f"Pulling {config.LLM_MODEL} via {config.OLLAMA_URL} ...")
    with requests.post(f"{config.OLLAMA_URL}/api/pull", json={"model": config.LLM_MODEL}, stream=True,
                       timeout=(10, None)) as r:
        r.raise_for_status()
        last = ""
        for line in r.iter_lines():
            msg = json.loads(line)
            if "error" in msg:
                sys.exit(f"Ollama error: {msg['error']}")
            if msg.get("status") != last:
                last = msg.get("status", "")
                print("  ", last)


voices = sys.argv[1:] or DEFAULT_VOICES
config.PIPER_DIR.mkdir(parents=True, exist_ok=True)
subprocess.run([sys.executable, "-m", "piper.download_voices", "--data-dir", str(config.PIPER_DIR), *voices],
               check=True)
print(f"Downloading Whisper '{config.WHISPER_MODEL}' ...")
WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8", download_root=str(config.WHISPER_DIR))
pull_llm()
print("All models downloaded. You can now go offline.")
