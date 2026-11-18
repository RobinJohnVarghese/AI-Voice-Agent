"""Local LLM via Ollama (quantized GGUF model, CPU friendly)."""
import requests

from . import config, lang

SYSTEM = """You are a friendly multilingual speaking and pronunciation tutor running fully offline.
Rules:
- Reply in {lang_name} unless the user explicitly asks for another language.
- Keep replies short: 1 to 3 sentences, because they may be read aloud.
- Use complete, correct punctuation (commas, periods, question marks); it controls pauses and intonation.
- No markdown, no bullet lists, no emojis, no IPA (phonetics are added automatically).
- If the user's message has a grammar or word-choice mistake, start your reply with the corrected sentence
  (for example: "Correction: Me gusta la música."), then continue the conversation.
- When asked how to say or pronounce something, give the phrase itself and a simple syllable breakdown like "bon-JOOR"."""


class LLM:
    def __init__(self):
        self.sessions: dict[str, list[dict]] = {}

    def chat(self, session_id: str, user_text: str, lang_code: str) -> str:
        history = self.sessions.setdefault(session_id, [])
        messages = [{"role": "system", "content": SYSTEM.format(lang_name=lang.name(lang_code))}]
        messages += history[-config.HISTORY_TURNS * 2:]
        messages.append({"role": "user", "content": user_text})
        r = requests.post(f"{config.OLLAMA_URL}/api/chat", timeout=300, json={
            "model": config.LLM_MODEL, "messages": messages, "stream": False, "keep_alive": "30m",
            "options": {"num_ctx": config.LLM_CTX, "temperature": 0.6, "num_predict": 200},
        })
        r.raise_for_status()
        reply = r.json()["message"]["content"].strip()
        history += [{"role": "user", "content": user_text}, {"role": "assistant", "content": reply}]
        return reply

    def reset(self, session_id: str):
        self.sessions.pop(session_id, None)
