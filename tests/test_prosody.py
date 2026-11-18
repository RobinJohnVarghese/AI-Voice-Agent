from app import prosody


def test_pauses_follow_punctuation():
    segs = prosody.segment("Hello, how are you? I am fine... Thanks!")
    assert [s.text for s in segs] == ["Hello,", "how are you?", "I am fine...", "Thanks!"]
    assert [s.pause for s in segs] == [0.22, 0.60, 0.80, 0.55]


def test_markdown_and_bullets_are_stripped():
    segs = prosody.segment("**Bold** text.\n- item one\n- item two")
    assert segs[0].text == "Bold text."
    assert all("*" not in s.text and not s.text.startswith("-") for s in segs)


def test_indic_and_cjk_marks():
    assert prosody.segment("नमस्ते। आप कैसे हैं?")[0].pause == 0.55
    assert prosody.segment("你好，世界。")[0].pause == 0.22


def test_question_mark_kept_for_intonation():
    assert prosody.segment("¿Cómo estás?")[0].text.endswith("?")
