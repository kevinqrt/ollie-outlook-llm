import logging
import threading
from pathlib import Path

import msal

from app.core.config import settings

logger = logging.getLogger(__name__)


class GraphAuthError(RuntimeError):
    pass


class GraphAuthService:
    """Handles the Microsoft Graph OAuth Authorization Code Flow via MSAL.

    Tokens are persisted in a single JSON cache file, since OLLIE is a
    single-mailbox development tool rather than a multi-tenant product.

    The MSAL app is built lazily on first use rather than in `__init__`,
    since constructing it triggers a real network call (tenant discovery).
    This keeps the service safe to instantiate at application startup even
    before Microsoft Graph credentials have been configured.
    """

    def __init__(self) -> None:
        self._cache_path = Path(settings.token_cache_path)
        self._lock = threading.Lock()
        self._cache = self._load_cache()
        self._app: msal.ConfidentialClientApplication | None = None

    def _load_cache(self) -> msal.SerializableTokenCache:
        cache = msal.SerializableTokenCache()
        if self._cache_path.exists():
            cache.deserialize(self._cache_path.read_text(encoding="utf-8"))
        return cache

    def _persist_cache(self) -> None:
        if self._cache.has_state_changed:
            self._cache_path.write_text(self._cache.serialize(), encoding="utf-8")

    @staticmethod
    def _is_configured() -> bool:
        return bool(
            settings.graph_tenant_id and settings.graph_client_id and settings.graph_client_secret
        )

    def _get_app(self) -> msal.ConfidentialClientApplication:
        if self._app is None:
            self._app = msal.ConfidentialClientApplication(
                client_id=settings.graph_client_id,
                client_credential=settings.graph_client_secret,
                authority=f"https://login.microsoftonline.com/{settings.graph_tenant_id}",
                token_cache=self._cache,
            )
        return self._app

    def get_auth_url(self) -> str:
        """Build the Microsoft login URL the user must open to grant consent.

        Raises:
            GraphAuthError: If Microsoft Graph credentials are not configured.
        """
        if not self._is_configured():
            raise GraphAuthError("Microsoft Graph is not configured.")
        url = self._get_app().get_authorization_request_url(
            scopes=settings.graph_scopes,
            redirect_uri=settings.graph_redirect_uri,
        )
        return str(url)

    def acquire_token_by_code(self, code: str) -> None:
        """Exchange an authorization code for tokens and persist them.

        Raises:
            GraphAuthError: If Microsoft Graph credentials are not configured
                or the code exchange fails.
        """
        if not self._is_configured():
            raise GraphAuthError("Microsoft Graph is not configured.")

        with self._lock:
            result = self._get_app().acquire_token_by_authorization_code(
                code=code,
                scopes=settings.graph_scopes,
                redirect_uri=settings.graph_redirect_uri,
            )
            self._persist_cache()

        if "access_token" not in result:
            logger.error("Graph token exchange failed: %s", result.get("error_description"))
            raise GraphAuthError(
                str(result.get("error_description", "Failed to acquire access token."))
            )

    def is_authenticated(self) -> bool:
        if not self._is_configured():
            return False
        return bool(self._get_app().get_accounts())

    def get_valid_access_token(self) -> str:
        """Return a valid access token, refreshing it silently if needed.

        Raises:
            GraphAuthError: If Graph is not configured, there is no
                authenticated account, or the silent token refresh fails.
        """
        if not self._is_configured():
            raise GraphAuthError("Microsoft Graph is not configured.")

        accounts = self._get_app().get_accounts()
        if not accounts:
            raise GraphAuthError("Not authenticated with Microsoft Graph.")

        with self._lock:
            result = self._get_app().acquire_token_silent(
                scopes=settings.graph_scopes, account=accounts[0]
            )
            self._persist_cache()

        if not result or "access_token" not in result:
            raise GraphAuthError("Failed to refresh Microsoft Graph access token.")
        return str(result["access_token"])
