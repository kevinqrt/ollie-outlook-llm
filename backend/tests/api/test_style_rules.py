from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from app.pipeline.llm_client import LlmClientError

DERIVE = "app.api.router.derive_style_rule"


def _post_correction(client: TestClient, **overrides: str):
    body = {"originalReply": "Sehr geehrte Damen und Herren, ...", "feedback": "immer duzen"}
    body.update(overrides)
    return client.post("/pipeline/corrections", json=body)


def test_get_style_rules_initially_empty_and_enabled(client: TestClient) -> None:
    response = client.get("/pipeline/style-rules")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"enabled": True, "rules": []}


def test_post_correction_learns_and_stores_rule(client: TestClient) -> None:
    with patch(DERIVE, AsyncMock(return_value="Duze den Empfänger.")):
        response = _post_correction(client)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["learned"] is True
    assert body["rule"]["text"] == "Duze den Empfänger."
    rules = client.get("/pipeline/style-rules").json()["rules"]
    assert [r["text"] for r in rules] == ["Duze den Empfänger."]


def test_post_correction_passes_all_inputs_to_the_derivation(client: TestClient) -> None:
    with patch(DERIVE, AsyncMock(return_value="Halte dich kurz.")) as derive:
        _post_correction(client, correctedReply="Hallo!")

    derive.assert_awaited_once_with("Sehr geehrte Damen und Herren, ...", "immer duzen", "Hallo!")


def test_post_correction_without_general_rule_is_not_learned(client: TestClient) -> None:
    with patch(DERIVE, AsyncMock(return_value=None)):
        response = _post_correction(client)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"learned": False, "rule": None}
    assert client.get("/pipeline/style-rules").json()["rules"] == []


def test_post_correction_with_known_rule_is_not_learned_twice(client: TestClient) -> None:
    with patch(DERIVE, AsyncMock(return_value="Duze den Empfänger.")):
        _post_correction(client)
        second = _post_correction(client)

    assert second.json()["learned"] is False
    assert len(client.get("/pipeline/style-rules").json()["rules"]) == 1


def test_post_correction_requires_feedback_or_corrected_reply(client: TestClient) -> None:
    response = client.post("/pipeline/corrections", json={"originalReply": "Antwort"})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_post_correction_returns_503_when_llm_fails(client: TestClient) -> None:
    with patch(DERIVE, AsyncMock(side_effect=LlmClientError("DGX-Anfrage fehlgeschlagen"))):
        response = _post_correction(client)

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "DGX" in response.json()["detail"]


def test_post_correction_returns_409_when_learning_is_off(client: TestClient) -> None:
    client.put("/pipeline/style-rules/settings", json={"enabled": False})

    with patch(DERIVE, AsyncMock(return_value="x")) as derive:
        response = _post_correction(client)

    assert response.status_code == status.HTTP_409_CONFLICT
    derive.assert_not_awaited()


def test_put_settings_toggles_enabled(client: TestClient) -> None:
    response = client.put("/pipeline/style-rules/settings", json={"enabled": False})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["enabled"] is False
    assert client.get("/pipeline/style-rules").json()["enabled"] is False


def test_delete_rule_removes_it(client: TestClient) -> None:
    with patch(DERIVE, AsyncMock(return_value="Regel A")):
        rule_id = _post_correction(client).json()["rule"]["id"]

    response = client.delete(f"/pipeline/style-rules/{rule_id}")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert client.get("/pipeline/style-rules").json()["rules"] == []


def test_delete_unknown_rule_returns_404(client: TestClient) -> None:
    response = client.delete("/pipeline/style-rules/does-not-exist")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_all_rules(client: TestClient) -> None:
    for text in ("Regel A", "Regel B"):
        with patch(DERIVE, AsyncMock(return_value=text)):
            _post_correction(client)

    response = client.delete("/pipeline/style-rules")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert client.get("/pipeline/style-rules").json()["rules"] == []
