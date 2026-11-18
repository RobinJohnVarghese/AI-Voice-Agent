from app import pronunciation


def test_perfect_attempt_scores_high():
    r = pronunciation.score("The weather is nice.", "The weather is nice.", [], "en")
    assert r["overall"] == 100 and r["weak_words"] == []


def test_wrong_word_flagged_with_diff():
    r = pronunciation.score("The weather is wonderful today.", "The weather is thorough today.", [], "en")
    assert r["weak_words"] == ["wonderful"]
    bad = r["words"][3]
    assert bad["heard"] == "thorough" and any(d["op"] != "equal" for d in bad["diff"])


def test_th_substitution_gives_tip():
    r = pronunciation.score("think", "sink", [], "en")
    assert r["words"][0]["diff"][0] == {"op": "replace", "target": "θ", "heard": "s"}
    assert any(t.startswith("θ") for t in r["tips"])


def test_missing_word_scores_zero():
    r = pronunciation.score("I like green apples", "I like apples", [], "en")
    assert r["words"][2]["score"] == 0 and r["words"][3]["score"] == 100


def test_low_confidence_lowers_score():
    probs = [{"word": "hello", "prob": 0.2}]
    assert pronunciation.score("hello", "hello", probs, "en")["words"][0]["score"] == 76
