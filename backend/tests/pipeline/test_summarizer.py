from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.pipeline import summarizer
from app.pipeline.llm_client import LlmClientError


@pytest.mark.anyio
async def test_summarize_thread_success():
    fake_model = MagicMock()

    with (
        patch.object(summarizer, "build_chat_model", return_value=fake_model),
        patch.object(
            summarizer, "invoke_chat", AsyncMock(return_value="Kurze Zusammenfassung.")
        ) as mock_invoke,
    ):
        result = await summarizer.summarize_thread("Hallo, Testmail.")

    assert result == "Kurze Zusammenfassung."
    mock_invoke.assert_awaited_once()
    model_arg, messages_arg = mock_invoke.await_args.args
    assert model_arg is fake_model
    assert messages_arg[0]["role"] == "system"
    assert messages_arg[1] == {"role": "user", "content": "Hallo, Testmail."}


@pytest.mark.anyio
async def test_summarize_thread_propagates_llm_client_error():
    with (
        patch.object(summarizer, "build_chat_model", return_value=MagicMock()),
        patch.object(
            summarizer,
            "invoke_chat",
            AsyncMock(side_effect=LlmClientError("DGX-Anfrage fehlgeschlagen")),
        ),
        pytest.raises(LlmClientError, match="DGX-Anfrage fehlgeschlagen"),
    ):
        await summarizer.summarize_thread("Testmail")
