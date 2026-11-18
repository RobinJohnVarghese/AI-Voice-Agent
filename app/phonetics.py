"""Phonetic helpers, all offline.

* ``to_ipa``      – IPA with stress marks via espeak-ng (100+ languages)
* ``romanize``    – pinyin (Chinese) / Hepburn romaji (Japanese)
* ``respell``     – learner-friendly respelling from IPA, stressed syllable in CAPS ("bon-ZHOOR")
* ``annotate``    – all of the above for one piece of text
"""
import re
import unicodedata
from functools import lru_cache

from phonemizer.backend import EspeakBackend
from phonemizer.separator import Separator

from . import lang

_WORD_SEP = Separator(phone="", syllable="", word=" ")
NO_RESPELL = {"zh", "ja", "ko"}  # romanization is more useful there
NO_IPA = {"ja"}  # espeak-ng cannot read kanji/kana; romaji is shown instead
_CJK_PUNCT = str.maketrans({"，": ",", "。": ".", "？": "?", "！": "!", "、": ",", "：": ":", "；": ";"})


@lru_cache(maxsize=8)
def _backend(code: str) -> EspeakBackend:
    return EspeakBackend(lang.espeak_voice(code), preserve_punctuation=True,
                         with_stress=True, language_switch="remove-flags")


def _clean(ipa: str) -> str:
    return re.sub(r"-(?=\s|$)", "", ipa).strip()


def to_ipa(text: str, code: str) -> str:
    if not text.strip() or code in NO_IPA:
        return ""
    try:
        return _clean(_backend(code).phonemize([text], separator=_WORD_SEP, strip=True)[0])
    except Exception as e:  # language missing from this espeak build
        return f"(IPA unavailable: {e})"


def _strip_punct(w: str) -> str:
    is_p = lambda c: unicodedata.category(c)[0] in "PSZ" and c != "'"
    i, j = 0, len(w)
    while i < j and is_p(w[i]):
        i += 1
    while j > i and is_p(w[j - 1]):
        j -= 1
    return w[i:j]


def words_ipa(text: str, code: str) -> list[tuple[str, str]]:
    words = [w for w in text.split() if any(c.isalnum() for c in w)]
    if not words:
        return []
    bare = [_strip_punct(w) or w for w in words]
    ipa = _backend(code).phonemize(bare, separator=_WORD_SEP, strip=True)
    return list(zip(bare, (_clean(i) for i in ipa)))


# ---------------------------------------------------------------- romanization
def romanize(text: str, code: str) -> str | None:
    if code == "zh":
        from pypinyin import Style, pinyin
        return _tidy(" ".join(p[0] for p in pinyin(text, style=Style.TONE)))
    if code == "ja":
        return _tidy(" ".join(_hepburn(x) for x in _kakasi().convert(text) if x["hepburn"].strip()))
    return None


def _tidy(s: str) -> str:
    return re.sub(r"\s+([,.?!:;])", r"\1", s.translate(_CJK_PUNCT))


def _hepburn(tok: dict) -> str:
    """pykakasi reads particles literally; は/へ as particles are pronounced wa/e."""
    orig, rom = tok["orig"], tok["hepburn"]
    if orig in ("は", "へ"):
        return "wa" if orig == "は" else "e"
    if orig.endswith(("にちは", "ばんは")) and rom.endswith("ha"):
        return rom[:-2] + "wa"
    return rom


@lru_cache(maxsize=1)
def _kakasi():
    import pykakasi
    return pykakasi.kakasi()


# ---------------------------------------------------------------- respelling
_VOWELS = {
    "aɪ": "eye", "aʊ": "ow", "eɪ": "ay", "oʊ": "oh", "əʊ": "oh", "ɔɪ": "oy", "ɪə": "eer", "eə": "air",
    "ʊə": "oor", "iː": "ee", "uː": "oo", "ɑː": "ah", "ɔː": "aw", "ɜː": "er", "aː": "aa", "eː": "ay",
    "oː": "oh", "ɛː": "eh", "yː": "ü", "øː": "ö",
    "a": "ah", "e": "eh", "i": "ee", "o": "oh", "u": "oo", "ɪ": "i", "ʊ": "u", "ə": "uh", "ɐ": "uh",
    "ʌ": "uh", "ɛ": "eh", "æ": "a", "ɑ": "ah", "ɒ": "o", "ɔ": "aw", "ɚ": "er", "ɝ": "er", "ᵻ": "i",
    "y": "ü", "ø": "ö", "œ": "ö", "ɨ": "i", "ɯ": "u", "ɤ": "uh", "ʏ": "ü", "ɵ": "uh",
}
_CONS = {
    "tʃ": "ch", "dʒ": "j", "ts": "ts", "dz": "dz",
    "ɡ": "g", "j": "y", "ʃ": "sh", "ʒ": "zh", "θ": "th", "ð": "th", "ŋ": "ng", "ɹ": "r", "r": "r",
    "ɾ": "r", "ʁ": "r", "ʀ": "r", "ɲ": "ny", "ʎ": "ly", "x": "kh", "χ": "kh", "β": "v", "ɣ": "g",
    "ʔ": "", "ç": "h", "ɕ": "sh", "ʑ": "zh", "ʂ": "sh", "ʐ": "zh", "ʈ": "t", "ɖ": "d", "ɳ": "n",
    "ɽ": "r", "ɭ": "l", "ʲ": "", "ʷ": "w", "ˠ": "", "ʋ": "v", "ɦ": "h", "ɫ": "l", "ʰ": "h", "c": "ky", "ɟ": "gy", "q": "k",
    "ħ": "h", "ʕ": "", "ɬ": "hl", "ɱ": "m", "ʍ": "wh", "ɥ": "w",
}
_KEYS = sorted({**_VOWELS, **_CONS}, key=len, reverse=True)
_NASAL = "\u0303"


def _tokens(ipa: str) -> list[tuple[str, bool, bool]]:
    """-> [(spelling, is_vowel, stressed)]"""
    ipa = unicodedata.normalize("NFD", ipa).replace("c\u0327", "ç")
    out, stress, i = [], False, 0
    while i < len(ipa):
        ch = ipa[i]
        if ch == "ˈ":
            stress, i = True, i + 1
            continue
        if ch == "ˌ":
            i += 1
            continue
        key = next((k for k in _KEYS if ipa.startswith(k, i)), None)
        if key is None:
            if ch.isalpha() and unicodedata.category(ch) != "Mn":
                out.append((ch, False, stress))
                stress = False
            i += 1
            continue
        i += len(key)
        is_v = key in _VOWELS
        spell = _VOWELS[key] if is_v else _CONS[key]
        if is_v and ipa.startswith(_NASAL, i):
            spell, i = spell.rstrip("h") + "n", i + 1
        out.append((spell, is_v, stress))
        stress = False
    return out


def respell_word(ipa: str) -> str:
    toks = _tokens(ipa)
    vowels = [i for i, t in enumerate(toks) if t[1]]
    if not vowels:
        return "".join(t[0] for t in toks)
    # syllable boundaries: one consonant between vowels -> onset of next; more -> split after first
    starts = [0]
    for a, b in zip(vowels, vowels[1:]):
        gap = b - a - 1
        starts.append(b if gap == 0 else (b - 1 if gap == 1 else a + 2))
    sylls = [toks[s:e] for s, e in zip(starts, starts[1:] + [len(toks)])]
    parts = []
    for syl in sylls:
        text = "".join(t[0] for t in syl)
        parts.append(text.upper() if any(t[2] for t in syl) and len(sylls) > 1 else text)
    return "-".join(p for p in parts if p)


def respell(text: str, code: str) -> str | None:
    if code in NO_RESPELL:
        return None
    try:
        return " ".join(respell_word(ipa) for _, ipa in words_ipa(text, code))
    except Exception:
        return None


def annotate(text: str, code: str, mixed: bool = False) -> dict:
    """Phonetics for text in ``code``; with ``mixed`` quoted phrases use their own language."""
    runs = lang.spans(text, code) if mixed else [(text, code)]
    parts = [(t, {"ipa": to_ipa(t, c), "romanized": romanize(t, c), "readable": respell(t, c)}) for t, c in runs]

    def join(key, fallback):
        vals = [p[key] or (t if fallback else "") for t, p in parts]
        return " ".join(v for v in vals if v) if any(p[key] for _, p in parts) else None

    return {"ipa": join("ipa", False) or "", "romanized": join("romanized", True), "readable": join("readable", True)}
