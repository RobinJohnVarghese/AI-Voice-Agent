"""FastAPI server: REST API + static web UI. Run: uvicorn app.server:app --port 8000"""
import os
import tempfile

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, lang
from .pipeline import Pipeline

app = FastAPI(title="Offline Voice Tutor")
pipe = Pipeline()


class TextIn(BaseModel):
    text: str
    session: str = "default"
    lang: str | None = None


class SpeakIn(BaseModel):
    text: str
    lang: str | None = None
    slow: bool = False


async def _save(upload: UploadFile) -> str:
    suffix = os.path.splitext(upload.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(await upload.read())
        return f.name


@app.get("/api/health")
def health():
    return {"ok": True, "llm": config.LLM_MODEL, "whisper": config.WHISPER_MODEL,
            "neural_voices": sorted(pipe.tts.available), "languages": lang.LANGS}


@app.post("/api/text")
async def text_turn(body: TextIn):
    return await run_in_threadpool(pipe.text_turn, body.session, body.text, body.lang or None)


@app.post("/api/voice")
async def voice_turn(audio: UploadFile = File(...), session: str = Form("default"),
                     lang_code: str = Form(""), slow: bool = Form(False)):
    path = await _save(audio)
    try:
        return await run_in_threadpool(pipe.voice_turn, session, path, lang_code or None, slow)
    finally:
        os.unlink(path)


@app.post("/api/practice")
async def practice(audio: UploadFile = File(...), target: str = Form(...), lang_code: str = Form("")):
    path = await _save(audio)
    try:
        return await run_in_threadpool(pipe.practice, target, path, lang_code or None)
    finally:
        os.unlink(path)


@app.post("/api/speak")
async def speak(body: SpeakIn):
    wav = await run_in_threadpool(pipe.speak, body.text, body.lang or None, body.slow)
    return Response(wav, media_type="audio/wav")


@app.post("/api/reset")
def reset(session: str = "default"):
    pipe.llm.reset(session)
    return {"ok": True}


app.mount("/static", StaticFiles(directory=config.ROOT / "web"), name="static")


@app.get("/")
def index():
    return FileResponse(config.ROOT / "web" / "index.html")
