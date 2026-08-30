import pytest

from app.services.llm_service import LlmService, LlmServiceError


def test_parse_action_response_plain_json() -> None:
    """Tests parsing a clean JSON response."""
    raw = (
        '{"category": "action", "actionType": "meeting", "actionSummary": "Termin", '
        '"linkIndex": null, "meeting": null}'
    )

    result = LlmService._parse_action_response(raw)

    assert result.category == "action"
    assert result.action_type == "meeting"


def test_parse_action_response_markdown_fenced() -> None:
    """Tests parsing a JSON response wrapped in a markdown code fence, as models often do."""
    raw = '```json\n{"category": "newsletter"}\n```'

    result = LlmService._parse_action_response(raw)

    assert result.category == "newsletter"


def test_parse_action_response_with_stray_text() -> None:
    """Tests parsing JSON surrounded by extraneous model chatter."""
    raw = 'Here is the classification:\n{"category": "info"}\nLet me know if you need more.'

    result = LlmService._parse_action_response(raw)

    assert result.category == "info"


def test_parse_action_response_no_json_raises() -> None:
    """Tests that a response without any JSON object raises a clear error."""
    with pytest.raises(LlmServiceError, match="did not contain JSON"):
        LlmService._parse_action_response("Sorry, I cannot classify this email.")


def test_parse_action_response_invalid_schema_raises() -> None:
    """Tests that JSON not matching the schema raises a clear error."""
    with pytest.raises(LlmServiceError, match="did not match the expected schema"):
        LlmService._parse_action_response('{"category": "not-a-real-category"}')
