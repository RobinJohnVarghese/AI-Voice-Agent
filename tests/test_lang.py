from app import lang


def test_detect_common_languages():
    assert lang.detect("Bonjour, comment allez-vous aujourd'hui ?") == "fr"
    assert lang.detect("Me gustaría aprender a hablar español.") == "es"


def test_quoted_phrase_switches_language():
    runs = lang.spans('Good morning in Spanish is "Buenos días".', "en")
    assert runs == [("Good morning in Spanish is", "en"), ('"Buenos días".', "es")]


def test_unquoted_text_keeps_base():
    assert lang.spans("Hola", "es") == [("Hola", "es")]


def test_short_romanized_quote_keeps_base():
    assert lang.spans('"Konnichiwa"', "ja") == [('"Konnichiwa"', "ja")]


def test_non_latin_quote_switches():
    runs = lang.spans('Hello in Japanese is "こんにちは".', "en")
    assert runs[-1][1] == "ja"
