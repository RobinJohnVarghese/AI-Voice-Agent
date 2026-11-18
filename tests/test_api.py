"""API tests with fake STT/LLM/TTS so they run without models."""
import io
import wave

import pytest
from fastapi.testclient import TestClient

from app import server
from app.pipeline import Pipeline
from app.store import Store
from app.stt import Transcript


class FakeSTT:
    def transcribe(self, path, language=None):
        return Transcript("Bonjour, je voudrais un café.", language or "fr", 0.99,
                          [{"word": w, "prob": 0.9} for w in "Bonjour, je voudrais un café.".split()])


class FakeLLM:
    def messages(self, history, text, code):
        return [{"role": "user", "content": text}]

    def stream(self, messages):
        yield from ["Très bien. ", "Voulez-vous ", "un croissant aussi ?"]

    def ping(self):
        return True


class FakeTTS:
    available = {"fr": None}

    def synthesize(self, text, code, slow=False):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(b"\0\0" * 100)
        return buf.getvalue()


@pytest.fixture
def client():
    pipe = Pipeline(stt=FakeSTT(), llm=FakeLLM(), tts=FakeTTS(), store=Store(":memory:"))
    server.app.dependency_overrides[server.get_pipe] = lambda: pipe
    yield TestClient(server.app)
    server.app.dependency_overrides.clear()


def _events(resp):
    import json
    return [json.loads(l) for l in resp.text.splitlines() if l.strip()]


def test_text_stream_is_text_only(client):
    evs = _events(client.post("/api/stream/text", json={"text": "Bonjour", "session": "t"}))
    sentences = [e for e in evs if e["type"] == "sentence"]
    assert [s["text"] for s in sentences] == ["Très bien.", "Voulez-vous un croissant aussi ?"]
    assert all("audio_b64" not in s and s["ipa"] for s in sentences)
    assert evs[-1]["type"] == "done" and evs[-1]["mode"] == "text"


def test_voice_stream_returns_audio(client):
    evs = _events(client.post("/api/stream/voice", files={"audio": ("a.webm", b"x" * 2000)}, data={"session": "v"}))
    assert evs[0]["type"] == "transcript" and evs[0]["lang"] == "fr"
    assert all("audio_b64" in e for e in evs if e["type"] == "sentence")
    assert evs[-1]["mode"] == "voice"


def test_history_persisted_and_reset(client):
    client.post("/api/stream/text", json={"text": "Salut", "session": "h"})
    assert len(client.get("/api/history", params={"session": "h"}).json()) == 2
    client.post("/api/reset", params={"session": "h"})
    assert client.get("/api/history", params={"session": "h"}).json() == []


def test_practice_records_progress(client):
    r = client.post("/api/practice", files={"audio": ("a.webm", b"x" * 2000)},
                    data={"target": "Bonjour, je voudrais un thé.", "lang_code": "fr"}).json()
    assert r["weak_words"] == ["thé"] and r["target_ipa"]
    assert client.get("/api/progress").json()["attempts"] == 1


def test_non_streaming_text(client):
    r = client.post("/api/text", json={"text": "Bonjour", "session": "n"}).json()
    assert r["reply"].startswith("Très bien") and r["ipa"] and "audio_b64" not in r


def test_bad_language_rejected(client):
    assert client.post("/api/text", json={"text": "hi", "lang": "xx"}).status_code == 400
