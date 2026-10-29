"""
Authentication handling for apibackuper
"""

import base64
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

from .cmds.utils import redact_text

try:
    import requests  # noqa: F401, W0611
except ImportError:
    requests = None


_DEFAULT_TIMEOUT = 30  # seconds; OAuth refresh must never hang forever (§5.4)
# Renew an OAuth2 token this many seconds before ``expires_in`` runs out.
_EXPIRY_MARGIN = 60


class AuthHandler:
    """Handles various authentication methods"""

    # Class-level defaults for handlers built without ``__init__``.
    error: Optional[str] = None
    _token_lock = threading.Lock()

    def __init__(self, config):
        """Initialize auth handler from config"""
        self.config = config
        self.auth_type = None
        self.auth_data = {}
        # Set when a configured credential file is missing or empty, so
        # requests fail instead of being sent without credentials.
        self.error: Optional[str] = None
        # Serializes OAuth2 token requests across parallel page fetches.
        self._token_lock = threading.Lock()
        self._load_auth_config()

    def _read_secret(self, option: str) -> Optional[str]:
        path = self.config.get("auth", option)
        if not os.path.exists(path):
            self.error = f"auth.{option} not found: {path}"
            return None
        with open(path, "r", encoding="utf-8") as f:
            secret = f.read().strip()
        if not secret:
            self.error = f"auth.{option} is empty: {path}"
            return None
        return secret

    def _load_auth_config(self):
        """Load authentication configuration"""
        if not self.config or not self.config.has_section("auth"):
            return

        if self.config.has_option("auth", "type"):
            self.auth_type = self.config.get("auth", "type")
        else:
            self.auth_type = None

        if self.auth_type == "basic":
            if self.config.has_option("auth", "username"):
                username = self.config.get("auth", "username")
            else:
                username = None
            password = None
            if self.config.has_option("auth", "password"):
                password = self.config.get("auth", "password")
            elif self.config.has_option("auth", "password_file"):
                password = self._read_secret("password_file")

            if username and password:
                self.auth_data = {"username": username, "password": password}

        elif self.auth_type == "bearer":
            token = None
            if self.config.has_option("auth", "token"):
                token = self.config.get("auth", "token")
            elif self.config.has_option("auth", "token_file"):
                token = self._read_secret("token_file")

            if token:
                self.auth_data = {"token": token}

        elif self.auth_type == "apikey":
            if self.config.has_option("auth", "api_key"):
                api_key = self.config.get("auth", "api_key")
            else:
                api_key = None
            if self.config.has_option("auth", "api_key_header"):
                api_key_header = self.config.get("auth", "api_key_header")
            else:
                api_key_header = "X-API-Key"

            if api_key:
                self.auth_data = {"api_key": api_key, "header": api_key_header}

        elif self.auth_type == "oauth2":
            token = None
            if self.config.has_option("auth", "token"):
                token = self.config.get("auth", "token")
            elif self.config.has_option("auth", "token_file"):
                token = self._read_secret("token_file")

            if self.config.has_option("auth", "auth_url"):
                auth_url = self.config.get("auth", "auth_url")
            else:
                auth_url = None
            if self.config.has_option("auth", "refresh_token"):
                refresh_token = self.config.get("auth", "refresh_token")
            else:
                refresh_token = None
            client_secret = None
            if self.config.has_option("auth", "client_secret"):
                client_secret = self.config.get("auth", "client_secret")
            elif self.config.has_option("auth", "client_secret_file"):
                client_secret = self._read_secret("client_secret_file")

            def option(name, default=None):
                if self.config.has_option("auth", name):
                    return self.config.get("auth", name)
                return default

            self.auth_data = {
                "token": token,
                "auth_url": auth_url,
                "refresh_token": refresh_token,
                "grant_type": option("grant_type", "refresh_token"),
                "client_id": option("client_id"),
                "client_secret": client_secret,
                "scope": option("scope"),
                "audience": option("audience"),
                "client_auth_method": option("client_auth_method", "client_secret_basic"),
                # time.monotonic() deadline from ``expires_in``; None if unknown.
                "expires_at": None,
            }

    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers.

        P2.25: only emit ``Authorization: Bearer <token>`` when ``token`` is a
        non-empty string. Previously, an oauth2 config with a missing token
        would still produce ``Authorization: Bearer None`` (§5.6 of the
        2026-10 analysis report).
        """
        headers = {}

        if (
            self.auth_type == "basic"
            and "username" in self.auth_data
            and "password" in self.auth_data
        ):
            credentials = f"{self.auth_data['username']}:" f"{self.auth_data['password']}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        elif self.auth_type == "bearer" and self.auth_data.get("token"):
            headers["Authorization"] = f"Bearer {self.auth_data['token']}"

        elif self.auth_type == "apikey" and self.auth_data.get("api_key"):
            header_name = self.auth_data.get("header", "X-API-Key")
            headers[header_name] = self.auth_data["api_key"]

        elif self.auth_type == "oauth2" and self.auth_data.get("token"):
            # Was: ``self.auth_data["token"] in self.auth_data`` which evaluates
            # key *presence*, not truthiness. The truthy check above fixes
            # ``Bearer None`` (§5.6).
            headers["Authorization"] = f"Bearer {self.auth_data['token']}"

        return headers

    def ensure_token(
        self,
        session,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
    ) -> None:
        """Obtain an OAuth2 token before a request when none is valid.

        Fetches a token when there is none or it expires within
        ``_EXPIRY_MARGIN`` seconds, using client credentials or the refresh
        token. Raises ``RuntimeError`` if a client-credentials token cannot be
        obtained, so requests are never sent without credentials.
        """
        if self.auth_type != "oauth2" or not self.auth_data.get("auth_url"):
            return
        client_credentials = self.auth_data.get("grant_type") == "client_credentials"
        if not client_credentials and not self.auth_data.get("refresh_token"):
            return
        if self.auth_data.get("token") and not self._token_expiring():
            return
        renewed = self.refresh_token_if_needed(
            session, timeout=timeout, verify=verify, if_invalid=True
        )
        if not renewed and client_credentials and not self.auth_data.get("token"):
            raise RuntimeError(
                f"OAuth2 token request to {redact_text(self.auth_data['auth_url'])} failed; "
                "see the log for the response status"
            )

    def _token_expiring(self) -> bool:
        expires_at = self.auth_data.get("expires_at")
        return expires_at is not None and time.monotonic() >= expires_at - _EXPIRY_MARGIN

    def refresh_token_if_needed(
        self,
        session,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
        failed_token: Optional[str] = None,
        if_invalid: bool = False,
    ) -> bool:
        """Obtain a new OAuth2 token with the configured grant.

        P2.24: hardens the previous implementation:

        - Adds a timeout`` argument (default 30 s) so a slow IdP cannot hang
          the run forever (§5.4 of the 2026-10 analysis report).
        - Accepts ``verify`` to propagate TLS verification from the parent
          session (default: inherit from ``session``).
        - Logs failures (and HTTP error codes) instead of silently returning
          ``False`` (§5.4).
        - Captures a rotated ``refresh_token`` from the response if the IdP
          returns one (RFC 6749 §6).

        Token requests are serialized. No new request is sent when another
        thread already replaced ``failed_token`` (the token a 401 rejected), or,
        with ``if_invalid``, when a valid token is already present.
        """
        client_credentials = self.auth_data.get("grant_type") == "client_credentials"
        if not (
            self.auth_type == "oauth2"
            and self.auth_data.get("auth_url")
            and (
                self.auth_data.get("client_id")
                if client_credentials
                else self.auth_data.get("refresh_token")
            )
        ):
            return False
        with self._token_lock:
            current = self.auth_data.get("token")
            if failed_token is not None and current and current != failed_token:
                return True
            if if_invalid and current and not self._token_expiring():
                return True
            if client_credentials:
                form = {"grant_type": "client_credentials"}
                for name in ("scope", "audience"):
                    if self.auth_data.get(name):
                        form[name] = self.auth_data[name]
            else:
                form = {
                    "grant_type": "refresh_token",
                    "refresh_token": self.auth_data["refresh_token"],
                }
            return self._request_token(session, form, timeout, verify)

    def _safe_diagnostic(self, value) -> str:
        text = redact_text(value)
        for name in ("token", "refresh_token", "client_secret"):
            secret = self.auth_data.get(name)
            if isinstance(secret, str) and secret:
                text = text.replace(secret, "***REDACTED***")
        return text

    def _request_token(self, session, form, timeout, verify) -> bool:
        """POST ``form`` to the token endpoint and store the returned token."""
        effective_timeout = timeout if timeout is not None else _DEFAULT_TIMEOUT
        kwargs: Dict[str, Any] = {"data": form, "timeout": effective_timeout}
        if verify is not None:
            kwargs["verify"] = verify
        client_id = self.auth_data.get("client_id")
        if client_id:
            secret = self.auth_data.get("client_secret") or ""
            if self.auth_data.get("client_auth_method") == "client_secret_post":
                form["client_id"] = client_id
                if secret:
                    form["client_secret"] = secret
            else:
                kwargs["auth"] = (client_id, secret)

        try:
            response = session.post(self.auth_data["auth_url"], **kwargs)
        except Exception as e:
            logging.warning(
                "OAuth2 token refresh raised %s: %s",
                type(e).__name__,
                self._safe_diagnostic(e),
            )
            return False

        if response.status_code != 200:
            # P2.24: log non-200 responses instead of silently returning False.
            # Coerce the body to str defensively — the test suite uses Mock
            # objects whose ``text`` attribute is itself a Mock.
            try:
                body_preview = self._safe_diagnostic(response.text)[:200]
            except Exception:
                body_preview = "<unprintable body>"
            logging.warning(
                "OAuth2 token refresh failed: HTTP %s, body=%s",
                response.status_code,
                body_preview,
            )
            return False

        try:
            data = response.json()
        except (ValueError, TypeError):
            logging.warning("OAuth2 token refresh: response is not JSON")
            return False

        if not isinstance(data, dict) or "access_token" not in data:
            logging.warning("OAuth2 token refresh: response missing 'access_token' field")
            return False

        self.auth_data["token"] = data["access_token"]
        # P2.24: capture rotated refresh token if the IdP returns one.
        new_refresh = data.get("refresh_token")
        if new_refresh:
            self.auth_data["refresh_token"] = new_refresh
        try:
            lifetime = float(data["expires_in"])
        except (KeyError, TypeError, ValueError):
            lifetime = None
        self.auth_data["expires_at"] = time.monotonic() + lifetime if lifetime else None
        logging.info("OAuth2 token refreshed successfully")
        return True
