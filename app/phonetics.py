"""IPA phonetic transcription via espeak-ng (100+ languages, fully offline)."""
import re
from functools import lru_cache

from phonemizer.backend import EspeakBackend
from phonemizer.separator import Separator

from . import lang

_WORD_SEP = Separator(phone="", syllable="", word=" ")


@lru_cache(maxsize=8)
def _backend(code: str) -> EspeakBackend:
    return EspeakBackend(lang.espeak_voice(code), preserve_punctuation=True,
                         with_stress=True, language_switch="remove-flags")


def to_ipa(text: str, code: str) -> str:
    if not text.strip():
        return ""
    try:
        ipa = _backend(code).phonemize([text], separator=_WORD_SEP, strip=True)[0]
        return re.sub(r"-(?=\s|$)", "", ipa)
    except Exception as e:  # unsupported language in espeak build
        return f"(IPA unavailable: {e})"


def words_ipa(text: str, code: str) -> list[tuple[str, str]]:
    words = [w for w in text.split() if any(c.isalnum() for c in w)]
    if not words:
        return []
    ipa = _backend(code).phonemize(words, separator=_WORD_SEP, strip=True)
    return list(zip(words, ipa))
