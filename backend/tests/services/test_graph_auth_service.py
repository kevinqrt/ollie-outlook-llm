from unittest.mock import MagicMock, patch

import pytest

from app.services.graph_auth_service import GraphAuthError, GraphAuthService


@pytest.fixture
def auth_service(tmp_path, monkeypatch):
    """A configured GraphAuthService with a mocked MSAL app injected directly."""
    monkeypatch.setattr(
        "app.services.graph_auth_service.settings.token_cache_path",
        str(tmp_path / "token_cache.json"),
    )
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_client_id", "client-id")
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_client_secret", "secret")
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_tenant_id", "tenant-id")
    service = GraphAuthService()
    service._app = MagicMock()
    return service


def test_load_cache_deserializes_existing_file(tmp_path, monkeypatch):
    cache_path = tmp_path / "token_cache.json"
    cache_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "app.services.graph_auth_service.settings.token_cache_path", str(cache_path)
    )

    with (
        patch("app.services.graph_auth_service.msal.ConfidentialClientApplication"),
        patch(
            "app.services.graph_auth_service.msal.SerializableTokenCache.deserialize"
        ) as mock_deserialize,
    ):
        GraphAuthService()

    mock_deserialize.assert_called_once_with("{}")


def test_get_app_constructs_msal_app_lazily_once(auth_service):
    auth_service._app = None

    with patch("app.services.graph_auth_service.msal.ConfidentialClientApplication") as mock_cls:
        first = auth_service._get_app()
        second = auth_service._get_app()

    mock_cls.assert_called_once()
    assert first is second


def test_is_authenticated_false_when_not_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.graph_auth_service.settings.token_cache_path",
        str(tmp_path / "token_cache.json"),
    )
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_client_id", "")
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_client_secret", "")
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_tenant_id", "")

    service = GraphAuthService()

    assert service.is_authenticated() is False


def test_get_auth_url_raises_when_not_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.graph_auth_service.settings.token_cache_path",
        str(tmp_path / "token_cache.json"),
    )
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_client_id", "")
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_client_secret", "")
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_tenant_id", "")

    service = GraphAuthService()

    with pytest.raises(GraphAuthError, match="not configured"):
        service.get_auth_url()


def test_acquire_token_by_code_raises_when_not_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.graph_auth_service.settings.token_cache_path",
        str(tmp_path / "token_cache.json"),
    )
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_client_id", "")
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_client_secret", "")
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_tenant_id", "")

    service = GraphAuthService()

    with pytest.raises(GraphAuthError, match="not configured"):
        service.acquire_token_by_code("some-code")


def test_get_valid_access_token_raises_when_not_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.graph_auth_service.settings.token_cache_path",
        str(tmp_path / "token_cache.json"),
    )
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_client_id", "")
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_client_secret", "")
    monkeypatch.setattr("app.services.graph_auth_service.settings.graph_tenant_id", "")

    service = GraphAuthService()

    with pytest.raises(GraphAuthError, match="not configured"):
        service.get_valid_access_token()


def test_get_auth_url_builds_url_from_msal(auth_service):
    auth_service._app.get_authorization_request_url.return_value = (
        "https://login.microsoftonline.com/authorize"
    )

    url = auth_service.get_auth_url()

    assert url == "https://login.microsoftonline.com/authorize"
    auth_service._app.get_authorization_request_url.assert_called_once()


def test_acquire_token_by_code_success_persists_cache(auth_service, tmp_path):
    auth_service._app.acquire_token_by_authorization_code.return_value = {"access_token": "abc123"}
    auth_service._cache.has_state_changed = True

    auth_service.acquire_token_by_code("valid-code")

    cache_path = tmp_path / "token_cache.json"
    assert cache_path.exists()


def test_acquire_token_by_code_does_not_persist_when_cache_unchanged(auth_service, tmp_path):
    auth_service._app.acquire_token_by_authorization_code.return_value = {"access_token": "abc123"}
    auth_service._cache.has_state_changed = False

    auth_service.acquire_token_by_code("valid-code")

    assert not (tmp_path / "token_cache.json").exists()


def test_acquire_token_by_code_failure_raises(auth_service):
    auth_service._app.acquire_token_by_authorization_code.return_value = {
        "error": "invalid_grant",
        "error_description": "Code expired.",
    }

    with pytest.raises(GraphAuthError, match="Code expired"):
        auth_service.acquire_token_by_code("expired-code")


def test_is_authenticated_true_with_accounts(auth_service):
    auth_service._app.get_accounts.return_value = [{"username": "a@b.com"}]
    assert auth_service.is_authenticated() is True


def test_is_authenticated_false_without_accounts(auth_service):
    auth_service._app.get_accounts.return_value = []
    assert auth_service.is_authenticated() is False


def test_get_valid_access_token_without_account_raises(auth_service):
    auth_service._app.get_accounts.return_value = []

    with pytest.raises(GraphAuthError, match="Not authenticated"):
        auth_service.get_valid_access_token()


def test_get_valid_access_token_success(auth_service):
    auth_service._app.get_accounts.return_value = [{"username": "a@b.com"}]
    auth_service._app.acquire_token_silent.return_value = {"access_token": "xyz789"}

    token = auth_service.get_valid_access_token()

    assert token == "xyz789"


def test_get_valid_access_token_silent_refresh_failure_raises(auth_service):
    auth_service._app.get_accounts.return_value = [{"username": "a@b.com"}]
    auth_service._app.acquire_token_silent.return_value = None

    with pytest.raises(GraphAuthError, match="Failed to refresh"):
        auth_service.get_valid_access_token()
