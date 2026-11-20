"""Local LLM via Ollama (quantized GGUF model, CPU friendly), streamed token by token."""
import json
from collections.abc import Iterator
from datetime import datetime

import requests

from . import config, lang

SYSTEM = """You are a friendly multilingual speaking and pronunciation tutor running fully offline.
Current local date and time: {now}. Use it for any question about the day, date or time.
Rules:
- Reply in {lang_name} unless the user explicitly asks for another language.
- Keep replies short: 1 to 3 sentences, because they may be read aloud.
- Use complete, correct punctuation (commas, periods, question marks); it controls pauses and intonation.
- No markdown, no bullet lists, no emojis, no IPA (phonetics are added automatically).
- If the user's message has a grammar or word-choice mistake, start your reply with the corrected sentence
  (for example: "Correction: Me gusta la música."), then continue the conversation.
- When asked how to say or pronounce something, give the phrase itself and a simple syllable breakdown like "bon-ZHOOR"."""


class LLMError(RuntimeError):
    pass


class LLM:
    def messages(self, history: list[dict], user_text: str, lang_code: str) -> list[dict]:
        msgs = [{"role": "system", "content": SYSTEM.format(lang_name=lang.name(lang_code),
                                                         now=datetime.now().strftime("%A, %d %B %Y, %H:%M"))}]
        msgs += [{"role": m["role"], "content": m["content"]} for m in history[-config.HISTORY_TURNS * 2:]]
        # A per-turn reminder keeps small models from drifting into the language of earlier turns.
        msgs.append({"role": "user", "content": f"{user_text}\n\n(Reply in {lang.name(lang_code)}.)"})
        return msgs

    def stream(self, messages: list[dict]) -> Iterator[str]:
        try:
            r = requests.post(f"{config.OLLAMA_URL}/api/chat", stream=True, timeout=(5, 300), json={
                "model": config.LLM_MODEL, "messages": messages, "stream": True,
                "keep_alive": config.LLM_KEEP_ALIVE,
                "options": {"num_ctx": config.LLM_CTX, "temperature": 0.6, "num_predict": 220},
            })
            r.raise_for_status()
        except requests.RequestException as e:
            raise LLMError(f"Cannot reach Ollama at {config.OLLAMA_URL} ({e}). Is `ollama serve` running "
                           f"and is `{config.LLM_MODEL}` pulled?") from e
        with r:
            for line in r.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if "error" in data:
                    raise LLMError(data["error"])
                if tok := data.get("message", {}).get("content"):
                    yield tok
                if data.get("done"):
                    break

    def ping(self) -> bool:
        try:
            tags = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=2).json()
            return any(m["name"].startswith(config.LLM_MODEL) for m in tags.get("models", []))
        except requests.RequestException:
            return False
