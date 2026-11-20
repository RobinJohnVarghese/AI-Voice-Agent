from datetime import datetime

from app.llm import LLM


def test_system_prompt_includes_current_date():
    msgs = LLM().messages([], "What day is it?", "en")
    assert datetime.now().strftime("%A") in msgs[0]["content"]
    assert msgs[-1]["content"].startswith("What day is it?")
