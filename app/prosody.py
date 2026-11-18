"""Punctuation-aware text shaping for natural narration.

Splits text into speakable segments and assigns a pause after each one based on
its trailing punctuation. The punctuation mark stays attached to the segment so
the TTS model still produces the right intonation (e.g. rising pitch for '?').
"""
import re
from dataclasses import dataclass

PAUSES = {  # seconds of silence after a segment ending with this mark
    ",": 0.22, "、": 0.22, "،": 0.22, "，": 0.22,
    ";": 0.35, ":": 0.35, "；": 0.35, "：": 0.35,
    "—": 0.30, "–": 0.30, "-": 0.30,
    ".": 0.55, "!": 0.55, "?": 0.60, "。": 0.55, "！": 0.55, "？": 0.60,
    "।": 0.55, "॥": 0.70, "؟": 0.60,
    "…": 0.80, "...": 0.80,
    "\n": 0.70,
}
_SPLIT = re.compile(r"(\.\.\.|…|[.!?。！？।॥؟]+|[,;:、،，；：]|\s[—–-]\s|\n+)")
_MARKDOWN = re.compile(r"[*_#`>\[\]{}|~^\"“”„«»「」]")
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002700-\U000027BF]")


@dataclass
class Segment:
    text: str
    pause: float


def clean_for_speech(text: str) -> str:
    text = _MARKDOWN.sub("", text)
    text = _EMOJI.sub("", text)
    text = re.sub(r"^\s*(\d+[.)]|[-•])\s+", "", text, flags=re.M)  # list bullets
    text = text.replace("&", " and ").replace("%", " percent")
    return re.sub(r"[ \t]+", " ", text).strip()


def segment(text: str) -> list[Segment]:
    parts = _SPLIT.split(clean_for_speech(text))
    segs: list[Segment] = []
    for i in range(0, len(parts), 2):
        chunk = parts[i].strip()
        raw = parts[i + 1] if i + 1 < len(parts) else ""
        mark = raw.strip()
        if not mark and "\n" in raw:
            key, suffix = "\n", "."
        elif mark in ("...", "…"):
            key, suffix = mark, mark
        elif mark in ("—", "–", "-"):
            key, suffix = mark, ","
        else:
            key, suffix = mark[-1:], mark
        pause = PAUSES.get(key, 0.0)
        if chunk:
            segs.append(Segment(chunk + suffix, pause))
        elif segs:
            segs[-1].pause = max(segs[-1].pause, pause)
    return segs
