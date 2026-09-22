from app.pipeline.prompt_builder import (
    build_revision_prompt,
    build_style_rule_distill_prompt,
    build_style_rules_instruction,
    build_tone_instruction,
)


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


def test_style_rules_instruction_lists_all_rules():
    instruction = build_style_rules_instruction(["Duze den Empfänger.", "Halte dich kurz."])

    assert "GELERNTE STILVORGABEN" in instruction
    assert "- Duze den Empfänger." in instruction
    assert "- Halte dich kurz." in instruction


def test_style_rules_instruction_is_empty_without_rules():
    assert build_style_rules_instruction([]) == ""


def test_style_rule_distill_prompt_includes_feedback_and_corrected_reply():
    prompt = build_style_rule_distill_prompt("Original", "kürzer", "Korrigiert")

    assert "Original" in prompt
    assert "kürzer" in prompt
    assert "Korrigiert" in prompt


def test_style_rule_distill_prompt_omits_missing_parts():
    prompt = build_style_rule_distill_prompt("Original", None, "  ")

    assert "Feedback des Nutzers" not in prompt
    assert "Korrigierte Fassung" not in prompt


def test_revision_prompt_contains_mail_previous_reply_and_feedback():
    prompt = build_revision_prompt("  Eingehende Mail  ", "Bisherige Antwort", " kürzer ")

    assert "Eingehende Mail" in prompt
    assert "Bisherige Antwort" in prompt
    assert "kürzer" in prompt
    assert "NUR den fertigen" in prompt
