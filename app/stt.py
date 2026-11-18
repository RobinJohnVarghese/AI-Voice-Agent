"""Speech-to-text with faster-whisper (CTranslate2, int8 on CPU, ~99 languages)."""
from dataclasses import dataclass, field

from faster_whisper import WhisperModel

from . import config


@dataclass
class Transcript:
    text: str
    lang: str
    lang_prob: float
    words: list[dict] = field(default_factory=list)  # {word, prob}


class STT:
    def __init__(self):
        self.model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8",
                                  download_root=str(config.WHISPER_DIR), cpu_threads=0)

    def transcribe(self, audio_path: str, language: str | None = None) -> Transcript:
        segments, info = self.model.transcribe(
            audio_path, language=language, beam_size=1, vad_filter=True, word_timestamps=True)
        words, texts = [], []
        for seg in segments:
            texts.append(seg.text.strip())
            for w in seg.words or []:
                words.append({"word": w.word.strip(), "prob": round(float(w.probability), 3)})
        return Transcript(" ".join(texts).strip(), info.language, round(float(info.language_probability), 3), words)
