"""FastAPI server: REST + streaming API and static web UI.

Run: uvicorn app.server:app --host 127.0.0.1 --port 8000
"""
import json
import os
import tempfile
from functools import lru_cache

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, lang, phonetics
from .pipeline import Pipeline, split_sentences

app = FastAPI(title="Offline Voice Tutor", version="2.0")


@lru_cache(maxsize=1)
def get_pipe() -> Pipeline:
    return Pipeline()


class TextIn(BaseModel):
    text: str
    session: str = "default"
    lang: str | None = None
    speak: bool = False
    slow: bool = False


class SpeakIn(BaseModel):
    text: str
    lang: str | None = None
    slow: bool = False


async def _save(upload: UploadFile) -> str:
    data = await upload.read()
    if not data:
        raise HTTPException(400, "Empty audio upload.")
    suffix = os.path.splitext(upload.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(data)
        return f.name


def _ndjson(events, cleanup: str | None = None):
    def gen():
        try:
            for ev in events:
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        except Exception as e:  # surface failures to the client instead of a broken stream
            yield json.dumps({"type": "error", "message": f"{type(e).__name__}: {e}"}) + "\n"
        finally:
            if cleanup:
                os.unlink(cleanup)
    return StreamingResponse(gen(), media_type="application/x-ndjson")


def _lang(code: str | None) -> str | None:
    if code and code not in lang.LANGS:
        raise HTTPException(400, f"Unsupported language '{code}'.")
    return code or None


@app.get("/api/health")
def health(pipe: Pipeline = Depends(get_pipe)):
    return {"ok": True, "llm": config.LLM_MODEL, "llm_ready": pipe.llm.ping(),
            "whisper": config.WHISPER_MODEL, "neural_voices": sorted(pipe.tts.available),
            "languages": lang.LANGS}


@app.post("/api/stream/text")
def stream_text(body: TextIn, pipe: Pipeline = Depends(get_pipe)):
    return _ndjson(pipe.stream(body.session, text=body.text, force_lang=_lang(body.lang),
                               speak=body.speak, slow=body.slow))


@app.post("/api/stream/voice")
async def stream_voice(audio: UploadFile = File(...), session: str = Form("default"),
                       lang_code: str = Form(""), slow: bool = Form(False), pipe: Pipeline = Depends(get_pipe)):
    path = await _save(audio)
    return _ndjson(pipe.stream(session, audio_path=path, force_lang=_lang(lang_code), speak=True, slow=slow),
                   cleanup=path)


@app.post("/api/text")
async def text_turn(body: TextIn, pipe: Pipeline = Depends(get_pipe)):
    return await run_in_threadpool(pipe.turn, body.session, body.text, None, _lang(body.lang))


@app.post("/api/voice")
async def voice_turn(audio: UploadFile = File(...), session: str = Form("default"),
                     lang_code: str = Form(""), slow: bool = Form(False), pipe: Pipeline = Depends(get_pipe)):
    path = await _save(audio)
    try:
        return await run_in_threadpool(pipe.turn, session, None, path, _lang(lang_code), slow)
    finally:
        os.unlink(path)


@app.post("/api/practice")
async def practice(audio: UploadFile = File(...), target: str = Form(...), lang_code: str = Form(""),
                   pipe: Pipeline = Depends(get_pipe)):
    if not target.strip():
        raise HTTPException(400, "Target phrase is empty.")
    path = await _save(audio)
    try:
        return await run_in_threadpool(pipe.practice, target, path, _lang(lang_code))
    finally:
        os.unlink(path)


@app.post("/api/speak")
async def speak(body: SpeakIn, pipe: Pipeline = Depends(get_pipe)):
    wav = await run_in_threadpool(pipe.speak, body.text, _lang(body.lang), body.slow)
    return Response(wav, media_type="audio/wav")


@app.post("/api/annotate")
def annotate(body: SpeakIn):
    from . import phonetics
    code = _lang(body.lang) or lang.detect(body.text)
    return {"lang": code, **phonetics.annotate(body.text, code)}


@app.get("/api/history")
def history(session: str = "default", pipe: Pipeline = Depends(get_pipe)):
    msgs = pipe.store.history(session, limit=200)
    for m in msgs:
        m["lang_name"] = lang.name(m["lang"])
        if m["role"] == "assistant":
            m["sentences"] = [{"text": t, **phonetics.annotate(t, m["lang"], mixed=True)}
                              for t in split_sentences(m["content"])]
    return msgs


@app.post("/api/reset")
def reset(session: str = "default", pipe: Pipeline = Depends(get_pipe)):
    pipe.store.clear(session)
    return {"ok": True}


@app.get("/api/progress")
def progress(pipe: Pipeline = Depends(get_pipe)):
    return pipe.store.progress()


app.mount("/static", StaticFiles(directory=config.ROOT / "web"), name="static")


@app.get("/")
def index():
    return FileResponse(config.ROOT / "web" / "index.html")
