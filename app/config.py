import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b")
LLM_CTX = int(os.getenv("LLM_CTX", "2048"))
HISTORY_TURNS = int(os.getenv("HISTORY_TURNS", "6"))

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")  # tiny | base | small
WHISPER_DIR = MODELS / "whisper"
PIPER_DIR = MODELS / "piper"
MAX_LOADED_VOICES = int(os.getenv("MAX_LOADED_VOICES", "2"))
