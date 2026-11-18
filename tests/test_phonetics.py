from app import phonetics


def test_ipa_has_stress_and_punctuation():
    ipa = phonetics.to_ipa("Hello, world.", "en")
    assert "ˈ" in ipa and "," in ipa


def test_respelling_marks_stressed_syllable():
    assert phonetics.respell("croissant", "fr") == "krwah-SAN"
    assert phonetics.respell("hello", "en") == "huh-LOH"


def test_respelling_keeps_indic_vowel_signs():
    assert phonetics.words_ipa("नमस्ते,", "hi")[0][0] == "नमस्ते"


def test_romanization():
    assert phonetics.romanize("你好。", "zh") == "nǐ hǎo."
    assert phonetics.romanize("こんにちは", "ja") == "konnichiwa"
    assert phonetics.romanize("hola", "es") is None


def test_annotate_shape():
    out = phonetics.annotate("Me gusta la música.", "es")
    assert set(out) == {"ipa", "romanized", "readable"}
    assert out["readable"].startswith("meh GOOS-tah")


def test_japanese_particle_wa():
    assert phonetics.romanize("こんにちは", "ja") == "konnichiwa"
    assert "wa" in phonetics.romanize("私は学生です", "ja").split()
