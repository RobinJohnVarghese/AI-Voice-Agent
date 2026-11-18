"""Orchestrator: routes text->text and voice->voice through STT, LLM, phonetics and TTS.

``stream`` yields events so the UI can show text as it is generated and play each
sentence as soon as it is synthesized:
  transcript -> delta* -> sentence* -> done      (or error)
"""
import base64
import re
from collections.abc import Iterator

from . import lang, phonetics, pronunciation
from .llm import LLM, LLMError
from .store import Store

# sentence end: western marks followed by whitespace, CJK/Indic marks, or newlines
_BOUNDARY = re.compile(r"[.!?…]+[\"')\]»”]*\s+|[。！？।॥]+\s*|\n+")
MIN_SENTENCE = 8  # shorter sentences ("Oui.") are merged with the next one


def _cut(buf: str) -> int:
    """Index just after the first sentence boundary that yields a long-enough sentence, else 0."""
    for m in _BOUNDARY.finditer(buf):
        if len(buf[:m.end()].strip()) >= MIN_SENTENCE:
            return m.end()
    return 0


class Pipeline:
    def __init__(self, stt=None, llm=None, tts=None, store=None):
        if stt is None:
            from .stt import STT
            stt = STT()
        if tts is None:
            from .tts import TTS
            tts = TTS()
        self.stt, self.tts = stt, tts
        self.llm = llm or LLM()
        self.store = store or Store()

    # ----------------------------------------------------------------- streaming
    def stream(self, session: str, text: str | None = None, audio_path: str | None = None,
               force_lang: str | None = None, speak: bool = False, slow: bool = False) -> Iterator[dict]:
        mode = "voice" if audio_path else "text"
        if audio_path:
            tr = self.stt.transcribe(audio_path, language=force_lang)
            if not tr.text:
                yield {"type": "error", "message": "No speech detected, please try again."}
                return
            text = tr.text
            code = force_lang or (tr.lang if tr.lang in lang.LANGS else "en")
            yield {"type": "transcript", "text": text, "lang": code, "lang_name": lang.name(code),
                   "unclear_words": [w["word"] for w in tr.words if w["prob"] < 0.5]}
        else:
            text = (text or "").strip()
            if not text:
                yield {"type": "error", "message": "Empty message."}
                return
            code = force_lang or lang.detect(text)

        history = self.store.history(session, limit=40)
        messages = self.llm.messages(history, text, code)
        reply, buf, index = "", "", 0
        try:
            for tok in self.llm.stream(messages):
                reply += tok
                buf += tok
                yield {"type": "delta", "text": tok}
                while end := _cut(buf):
                    sentence, buf = buf[:end].strip(), buf[end:]
                    yield self._sentence(sentence, code, index, speak, slow)
                    index += 1
        except LLMError as e:
            yield {"type": "error", "message": str(e)}
            return
        if buf.strip():
            yield self._sentence(buf.strip(), code, index, speak, slow)

        reply = reply.strip()
        reply_lang = lang.detect(reply, default=code) if len(reply) > 25 else code
        self.store.add_message(session, "user", text, code, mode)
        self.store.add_message(session, "assistant", reply, reply_lang, mode)
        yield {"type": "done", "mode": mode, "reply": reply, "user_lang": code,
               "lang": reply_lang, "lang_name": lang.name(reply_lang)}

    def _sentence(self, sentence: str, code: str, index: int, speak: bool, slow: bool) -> dict:
        # replies may switch language (e.g. 'Hello in French is "Bonjour".'), so work per language run
        runs = lang.spans(sentence, code)
        s_code = max(runs, key=lambda r: len(r[0]))[1]
        ev = {"type": "sentence", "index": index, "text": sentence, "lang": s_code,
              "langs": sorted({c for _, c in runs}), **phonetics.annotate(sentence, code, mixed=True)}
        if speak:
            ev["audio_b64"] = base64.b64encode(self.tts.synthesize(sentence, code, slow=slow)).decode()
        return ev

    # ------------------------------------------------------------ non-streaming
    def turn(self, session: str, text: str | None = None, audio_path: str | None = None,
             force_lang: str | None = None, slow: bool = False) -> dict:
        out: dict = {"sentences": []}
        for ev in self.stream(session, text, audio_path, force_lang, speak=False):
            t = ev.pop("type")
            if t == "error":
                return {"error": ev["message"]}
            if t == "transcript":
                out.update(transcript=ev["text"], unclear_words=ev["unclear_words"])
            elif t == "sentence":
                out["sentences"].append(ev)
            elif t == "done":
                out.update(ev)
        out.update(phonetics.annotate(out["reply"], out["lang"], mixed=True))
        if audio_path:  # voice in -> voice out
            out["audio_b64"] = base64.b64encode(self.tts.synthesize(out["reply"], out["lang"], slow)).decode()
        return out

    def practice(self, target: str, audio_path: str, code: str | None = None) -> dict:
        code = code or lang.detect(target)
        tr = self.stt.transcribe(audio_path, language=code)
        result = pronunciation.score(target, tr.text, tr.words, code)
        result.update(lang=code, target_ipa=phonetics.to_ipa(target, code),
                      target_readable=phonetics.respell(target, code),
                      target_romanized=phonetics.romanize(target, code))
        result["attempt_id"] = self.store.add_attempt(target, code, result)
        return result

    def speak(self, text: str, code: str | None = None, slow: bool = False) -> bytes:
        return self.tts.synthesize(text, code or lang.detect(text), slow=slow)
