import pytest

from app.services.pipeline_settings_service import (
    DEFAULT_PROMPT_ID,
    PipelineSettingsStore,
    SavedPromptNotFoundError,
)


@pytest.fixture
def store(tmp_path) -> PipelineSettingsStore:
    return PipelineSettingsStore(str(tmp_path / "pipeline_settings.json"), "DEFAULT PROMPT")


def test_prompt_and_clarifying_questions_default(store: PipelineSettingsStore):
    assert store.get_prompt() == "DEFAULT PROMPT"
    assert store.get_allow_clarifying_questions() is False
    assert store.get_tone() == "friendly"
    assert store.get_custom_tone_text() is None


def test_update_persists_prompt_and_toggle(tmp_path):
    path = str(tmp_path / "pipeline_settings.json")
    store = PipelineSettingsStore(path, "DEFAULT PROMPT")

    store.update(prompt="Custom prompt", allow_clarifying_questions=True)

    assert store.get_prompt() == "Custom prompt"
    assert store.get_allow_clarifying_questions() is True

    # A freshly loaded store (e.g. after a restart) must see the same values.
    reloaded = PipelineSettingsStore(path, "DEFAULT PROMPT")
    assert reloaded.get_prompt() == "Custom prompt"
    assert reloaded.get_allow_clarifying_questions() is True


def test_update_persists_tone_and_custom_tone_text(tmp_path):
    path = str(tmp_path / "pipeline_settings.json")
    store = PipelineSettingsStore(path, "DEFAULT PROMPT")

    store.update(
        prompt="Custom prompt",
        allow_clarifying_questions=False,
        tone="custom",
        custom_tone_text="sehr knapp und direkt",
    )

    assert store.get_tone() == "custom"
    assert store.get_custom_tone_text() == "sehr knapp und direkt"

    # Survives a restart, same as prompt/allow_clarifying_questions.
    reloaded = PipelineSettingsStore(path, "DEFAULT PROMPT")
    assert reloaded.get_tone() == "custom"
    assert reloaded.get_custom_tone_text() == "sehr knapp und direkt"


def test_settings_file_written_before_tone_feature_falls_back_to_friendly(tmp_path):
    # An existing pipeline_settings.json from before this feature has no
    # "tone"/"custom_tone_text" keys at all - must not crash, must default to
    # "friendly" instead.
    path = tmp_path / "pipeline_settings.json"
    path.write_text(
        '{"prompt": "Custom prompt", "allow_clarifying_questions": true, "saved_prompts": []}',
        encoding="utf-8",
    )

    store = PipelineSettingsStore(str(path), "DEFAULT PROMPT")

    assert store.get_tone() == "friendly"
    assert store.get_custom_tone_text() is None


def test_saved_prompts_start_empty(store: PipelineSettingsStore):
    assert store.list_saved_prompts() == []


def test_add_saved_prompt_appears_in_list(store: PipelineSettingsStore):
    entry = store.add_saved_prompt("Antworte immer auf Englisch.")

    assert entry["text"] == "Antworte immer auf Englisch."
    assert entry["id"]
    assert store.list_saved_prompts() == [entry]


def test_update_saved_prompt_changes_text(store: PipelineSettingsStore):
    entry = store.add_saved_prompt("Erster Text")

    updated = store.update_saved_prompt(entry["id"], "Geänderter Text")

    assert updated["id"] == entry["id"]
    assert updated["text"] == "Geänderter Text"
    assert store.list_saved_prompts() == [updated]


def test_update_unknown_saved_prompt_raises(store: PipelineSettingsStore):
    # Updating a nonexistent id must fail clearly instead of silently doing nothing.
    with pytest.raises(SavedPromptNotFoundError):
        store.update_saved_prompt("does-not-exist", "text")


def test_get_default_prompt_survives_overwriting_the_active_prompt(
    store: PipelineSettingsStore,
):
    # Regression: a user editing the prompt field and saving must not lose the
    # original default forever - it stays recoverable via get_default_prompt().
    store.update(
        prompt="Ich habe den Standard versehentlich ersetzt.",
        allow_clarifying_questions=False,
    )

    assert store.get_prompt() == "Ich habe den Standard versehentlich ersetzt."
    assert store.get_default_prompt() == "DEFAULT PROMPT"


def test_update_saved_prompt_rejects_reserved_default_id(store: PipelineSettingsStore):
    # The synthesized default entry (id="default") must never become editable,
    # even if a real saved prompt with that literal id were somehow requested.
    with pytest.raises(SavedPromptNotFoundError):
        store.update_saved_prompt(DEFAULT_PROMPT_ID, "Neuer Text")


def test_delete_saved_prompt_removes_it(store: PipelineSettingsStore):
    entry = store.add_saved_prompt("Zu loeschender Text")

    store.delete_saved_prompt(entry["id"])

    assert store.list_saved_prompts() == []


def test_delete_unknown_saved_prompt_raises(store: PipelineSettingsStore):
    with pytest.raises(SavedPromptNotFoundError):
        store.delete_saved_prompt("does-not-exist")


def test_delete_saved_prompt_rejects_reserved_default_id(store: PipelineSettingsStore):
    # The synthesized default entry must never be deletable either.
    with pytest.raises(SavedPromptNotFoundError):
        store.delete_saved_prompt(DEFAULT_PROMPT_ID)


def test_delete_only_removes_the_targeted_prompt(store: PipelineSettingsStore):
    keep = store.add_saved_prompt("Bleibt erhalten")
    remove = store.add_saved_prompt("Wird geloescht")

    store.delete_saved_prompt(remove["id"])

    assert store.list_saved_prompts() == [keep]


def test_missing_settings_file_starts_with_default_prompt(tmp_path):
    # No file has ever been written yet (fresh install) - must not crash and
    # must fall back to the default prompt, checked right at startup.
    store = PipelineSettingsStore(str(tmp_path / "does-not-exist.json"), "DEFAULT PROMPT")

    assert store.get_prompt() == "DEFAULT PROMPT"


def test_corrupted_settings_file_falls_back_to_default_instead_of_crashing(tmp_path, caplog):
    # A settings file can end up truncated/corrupted (e.g. a crash mid-write).
    # Startup must recover with the default prompt instead of taking the
    # whole backend down with an unhandled JSONDecodeError.
    path = tmp_path / "pipeline_settings.json"
    path.write_text("{not valid json", encoding="utf-8")

    with caplog.at_level("WARNING"):
        store = PipelineSettingsStore(str(path), "DEFAULT PROMPT")

    assert store.get_prompt() == "DEFAULT PROMPT"
    assert store.list_saved_prompts() == []
    assert "konnten nicht gelesen werden" in caplog.text


def test_startup_logs_which_prompt_is_active(tmp_path, caplog):
    path = str(tmp_path / "pipeline_settings.json")

    with caplog.at_level("INFO"):
        PipelineSettingsStore(path, "DEFAULT PROMPT")
    assert "Standard-Prompt" in caplog.text

    caplog.clear()
    store = PipelineSettingsStore(path, "DEFAULT PROMPT")
    store.update(prompt="Custom prompt", allow_clarifying_questions=False)

    caplog.clear()
    with caplog.at_level("INFO"):
        PipelineSettingsStore(path, "DEFAULT PROMPT")
    assert "benutzerdefinierter Prompt aktiv" in caplog.text
