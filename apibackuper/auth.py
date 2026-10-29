"""
Authentication handling for apibackuper
"""

import base64
import logging
import os
from typing import Any, Dict, Optional

from .cmds.utils import redact_text

try:
    import requests  # noqa: F401, W0611
except ImportError:
    requests = None


_DEFAULT_TIMEOUT = 30  # seconds; OAuth refresh must never hang forever (§5.4)


class AuthHandler:
    """Handles various authentication methods"""

    def __init__(self, config):
        """Initialize auth handler from config"""
        self.config = config
        self.auth_type = None
        self.auth_data = {}
        # Set when a configured credential file is missing or empty, so
        # requests fail instead of being sent without credentials.
        self.error: Optional[str] = None
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

            self.auth_data = {"token": token, "auth_url": auth_url, "refresh_token": refresh_token}

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

    def refresh_token_if_needed(
        self,
        session,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
    ) -> bool:
        """Refresh OAuth2 token if needed.

        P2.24: hardens the previous implementation:

        - Adds a timeout`` argument (default 30 s) so a slow IdP cannot hang
          the run forever (§5.4 of the 2026-10 analysis report).
        - Accepts ``verify`` to propagate TLS verification from the parent
          session (default: inherit from ``session``).
        - Logs failures (and HTTP error codes) instead of silently returning
          ``False`` (§5.4).
        - Captures a rotated ``refresh_token`` from the response if the IdP
          returns one (RFC 6749 §6).
        """
        if not (
            self.auth_type == "oauth2"
            and self.auth_data.get("auth_url")
            and self.auth_data.get("refresh_token")
        ):
            return False

        effective_timeout = timeout if timeout is not None else _DEFAULT_TIMEOUT

        def safe_diagnostic(value):
            text = redact_text(value)
            for name in ("token", "refresh_token"):
                secret = self.auth_data.get(name)
                if isinstance(secret, str) and secret:
                    text = text.replace(secret, "***REDACTED***")
            return text

        kwargs: Dict[str, Any] = {
            "data": {
                "grant_type": "refresh_token",
                "refresh_token": self.auth_data["refresh_token"],
            },
            "timeout": effective_timeout,
        }
        if verify is not None:
            kwargs["verify"] = verify

        try:
            response = session.post(self.auth_data["auth_url"], **kwargs)
        except Exception as e:
            logging.warning(
                "OAuth2 token refresh raised %s: %s",
                type(e).__name__,
                safe_diagnostic(e),
            )
            return False

        if response.status_code != 200:
            # P2.24: log non-200 responses instead of silently returning False.
            # Coerce the body to str defensively — the test suite uses Mock
            # objects whose ``text`` attribute is itself a Mock.
            try:
                body_preview = safe_diagnostic(response.text)[:200]
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
        logging.info("OAuth2 token refreshed successfully")
        return True
