# Offline Voice Tutor — local, multilingual chatbot for 8 GB RAM

Text in → text out. Voice in → voice out. Every reply carries an **IPA phonetic transcription**,
the narrator **pauses and inflects according to punctuation**, and a **practice mode** scores your
pronunciation word by word. After a one-time model download, nothing leaves your machine.

---

## 1. Architecture

```
                         ┌──────────────────────── Browser UI (web/index.html) ────────────────────────┐
                         │  text box  ·  push-to-talk mic  ·  language picker  ·  practice panel        │
                         └───────┬───────────────────────┬──────────────────────────────┬───────────────┘
                     POST /api/text            POST /api/voice (webm)          POST /api/practice
                                 │                       │                              │
┌────────────────────────────────▼───────────────────────▼──────────────────────────────▼───────────────┐
│ FastAPI server (app/server.py)  →  Pipeline orchestrator (app/pipeline.py)                            │
│                                                                                                       │
│   TEXT MODE                         VOICE MODE                           PRACTICE MODE                │
│   ─────────                         ──────────                           ─────────────                │
│   lang.detect (langid)              STT: faster-whisper small int8       STT (language forced)         │
│        │                            → transcript + language + per-word   │                             │
│        ▼                              confidence                         ▼                             │
│   LLM: Ollama qwen2.5:3b (Q4)  ◄────────┘                                pronunciation.score:          │
│        │  (short, punctuated, corrects grammar, per-session memory)       IPA(target) vs IPA(heard)    │
│        ▼                                  │                               + Whisper word confidence    │
│   phonetics.to_ipa (espeak-ng)            ▼                               → 0–100 score per word       │
│        │                            phonetics.to_ipa                                                   │
│        ▼                                  ▼                                                            │
│   JSON {reply, ipa}               prosody.segment → TTS narrator                                       │
│                                   (Piper neural voice, espeak-ng fallback)                             │
│                                   → WAV (base64) + reply + ipa                                         │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Layer | Component | Why this choice | RAM (approx.) |
|---|---|---|---|
| LLM | Ollama + `qwen2.5:3b` (Q4_K_M GGUF) | Strong multilingual for its size, fast on CPU | ~2.0–2.5 GB |
| Speech-to-text | `faster-whisper` `small`, int8 | 99 languages, auto language ID, word confidence | ~0.6–1.0 GB |
| Text-to-speech | Piper (ONNX neural voices) | Natural, real-time on CPU, ~40 languages | ~100 MB per loaded voice (max 2 loaded) |
| TTS fallback | espeak-ng | 100+ languages when no Piper voice is installed | negligible |
| Phonetics | phonemizer + espeak-ng → IPA | Same engine for every language | negligible |
| Language ID (text) | langid | Tiny, offline | ~30 MB |
| API / UI | FastAPI + plain HTML/JS | No build step; mic via MediaRecorder | ~100 MB |

Total measured on an 8 GB machine during a voice turn: **~3.3 GB** (LLM 2.0 GB + Python app 1.2 GB),
leaving room for the OS and a browser.

### Project layout

```
offline-voice-tutor/
├── app/
│   ├── config.py         # model names, paths (override with env vars)
│   ├── lang.py           # language detection + per-language voice mapping
│   ├── stt.py            # faster-whisper wrapper
│   ├── llm.py            # Ollama chat client + tutor system prompt + session memory
│   ├── phonetics.py      # IPA via espeak-ng
│   ├── prosody.py        # punctuation → speakable segments + pause lengths
│   ├── tts.py            # Piper narrator, espeak-ng fallback, LRU voice cache
│   ├── pronunciation.py  # practice-mode scoring
│   ├── pipeline.py       # orchestrates text / voice / practice flows
│   └── server.py         # REST API + static UI
├── web/index.html        # chat UI
├── download_models.py    # one-time downloads
└── requirements.txt
```

---

## 2. Step-by-step setup

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
uvicorn app.server:app --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000 (microphone access works on `localhost`/`127.0.0.1` without HTTPS).

### Step 5 — Use it
* **Type** a message → text reply + IPA line.
* **Hold "Hold to talk"** and speak → your transcript (words Whisper was unsure of are flagged),
  then the spoken reply plays automatically, with text + IPA shown.
* **Practice panel**: type a phrase → "Hear it" (tick *Slow narration* for learners) → hold
  "Hold to record" and repeat → overall score, per-word scores, IPA of weak words on hover.
* Pick a language in the header to force it; *Auto-detect* works for most input longer than a few words.

---

## 3. How each requirement is met

**Text → text, voice → voice.** `/api/text` returns only text; `/api/voice` runs
STT → LLM → TTS and returns audio (plus the transcript/reply text for reading along).

**Any language.** Whisper detects the spoken language; langid detects typed language; the LLM is
told to answer in that language; phonetics and voice are chosen per language.

**Phonetic response.** Every reply is converted to IPA with stress marks, e.g.
`¡Hola! ¿Qué tal?` → `¡ˈola! ¿kˈe tˈal?`. The system prompt also asks for a simple syllable
breakdown (e.g. `bon-ZHOOR`) when you ask how to say something.

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
converts target and heard words to IPA, and scores each word by phonetic similarity and Whisper's
acoustic confidence. In normal voice chat, low-confidence words are listed as "unclear", and the
tutor corrects grammar ("Correction: Me gusta la música.").

---

## 4. API reference

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/health` | – | models, installed neural voices, languages |
| POST | `/api/text` | JSON `{text, session?, lang?}` | `{reply, ipa, lang, lang_name}` |
| POST | `/api/voice` | multipart `audio`, `session?`, `lang_code?`, `slow?` | `{transcript, unclear_words, reply, ipa, audio_b64}` |
| POST | `/api/practice` | multipart `audio`, `target`, `lang_code?` | `{overall, words[], heard, weak_words, target_ipa}` |
| POST | `/api/speak` | JSON `{text, lang?, slow?}` | `audio/wav` |
| POST | `/api/reset?session=` | – | clears chat memory |

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
30 min idle (`keep_alive`). Typical latency on a 2-core CPU: text turn 5–10 s, voice turn ~15 s.
More cores or a GPU reduce this a lot.

---

## 6. Known limits and next steps
* A 3B model sometimes gives imperfect corrections or syllable breakdowns; switch to a 7B model for
  noticeably better tutoring if you can free ~5 GB.
* espeak-ng IPA is weaker for Mandarin/Japanese tones and pitch accent; consider `pypinyin` /
  `pykakasi` for those.
* Phoneme-level scoring (rather than word-level) would need a phoneme recogniser such as
  `wav2vec2-xlsr-53-espeak-cv-ft` (~1.2 GB) — a good upgrade once the basics work.
* Streaming: stream LLM tokens and synthesize sentence-by-sentence to start speaking sooner.
* Desktop packaging: wrap the server + UI with PyInstaller or Tauri for a one-click app.
