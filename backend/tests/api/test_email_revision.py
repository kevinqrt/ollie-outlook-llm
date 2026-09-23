from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from app.pipeline.llm_client import LlmClientError

REVISE = "app.api.router.revise_reply"
PAYLOAD = {
    "emailContent": "Können wir das Meeting verschieben?",
    "previousReply": "Sehr geehrte Damen und Herren, gerne ...",
    "feedback": "kürzer",
}


def test_revise_returns_the_revised_reply(client: TestClient) -> None:
    with patch(REVISE, AsyncMock(return_value="Klar, passt!")) as revise:
        response = client.post("/email/suggestion/revise", json=PAYLOAD)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"finalReply": "Klar, passt!"}
    _, email_content, previous_reply, feedback = revise.call_args.args
    assert email_content == PAYLOAD["emailContent"]
    assert previous_reply == PAYLOAD["previousReply"]
    assert feedback == "kürzer"


def test_revise_uses_tone_and_learned_style_rules_in_system_prompt(client: TestClient) -> None:
    client.put(
        "/pipeline/settings",
        json={"prompt": "BASIS-PROMPT", "tone": "custom", "customToneText": "sehr knapp"},
    )
    with patch("app.api.router.derive_style_rule", AsyncMock(return_value="Duze den Empfänger.")):
        client.post("/pipeline/corrections", json={"originalReply": "Antwort", "feedback": "duzen"})

    with patch(REVISE, AsyncMock(return_value="ok")) as revise:
        client.post("/email/suggestion/revise", json=PAYLOAD)

    system_prompt = revise.call_args.args[0]
    assert "BASIS-PROMPT" in system_prompt
    assert "sehr knapp" in system_prompt
    assert "- Duze den Empfänger." in system_prompt


def test_revise_ignores_style_rules_when_learning_is_off(client: TestClient) -> None:
    with patch("app.api.router.derive_style_rule", AsyncMock(return_value="Duze den Empfänger.")):
        client.post("/pipeline/corrections", json={"originalReply": "Antwort", "feedback": "duzen"})
    client.put("/pipeline/style-rules/settings", json={"enabled": False})

    with patch(REVISE, AsyncMock(return_value="ok")) as revise:
        client.post("/email/suggestion/revise", json=PAYLOAD)

    assert "GELERNTE STILVORGABEN" not in revise.call_args.args[0]


def test_revise_does_not_store_the_feedback_as_a_rule(client: TestClient) -> None:
    with patch(REVISE, AsyncMock(return_value="ok")):
        client.post("/email/suggestion/revise", json=PAYLOAD)

    assert client.get("/pipeline/style-rules").json()["rules"] == []


def test_revise_rejects_empty_feedback(client: TestClient) -> None:
    response = client.post("/email/suggestion/revise", json={**PAYLOAD, "feedback": ""})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_revise_returns_503_when_llm_fails(client: TestClient) -> None:
    with patch(REVISE, AsyncMock(side_effect=LlmClientError("DGX-Anfrage fehlgeschlagen"))):
        response = client.post("/email/suggestion/revise", json=PAYLOAD)

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "DGX" in response.json()["detail"]
