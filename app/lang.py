"""Language detection and per-language engine mapping."""
import re

import langid

# iso code -> (display name, espeak-ng voice for phonemes / fallback TTS)
LANGS = {
    "en": ("English", "en-us"), "es": ("Spanish", "es"), "fr": ("French", "fr-fr"),
    "de": ("German", "de"), "it": ("Italian", "it"), "pt": ("Portuguese", "pt"),
    "nl": ("Dutch", "nl"), "ru": ("Russian", "ru"), "uk": ("Ukrainian", "uk"),
    "pl": ("Polish", "pl"), "tr": ("Turkish", "tr"), "ar": ("Arabic", "ar"),
    "hi": ("Hindi", "hi"), "bn": ("Bengali", "bn"), "ta": ("Tamil", "ta"),
    "te": ("Telugu", "te"), "kn": ("Kannada", "kn"), "ml": ("Malayalam", "ml"),
    "mr": ("Marathi", "mr"), "gu": ("Gujarati", "gu"), "pa": ("Punjabi", "pa"),
    "ur": ("Urdu", "ur"), "zh": ("Chinese (Mandarin)", "cmn"), "ja": ("Japanese", "ja"),
    "ko": ("Korean", "ko"), "vi": ("Vietnamese", "vi"), "id": ("Indonesian", "id"),
    "sw": ("Swahili", "sw"),
}

langid.set_languages(list(LANGS))


def detect(text: str, default: str = "en") -> str:
    text = text.strip()
    if len(text) < 3:
        return default
    code, _ = langid.classify(text)
    return code if code in LANGS else default


def name(code: str) -> str:
    return LANGS.get(code, (code, code))[0]


def espeak_voice(code: str) -> str:
    return LANGS.get(code, ("", "en-us"))[1]


_QUOTED = re.compile(r'"[^"]+"|“[^”]+”|„[^“”]+[“”]|«[^»]+»|「[^」]+」')


def spans(text: str, base: str) -> list[tuple[str, str]]:
    """Split text into (chunk, language) runs. Quoted phrases often switch language,
    e.g. 'Good morning in Spanish is "Buenos días".' -> [(..., "en"), ('"Buenos días"', "es"), ...]."""
    outside = _QUOTED.sub(" ", text)
    outer = detect(outside, default=base) if len(outside.strip()) >= 20 else base
    out: list[tuple[str, str]] = []
    pos = 0
    for m in _QUOTED.finditer(text):
        if text[pos:m.start()].strip():
            out.append((text[pos:m.start()], outer))
        inner = m.group()[1:-1].strip()
        out.append((m.group(), detect(inner, default=outer) if len(inner) >= 4 else outer))
        pos = m.end()
    if text[pos:].strip():
        out.append((text[pos:], outer))
    merged: list[tuple[str, str]] = []
    for chunk, code in out:
        if merged and (merged[-1][1] == code or not any(ch.isalnum() for ch in chunk)):
            merged[-1] = (merged[-1][0] + chunk, merged[-1][1])
        else:
            merged.append((chunk, code))
    return [(c.strip(), code) for c, code in merged] or [(text, base)]
