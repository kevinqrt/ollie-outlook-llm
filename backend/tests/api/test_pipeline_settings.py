from fastapi import status
from fastapi.testclient import TestClient


def test_get_settings_returns_default_prompt_initially(client: TestClient) -> None:
    response = client.get("/pipeline/settings")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["prompt"]
    assert body["allowClarifyingQuestions"] is False
    assert body["tone"] == "friendly"
    assert body["customToneText"] is None


def test_put_settings_persists_and_is_returned_by_get(client: TestClient) -> None:
    put_response = client.put(
        "/pipeline/settings",
        json={"prompt": "Antworte immer auf Englisch.", "allowClarifyingQuestions": True},
    )
    assert put_response.status_code == status.HTTP_200_OK
    assert put_response.json() == {
        "prompt": "Antworte immer auf Englisch.",
        "allowClarifyingQuestions": True,
        "tone": "friendly",
        "customToneText": None,
    }

    get_response = client.get("/pipeline/settings")
    assert get_response.json() == {
        "prompt": "Antworte immer auf Englisch.",
        "allowClarifyingQuestions": True,
        "tone": "friendly",
        "customToneText": None,
    }


def test_put_settings_persists_custom_tone(client: TestClient) -> None:
    put_response = client.put(
        "/pipeline/settings",
        json={
            "prompt": "Standard-Prompt",
            "allowClarifyingQuestions": False,
            "tone": "custom",
            "customToneText": "sehr knapp und direkt",
        },
    )
    assert put_response.status_code == status.HTTP_200_OK
    assert put_response.json()["tone"] == "custom"
    assert put_response.json()["customToneText"] == "sehr knapp und direkt"

    get_response = client.get("/pipeline/settings")
    assert get_response.json()["tone"] == "custom"
    assert get_response.json()["customToneText"] == "sehr knapp und direkt"


def test_put_settings_rejects_custom_tone_without_text(client: TestClient) -> None:
    response = client.put(
        "/pipeline/settings",
        json={
            "prompt": "Standard-Prompt",
            "allowClarifyingQuestions": False,
            "tone": "custom",
            "customToneText": "",
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_saved_prompts_list_always_includes_default_first(client: TestClient) -> None:
    response = client.get("/pipeline/settings/prompts")

    assert response.status_code == status.HTTP_200_OK
    prompts = response.json()["prompts"]
    assert len(prompts) == 1
    assert prompts[0]["id"] == "default"
    assert prompts[0]["isDefault"] is True
    assert prompts[0]["text"]


def test_default_prompt_stays_recoverable_after_overwriting_active_prompt(
    client: TestClient,
) -> None:
    # Regression: editing the prompt field and saving over the original default
    # must not make the default disappear from the library.
    default_text = client.get("/pipeline/settings/prompts").json()["prompts"][0]["text"]

    client.put(
        "/pipeline/settings",
        json={
            "prompt": "Ich habe den Standard versehentlich ersetzt.",
            "allowClarifyingQuestions": False,
        },
    )

    prompts = client.get("/pipeline/settings/prompts").json()["prompts"]
    assert prompts[0]["id"] == "default"
    assert prompts[0]["text"] == default_text


def test_create_and_update_saved_prompt(client: TestClient) -> None:
    create_response = client.post(
        "/pipeline/settings/prompts", json={"text": "Kurz und knapp antworten."}
    )
    assert create_response.status_code == status.HTTP_200_OK
    created = create_response.json()
    assert created["text"] == "Kurz und knapp antworten."
    assert created["isDefault"] is False

    update_response = client.put(
        f"/pipeline/settings/prompts/{created['id']}",
        json={"text": "Noch kürzer antworten."},
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["text"] == "Noch kürzer antworten."

    prompts = client.get("/pipeline/settings/prompts").json()["prompts"]
    assert [p["text"] for p in prompts] == [prompts[0]["text"], "Noch kürzer antworten."]


def test_update_default_prompt_is_rejected(client: TestClient) -> None:
    response = client.put(
        "/pipeline/settings/prompts/default", json={"text": "Sollte nicht klappen."}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_update_unknown_saved_prompt_returns_404(client: TestClient) -> None:
    response = client.put("/pipeline/settings/prompts/does-not-exist", json={"text": "Text"})

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_saved_prompt_removes_it_from_the_list(client: TestClient) -> None:
    created = client.post(
        "/pipeline/settings/prompts", json={"text": "Zu loeschender Prompt"}
    ).json()

    delete_response = client.delete(f"/pipeline/settings/prompts/{created['id']}")
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    prompts = client.get("/pipeline/settings/prompts").json()["prompts"]
    assert [p["id"] for p in prompts] == ["default"]


def test_delete_default_prompt_is_rejected(client: TestClient) -> None:
    response = client.delete("/pipeline/settings/prompts/default")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    prompts = client.get("/pipeline/settings/prompts").json()["prompts"]
    assert prompts[0]["id"] == "default"


def test_delete_unknown_saved_prompt_returns_404(client: TestClient) -> None:
    response = client.delete("/pipeline/settings/prompts/does-not-exist")

    assert response.status_code == status.HTTP_404_NOT_FOUND
