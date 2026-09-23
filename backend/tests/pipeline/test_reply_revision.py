from unittest.mock import AsyncMock, patch

import pytest

from app.pipeline.llm_client import LlmClientError
from app.pipeline.reply_revision import revise_reply


@pytest.mark.asyncio
async def test_revise_reply_sends_system_prompt_and_all_inputs_and_strips_result():
    with (
        patch("app.pipeline.reply_revision.build_chat_model"),
        patch(
            "app.pipeline.reply_revision.invoke_chat",
            AsyncMock(return_value="  Hallo Max, passt!\n"),
        ) as invoke,
    ):
        result = await revise_reply(
            "SYSTEM PROMPT", "Können wir uns treffen?", "Sehr geehrter Herr Max, ...", "kürzer"
        )

    assert result == "Hallo Max, passt!"
    system_message, user_message = invoke.call_args.args[1]
    assert system_message == {"role": "system", "content": "SYSTEM PROMPT"}
    assert user_message["role"] == "user"
    assert "Können wir uns treffen?" in user_message["content"]
    assert "Sehr geehrter Herr Max" in user_message["content"]
    assert "kürzer" in user_message["content"]


@pytest.mark.asyncio
async def test_revise_reply_propagates_llm_errors():
    with (
        patch("app.pipeline.reply_revision.build_chat_model"),
        patch(
            "app.pipeline.reply_revision.invoke_chat",
            AsyncMock(side_effect=LlmClientError("DGX nicht erreichbar")),
        ),
        pytest.raises(LlmClientError),
    ):
        await revise_reply("SYSTEM", "Mail", "Antwort", "kürzer")
