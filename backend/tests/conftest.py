from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.app import app
from app.core.config import settings


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Generator[TestClient]:
    """Provides a TestClient for the FastAPI app.

    Forces calendar_mock_mode off and calendar_backend to "ics" (today's
    default) regardless of the developer's local .env, so tests deterministically
    exercise the same backend independent of local machine state. The ICS and
    pipeline-settings stores are redirected to tmp files so tests never touch
    the real `ics_calendars.json` / `pipeline_settings.json` in the repo.
    """
    monkeypatch.setattr(settings, "calendar_mock_mode", False)
    monkeypatch.setattr(settings, "calendar_backend", "ics")
    monkeypatch.setattr(settings, "ics_store_path", str(tmp_path / "ics_calendars.json"))
    monkeypatch.setattr(
        settings, "pipeline_settings_path", str(tmp_path / "pipeline_settings.json")
    )
    monkeypatch.setattr(settings, "style_rules_path", str(tmp_path / "style_rules.json"))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def graph_client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Generator[TestClient]:
    """Provides a TestClient forced onto the Microsoft Graph calendar backend.

    For tests that specifically exercise Graph/Azure AD OAuth behavior (they
    patch GraphAuthService/GraphCalendarService directly) - everything else
    should use the `client` fixture instead.
    """
    monkeypatch.setattr(settings, "calendar_mock_mode", False)
    monkeypatch.setattr(settings, "calendar_backend", "graph")
    # Never talk to the developer's real Microsoft account from tests, even
    # when the local .env contains real Graph credentials.
    monkeypatch.setattr(settings, "graph_client_id", "")
    monkeypatch.setattr(settings, "graph_client_secret", "")
    monkeypatch.setattr(settings, "graph_tenant_id", "")
    monkeypatch.setattr(settings, "token_cache_path", str(tmp_path / "token_cache.json"))
    monkeypatch.setattr(
        settings, "pipeline_settings_path", str(tmp_path / "pipeline_settings.json")
    )
    monkeypatch.setattr(settings, "style_rules_path", str(tmp_path / "style_rules.json"))
    with TestClient(app) as c:
        yield c
