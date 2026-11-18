"""One-time model download (needs internet). After this, everything runs offline.

Usage: python download_models.py [piper voice names...]
Browse voices: https://huggingface.co/rhasspy/piper-voices
"""
import subprocess
import sys

from faster_whisper import WhisperModel

from app import config

DEFAULT_VOICES = ["en_US-lessac-medium", "es_ES-davefx-medium", "fr_FR-siwis-medium",
                  "de_DE-thorsten-medium", "hi_IN-pratham-medium"]

voices = sys.argv[1:] or DEFAULT_VOICES
config.PIPER_DIR.mkdir(parents=True, exist_ok=True)
subprocess.run([sys.executable, "-m", "piper.download_voices", "--data-dir", str(config.PIPER_DIR), *voices], check=True)
WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8", download_root=str(config.WHISPER_DIR))
subprocess.run(["ollama", "pull", config.LLM_MODEL], check=True)
print("All models downloaded. You can now go offline.")
