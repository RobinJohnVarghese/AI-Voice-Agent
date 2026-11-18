"""Language detection and per-language engine mapping."""
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
