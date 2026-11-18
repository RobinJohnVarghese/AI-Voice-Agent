from app.store import Store


def test_history_and_progress():
    s = Store(":memory:")
    s.add_message("a", "user", "hi", "en", "text")
    s.add_message("a", "assistant", "hello", "en", "text")
    assert [m["role"] for m in s.history("a")] == ["user", "assistant"]
    s.clear("a")
    assert s.history("a") == []

    s.add_attempt("think", "en", {"overall": 50, "heard": "sink", "words": [{"word": "think", "score": 50}]})
    p = s.progress()
    assert p["attempts"] == 1 and p["weak_words"][0]["word"] == "think"
