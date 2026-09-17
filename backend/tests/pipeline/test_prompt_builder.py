from app.pipeline.prompt_builder import build_tone_instruction


def test_friendly_tone_returns_fixed_instruction():
    assert "freundlichen" in build_tone_instruction("friendly", None)


def test_formal_tone_returns_fixed_instruction():
    assert "formellen" in build_tone_instruction("formal", None)


def test_casual_tone_returns_fixed_instruction():
    assert "lockeren" in build_tone_instruction("casual", None)


def test_custom_tone_with_text_includes_the_text():
    instruction = build_tone_instruction("custom", "sehr knapp und direkt")

    assert "sehr knapp und direkt" in instruction


def test_custom_tone_without_text_returns_empty_string():
    assert build_tone_instruction("custom", None) == ""
    assert build_tone_instruction("custom", "   ") == ""


def test_unknown_tone_falls_back_to_friendly():
    assert build_tone_instruction("does-not-exist", None) == build_tone_instruction(
        "friendly", None
    )
