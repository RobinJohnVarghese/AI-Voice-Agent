"""Orchestrator: routes text->text and voice->voice through STT, LLM, phonetics and TTS."""
import base64

from . import lang, phonetics, pronunciation
from .llm import LLM
from .stt import STT
from .tts import TTS


class Pipeline:
    def __init__(self):
        self.stt, self.llm, self.tts = STT(), LLM(), TTS()

    def _reply(self, session: str, text: str, code: str) -> dict:
        reply = self.llm.chat(session, text, code)
        reply_lang = lang.detect(reply, default=code)
        return {"reply": reply, "lang": reply_lang, "lang_name": lang.name(reply_lang),
                "ipa": phonetics.to_ipa(reply, reply_lang)}

    def text_turn(self, session: str, text: str, force_lang: str | None = None) -> dict:
        code = force_lang or lang.detect(text)
        return {"mode": "text", "user_lang": code, **self._reply(session, text, code)}

    def voice_turn(self, session: str, audio_path: str, force_lang: str | None = None,
                   slow: bool = False) -> dict:
        tr = self.stt.transcribe(audio_path, language=force_lang)
        if not tr.text:
            return {"mode": "voice", "error": "No speech detected, please try again."}
        code = force_lang or (tr.lang if tr.lang in lang.LANGS else "en")
        out = self._reply(session, tr.text, code)
        wav = self.tts.synthesize(out["reply"], out["lang"], slow=slow)
        unclear = [w["word"] for w in tr.words if w["prob"] < 0.5]
        return {"mode": "voice", "transcript": tr.text, "user_lang": code, "unclear_words": unclear,
                "audio_b64": base64.b64encode(wav).decode(), **out}

    def practice(self, target: str, audio_path: str, code: str | None = None) -> dict:
        code = code or lang.detect(target)
        tr = self.stt.transcribe(audio_path, language=code)
        result = pronunciation.score(target, tr.text, tr.words, code)
        result["target_ipa"] = phonetics.to_ipa(target, code)
        return result

    def speak(self, text: str, code: str | None = None, slow: bool = False) -> bytes:
        return self.tts.synthesize(text, code or lang.detect(text), slow=slow)
