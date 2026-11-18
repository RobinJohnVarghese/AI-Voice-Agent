# Offline Voice Tutor — local, multilingual chatbot for 8 GB RAM

Text in → text out. Voice in → voice out. Every reply carries an **IPA phonetic transcription**,
the narrator **pauses and inflects according to punctuation**, and a **practice mode** scores your
pronunciation word by word. After a one-time model download, nothing leaves your machine.

---

## 1. Architecture

```
┌──────────────────────────── Browser UI (web/index.html · app.js · style.css) ────────────────────────────┐
│ text box · tap/hold-to-talk mic (auto-stop on silence) · language picker · IPA/readable/romanized toggles │
│ chat (streams text, queues sentence audio) · practice panel (record, replay, phoneme diff) · progress tab │
└──────┬─────────────────────────────┬───────────────────────────────┬─────────────────────┬────────────────┘
 POST /api/stream/text      POST /api/stream/voice (webm)       POST /api/practice     GET /api/progress
 (NDJSON events)            (NDJSON events)                                             GET /api/history
┌──────▼─────────────────────────────▼───────────────────────────────▼─────────────────────▼────────────────┐
│ FastAPI (app/server.py) → Pipeline (app/pipeline.py)                         SQLite (app/store.py)        │
│                                                                              messages · attempts ·        │
│  TEXT MODE                    VOICE MODE                     PRACTICE MODE   word_scores                  │
│  langid ──┐                   faster-whisper small int8      Whisper (lang forced)                        │
│           │                   → transcript event             → IPA(target) vs IPA(heard)                  │
│           ▼                           │                      → phoneme alignment + diff                   │
│  Ollama qwen2.5:3b, token stream ◄────┘                      → articulation tips, 0–100 per word          │
│           │ delta events (text appears live)                                                              │
│           ▼ sentence splitter                                                                             │
│  per sentence: lang.spans (quoted phrases in other languages)                                             │
│     → phonetics: IPA (espeak-ng) · pinyin · romaji · readable respelling                                  │
│     → voice mode only: prosody.segment → Piper narrator (espeak-ng fallback) → WAV                        │
│  → sentence event {text, ipa, readable, romanized, audio_b64?} … → done event                             │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Voice replies start playing after the **first sentence** is ready (about 3 s after the transcript on a
2-core CPU) instead of waiting for the whole answer.

| Layer | Component | Why this choice | RAM (approx.) |
|---|---|---|---|
| LLM | Ollama + `qwen2.5:3b` (Q4_K_M GGUF), streaming | Strong multilingual for its size, fast on CPU | ~2.0 GB |
| Speech-to-text | `faster-whisper` `small`, int8 | 99 languages, auto language ID, word confidence | ~0.6–1.0 GB |
| Text-to-speech | Piper (ONNX neural voices) | Natural, real-time on CPU, ~40 languages | ~100 MB per loaded voice (max 2 loaded) |
| TTS fallback | espeak-ng | 100+ languages when no Piper voice is installed | negligible |
| Phonetics | phonemizer + espeak-ng → IPA; `pypinyin`; `pykakasi` | IPA for most languages, pinyin for Chinese, romaji for Japanese | negligible |
| Language ID (text) | langid | Tiny, offline | ~30 MB |
| Storage | SQLite (`data/tutor.db`) | Chat history, practice scores, weak words | negligible |
| API / UI | FastAPI + plain HTML/JS | No build step; mic via MediaRecorder | ~100 MB |

Measured on an 8 GB, 2-core, CPU-only machine during a streamed voice turn: LLM 2.1 GB + Python app 1.4 GB;
**peak system usage 4.3 GB** including the desktop and browser.

### Project layout

```
offline-voice-tutor/
├── app/
│   ├── config.py         # settings from .env / environment variables
│   ├── lang.py           # language detection, voice mapping, quoted mixed-language spans
│   ├── stt.py            # faster-whisper wrapper
│   ├── llm.py            # Ollama streaming chat client + tutor system prompt
│   ├── phonetics.py      # IPA, pinyin, romaji, readable respelling
│   ├── prosody.py        # punctuation → speakable segments + pause lengths
│   ├── tts.py            # Piper narrator, espeak-ng fallback, voice switching, LRU cache
│   ├── pronunciation.py  # phoneme alignment, per-word scores, articulation tips
│   ├── store.py          # SQLite history + practice progress
│   ├── pipeline.py       # streaming text / voice / practice flows
│   └── server.py         # REST + NDJSON streaming API, static UI
├── web/                  # index.html, app.js, style.css
├── tests/                # pytest suite (no models needed)
├── setup.sh · setup.ps1  # one-command install (Linux/macOS · Windows)
├── run.sh · run.ps1      # start Ollama (if needed) + the app
├── Dockerfile · docker-compose.yml
├── .env.example
├── download_models.py    # one-time downloads
└── requirements.txt
```

---

## 2. Step-by-step setup

### Quick start (one command)
* **Linux/macOS:** `./setup.sh` then `./run.sh`
* **Windows (PowerShell):** `powershell -ExecutionPolicy Bypass -File setup.ps1` then `.\run.ps1`
* **Docker:** `docker compose run --rm models` (one-time download), then `docker compose up -d app`

Then open http://127.0.0.1:8000. Settings live in `.env` (copied from `.env.example`).
The manual steps below do the same thing.

### Step 1 — System prerequisites
* Python 3.10–3.12, ~6 GB free disk.
* **espeak-ng** (phonetics + fallback voice):
  * Ubuntu/Debian: `sudo apt install espeak-ng ffmpeg`
  * macOS: `brew install espeak-ng ffmpeg`
  * Windows: install the `.msi` from https://github.com/espeak-ng/espeak-ng/releases, then set
    `PHONEMIZER_ESPEAK_LIBRARY=C:\Program Files\eSpeak NG\libespeak-ng.dll`
* **Ollama** (LLM runtime): Linux `curl -fsSL https://ollama.com/install.sh | sh`;
  macOS/Windows: installer from https://ollama.com/download

### Step 2 — Python environment
```bash
cd offline-voice-tutor
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3 — Download models (only step that needs internet)
```bash
ollama serve &                     # skip if the Ollama app is already running
python download_models.py          # Whisper small, Piper voices (en/es/fr/de/hi), qwen2.5:3b
# add more voices, e.g.:
python download_models.py it_IT-paola-medium pt_BR-faber-medium ru_RU-irina-medium
```
Piper voice files go in `models/piper/`; the first two letters of the filename are the language code
(`it_IT-…` → `it`). Languages without a Piper voice automatically use espeak-ng.

### Step 4 — Run
```bash
cp .env.example .env               # optional: change models / limits
uvicorn app.server:app --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000 (microphone access works on `localhost`/`127.0.0.1` without HTTPS).

### Step 5 — Use it
* **Type** a message → the reply streams in as text, each sentence with IPA, readable respelling
  (e.g. `gud MAWR-ning`) and pinyin/romaji where relevant. Tick *Speak text replies* or press
  **Listen** on any reply to hear it.
* **Tap "Talk"** and speak — recording stops when you go quiet (or **hold** and release). Your
  transcript appears (unclear words flagged), and the spoken reply starts after the first sentence.
* **Practise** on any reply (or type a phrase in the Practice panel) → "Hear it" / "Slow" →
  "Record" → overall score, a chip per word; click a word to see target vs heard sounds with the
  differences highlighted and a tip on how to make the sound. Replay your recording next to the
  reference.
* **Progress tab:** average score, recent attempts and the words you most need to review.
* Pick a language in the header to force it; *Auto-detect* works for most input longer than a few words.
* Quoted phrases in another language ("In Spanish it's \"Buenos días\"") get that language's
  phonetics and narrator voice.

---

## 3. How each requirement is met

**Text → text, voice → voice.** `/api/stream/text` returns only text (audio only if you opt in);
`/api/stream/voice` runs STT → LLM → TTS and streams audio sentence by sentence (plus the
transcript/reply text for reading along).

**Any language.** Whisper detects the spoken language; langid detects typed language; the LLM is
told to answer in that language; phonetics and voice are chosen per language.

**Phonetic response.** Every reply is converted to IPA with stress marks, e.g.
`¡Hola! ¿Qué tal?` → `¡ˈola! ¿kˈe tˈal?`, plus a readable respelling generated from the IPA
(`OH-lah keh tahl`). Chinese also gets tone-marked pinyin (`nǐ hǎo`) and Japanese gets Hepburn
romaji (`konnichiwa`; espeak-ng IPA is unreliable for Japanese so it is hidden).

**Punctuation-aware narration** (`app/prosody.py`). Text is split at punctuation; the mark stays
attached so the voice gets the right intonation (rising for `?`), and a pause is inserted:

| Mark | Pause |
|---|---|
| `,` `、` `،` | 0.22 s |
| `;` `:` `—` | 0.30–0.35 s |
| `.` `!` `।` `。` | 0.55 s |
| `?` `؟` `？` | 0.60 s |
| `…` / `...` | 0.80 s |
| new line | 0.70 s |

Markdown, emojis and list bullets are stripped before speaking; *Slow narration* stretches both
speech (Piper `length_scale=1.35`) and pauses (×1.3).

**Pronunciation improvement.** Practice mode transcribes your attempt with the language forced,
converts target and heard words to IPA, aligns them phoneme by phoneme, and scores each word by
phonetic similarity and Whisper's acoustic confidence. Substitutions such as `θ → s` produce
specific tips ("th: put the tongue tip between the teeth…"). Scores are saved so weak words can be
reviewed later. In normal voice chat, low-confidence words are listed as "unclear", and the
tutor corrects grammar ("Correction: Me gusta la música.").

---

## 4. API reference

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/health` | – | models, installed neural voices, languages, LLM status |
| POST | `/api/stream/text` | JSON `{text, session?, lang?, speak?, slow?}` | NDJSON: `delta`…, `sentence`…, `done` |
| POST | `/api/stream/voice` | multipart `audio`, `session?`, `lang_code?`, `slow?` | NDJSON: `transcript`, `delta`…, `sentence` (with `audio_b64`)…, `done` |
| POST | `/api/text` | JSON `{text, session?, lang?}` | `{reply, ipa, readable, romanized, lang}` |
| POST | `/api/voice` | multipart `audio`, `session?`, `lang_code?`, `slow?` | `{transcript, unclear_words, reply, ipa, audio_b64}` |
| POST | `/api/practice` | multipart `audio`, `target`, `lang_code?` | `{overall, words[{word, ipa, heard_ipa, score, diff}], tips, weak_words}` |
| POST | `/api/speak` | JSON `{text, lang?, slow?}` | `audio/wav` |
| POST | `/api/annotate` | JSON `{text, lang?}` | `{ipa, readable, romanized}` |
| GET | `/api/history?session=` | – | saved messages |
| POST | `/api/reset?session=` | – | clears chat memory |
| GET | `/api/progress` | – | average, recent attempts, weak words |

Each NDJSON line is one JSON event; errors arrive as `{"type": "error", "message": …}`.

Example: `curl -X POST localhost:8000/api/text -H 'Content-Type: application/json' -d '{"text":"Hola, yo gusta la música"}'`

---

## 5. Tuning for 8 GB RAM

| Setting (env var) | Default | Lower RAM / faster | Better quality (if RAM allows) |
|---|---|---|---|
| `LLM_MODEL` | `qwen2.5:3b` | `qwen2.5:1.5b`, `gemma2:2b` | `qwen2.5:7b` (~4.7 GB; close other apps), `llama3.1:8b` |
| `WHISPER_MODEL` | `small` | `base`, `tiny` | `medium` (~1.5 GB, slower) |
| `LLM_CTX` | 2048 | 1024 | 4096 |
| `MAX_LOADED_VOICES` | 2 | 1 | 4 |

Other tips: keep only one browser tab open; on Linux add 4 GB swap; Ollama unloads the LLM after
30 min idle (`keep_alive`). Typical latency on a 2-core CPU: first text appears in ~1–2 s; in voice mode the first sentence plays ~3 s after the transcript and a full 3-sentence reply finishes in ~13 s.
More cores or a GPU reduce this a lot.

---

## 6. Testing

```bash
pip install pytest
python -m pytest -q tests     # 25 tests; uses fake models, runs in ~2 s
```

---

## 7. Known limits and next steps
* A 3B model sometimes gives imperfect corrections or syllable breakdowns; switch to a 7B model for
  noticeably better tutoring if you can free ~5 GB.
* Readable respelling is generated by rules from IPA, so it is approximate (aimed at English readers).
* Scoring compares phonemes of what Whisper *heard*; a dedicated phoneme recogniser such as
  `wav2vec2-xlsr-53-espeak-cv-ft` (~1.2 GB) would catch accent-level errors Whisper auto-corrects.
* Mixed-language detection only applies to quoted phrases (≥ 4 characters).
* Desktop packaging: wrap the server + UI with PyInstaller or Tauri for a one-click app.
