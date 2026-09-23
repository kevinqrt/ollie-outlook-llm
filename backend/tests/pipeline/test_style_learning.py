from unittest.mock import AsyncMock, patch

import pytest

from app.pipeline.llm_client import LlmClientError
from app.pipeline.style_learning import MAX_RULE_LENGTH, derive_style_rule, normalize_rule


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Duze den Empfänger.", "Duze den Empfänger."),
        ("- Duze den Empfänger.", "Duze den Empfänger."),
        ("• Duze den Empfänger.", "Duze den Empfänger."),
        ('"Duze den Empfänger."', "Duze den Empfänger."),
        ("„Duze den Empfänger.“", "Duze den Empfänger."),
        ("Duze den Empfänger.\n\nDas war meine Begründung.", "Duze den Empfänger."),
        ("KEINE", None),
        ("keine.", None),
        ("   \n  ", None),
        ("", None),
    ],
)
def test_normalize_rule(raw: str, expected: str | None):
    assert normalize_rule(raw) == expected


def test_normalize_rule_truncates_overlong_rules():
    assert len(normalize_rule("a" * 1000) or "") == MAX_RULE_LENGTH


@pytest.mark.asyncio
async def test_derive_style_rule_returns_normalized_rule_and_sends_all_inputs():
    with (
        patch("app.pipeline.style_learning.build_chat_model"),
        patch(
            "app.pipeline.style_learning.invoke_chat",
            AsyncMock(return_value="- Halte Antworten kurz."),
        ) as invoke,
    ):
        rule = await derive_style_rule("Sehr geehrte Damen und Herren, ...", "kürzer", "Hallo!")

    assert rule == "Halte Antworten kurz."
    prompt = invoke.call_args.args[1][0]["content"]
    assert "Sehr geehrte Damen und Herren" in prompt
    assert "kürzer" in prompt
    assert "Hallo!" in prompt


@pytest.mark.asyncio
async def test_derive_style_rule_returns_none_for_content_only_change():
    with (
        patch("app.pipeline.style_learning.build_chat_model"),
        patch("app.pipeline.style_learning.invoke_chat", AsyncMock(return_value="KEINE")),
    ):
        assert await derive_style_rule("Antwort", "Termin ist am Dienstag", None) is None


@pytest.mark.asyncio
async def test_derive_style_rule_propagates_llm_errors():
    with (
        patch("app.pipeline.style_learning.build_chat_model"),
        patch(
            "app.pipeline.style_learning.invoke_chat",
            AsyncMock(side_effect=LlmClientError("DGX nicht erreichbar")),
        ),
        pytest.raises(LlmClientError),
    ):
        await derive_style_rule("Antwort", "kürzer", None)
