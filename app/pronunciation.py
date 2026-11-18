"""Pronunciation coaching.

1. Align target words with heard words (dynamic programming on phonetic distance).
2. Score each word from IPA similarity, weighted by Whisper's acoustic confidence.
3. Diff the phonemes of each mismatched word and attach articulation tips.
"""
import re
import unicodedata
from difflib import SequenceMatcher

from . import phonetics

TIPS = {
    "θ": "θ (think): put the tongue tip lightly between the teeth and blow air, no voice.",
    "ð": "ð (this): tongue between the teeth like θ, but voice it.",
    "ɹ": "English r: curl the tongue back without touching the roof of the mouth; lips slightly round.",
    "ʁ": "French/German r: gargle softly at the back of the throat.",
    "r": "Trilled r: let the tongue tip flutter against the ridge behind the upper teeth.",
    "ɾ": "Tapped r: one quick tap of the tongue tip behind the upper teeth (like 'tt' in American 'butter').",
    "y": "y/ü: say 'ee' while rounding the lips as for 'oo'.",
    "ø": "ø/ö: say 'eh' while rounding the lips.",
    "œ": "œ: open 'eh' with rounded lips.",
    "ʃ": "ʃ (sh): lips pushed forward, tongue a little further back than for s.",
    "ʒ": "ʒ (measure): like sh but voiced.",
    "x": "x (loch, jota): air through a narrow gap between the back of the tongue and the soft palate.",
    "ç": "ç (German ich): whisper a strong 'h' with the tongue in the 'ee' position.",
    "ŋ": "ŋ (sing): back of the tongue against the soft palate; don't add a hard g.",
    "æ": "æ (cat): open the jaw wide and spread the lips, between 'a' and 'e'.",
    "ɪ": "ɪ (sit): short and relaxed, not as tense as 'ee'.",
    "i": "i (see): spread the lips, tongue high and forward, keep it pure.",
    "v": "v: upper teeth on the lower lip, with voice (not w or b).",
    "w": "w: round the lips, no teeth contact.",
    "h": "h: a breathy push of air before the vowel.",
    "ɲ": "ɲ (ñ): middle of the tongue against the palate, like 'ny' in canyon.",
    "ʎ": "ʎ: middle of the tongue against the palate, like 'lli' in million.",
    "\u0303": "Nasal vowel: let air flow through the nose as well; don't pronounce a full n.",
    "ə": "ə (schwa): a short, relaxed 'uh'; unstressed syllables are often reduced to this.",
    "ʈ": "Retroflex t: curl the tongue tip back to touch the roof of the mouth.",
    "ɖ": "Retroflex d: curl the tongue tip back, with voice.",
    "ʰ": "Aspiration: release a small puff of air after the consonant.",
}
_STRIP = re.compile(r"[ˈˌ.,!?¡¿:;\"'()-]")


def _norm(w: str) -> str:
    return re.sub(r"[^\w']", "", w.lower())


def _phones(ipa: str) -> list[str]:
    """Split IPA into phones, keeping length/nasal/aspiration marks with their base symbol."""
    out: list[str] = []
    for ch in unicodedata.normalize("NFD", _STRIP.sub("", ipa)):
        if out and (unicodedata.category(ch) == "Mn" or ch in "ːʰʲʷ"):
            out[-1] += ch
        elif not ch.isspace():
            out.append(ch)
    return out


def similarity(a: str, b: str) -> float:
    pa, pb = _phones(a), _phones(b)
    if not pa and not pb:
        return 1.0
    return SequenceMatcher(None, pa, pb, autojunk=False).ratio()


def align(target: list[tuple[str, str]], heard: list[tuple[str, str]]):
    """Needleman-Wunsch alignment -> list of (target_idx | None, heard_idx | None, sim)."""
    n, m, skip_t, skip_h = len(target), len(heard), 1.0, 0.4
    cost = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        cost[i][0] = i * skip_t
    for j in range(1, m + 1):
        cost[0][j] = j * skip_h
    sims = [[1.0 if _norm(t[0]) == _norm(h[0]) else similarity(t[1], h[1]) for h in heard] for t in target]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost[i][j] = min(cost[i - 1][j - 1] + 1 - sims[i - 1][j - 1],
                             cost[i - 1][j] + skip_t, cost[i][j - 1] + skip_h)
    pairs, i, j = [], n, m
    while i > 0 or j > 0:
        if i and j and abs(cost[i][j] - (cost[i - 1][j - 1] + 1 - sims[i - 1][j - 1])) < 1e-9:
            pairs.append((i - 1, j - 1, sims[i - 1][j - 1])); i, j = i - 1, j - 1
        elif i and (not j or abs(cost[i][j] - (cost[i - 1][j] + skip_t)) < 1e-9):
            pairs.append((i - 1, None, 0.0)); i -= 1
        else:
            pairs.append((None, j - 1, 0.0)); j -= 1
    return list(reversed(pairs))


def phone_diff(target_ipa: str, heard_ipa: str) -> list[dict]:
    a, b = _phones(target_ipa), _phones(heard_ipa)
    ops = SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    return [{"op": op, "target": "".join(a[i1:i2]), "heard": "".join(b[j1:j2])} for op, i1, i2, j1, j2 in ops]


def _tips_for(diff: list[dict]) -> list[str]:
    tips = []
    for d in diff:
        if d["op"] in ("replace", "delete"):
            for ph in _phones(d["target"]):
                for key in (ph, ph[:1], *[c for c in ph[1:]]):
                    if key in TIPS and TIPS[key] not in tips:
                        tips.append(TIPS[key])
    return tips


def score(target: str, heard: str, words_prob: list[dict], code: str) -> dict:
    tgt = phonetics.words_ipa(target, code)
    hrd = phonetics.words_ipa(heard, code) if heard else []
    probs = [w["prob"] for w in words_prob]
    report: list[dict] = [{} for _ in tgt]
    for ti, hi, sim in align(tgt, hrd):
        if ti is None:
            continue
        word, ipa = tgt[ti]
        h_word, h_ipa = hrd[hi] if hi is not None else ("", "")
        if hi is not None and sim == 1.0 and hi < len(probs) and len(probs) == len(hrd):
            sim = 0.7 + 0.3 * probs[hi]
        diff = phone_diff(ipa, h_ipa) if sim < 0.95 else []
        report[ti] = {"word": word, "ipa": ipa, "heard": h_word, "heard_ipa": h_ipa,
                      "score": int(round(sim * 100)), "ok": bool(sim >= 0.8), "diff": diff}
    overall = round(sum(r["score"] for r in report) / len(report)) if report else 0
    tips = []
    for r in report:
        if not r["ok"]:
            tips += [t for t in _tips_for(r["diff"]) if t not in tips]
    return {"overall": overall, "words": report, "heard": heard,
            "weak_words": [r["word"] for r in report if not r["ok"]], "tips": tips[:4]}
