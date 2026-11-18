"""Pronunciation scoring: compare the IPA of the target phrase to the IPA of what Whisper heard."""
import re
from difflib import SequenceMatcher

from . import phonetics


def _norm(w: str) -> str:
    return re.sub(r"[^\w']", "", w.lower())


def score(target: str, heard: str, words_prob: list[dict], code: str) -> dict:
    tgt = phonetics.words_ipa(target, code)
    hrd = phonetics.words_ipa(heard, code) if heard else []
    hrd_map = {_norm(w): ipa for w, ipa in hrd}
    prob_map = {_norm(w["word"]): w["prob"] for w in words_prob}
    hrd_ipa_all = [ipa for _, ipa in hrd]

    report, total = [], 0.0
    for word, ipa in tgt:
        key = _norm(word)
        if key in hrd_map:
            sim = 1.0
        else:  # best phonetic match among heard words
            sim = max((SequenceMatcher(None, ipa, h).ratio() for h in hrd_ipa_all), default=0.0)
        conf = prob_map.get(key)
        if conf is not None and sim == 1.0:
            sim = 0.7 + 0.3 * conf  # recognised, weight by acoustic confidence
        total += sim
        report.append({"word": word, "ipa": ipa, "score": int(round(sim * 100)),
                       "ok": bool(sim >= 0.8)})
    overall = round(100 * total / len(tgt)) if tgt else 0
    weak = [r["word"] for r in report if not r["ok"]]
    return {"overall": overall, "words": report, "heard": heard, "weak_words": weak}
