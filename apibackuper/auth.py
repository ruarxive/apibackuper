"""
Authentication handling for apibackuper
"""
import os
import base64
import logging
from typing import Dict

try:
    import requests  # noqa: F401, W0611
except ImportError:
    requests = None


class AuthHandler:
    """Handles various authentication methods"""

    def __init__(self, config):
        """Initialize auth handler from config"""
        self.config = config
        self.auth_type = None
        self.auth_data = {}
        self._load_auth_config()

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
                password_file = self.config.get("auth", "password_file")
                if os.path.exists(password_file):
                    with open(password_file, "r", encoding="utf-8") as f:
                        password = f.read().strip()

            if username and password:
                self.auth_data = {"username": username, "password": password}

        elif self.auth_type == "bearer":
            token = None
            if self.config.has_option("auth", "token"):
                token = self.config.get("auth", "token")
            elif self.config.has_option("auth", "token_file"):
                token_file = self.config.get("auth", "token_file")
                if os.path.exists(token_file):
                    with open(token_file, "r", encoding="utf-8") as f:
                        token = f.read().strip()

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
                token_file = self.config.get("auth", "token_file")
                if os.path.exists(token_file):
                    with open(token_file, "r", encoding="utf-8") as f:
                        token = f.read().strip()

            if self.config.has_option("auth", "auth_url"):
                auth_url = self.config.get("auth", "auth_url")
            else:
                auth_url = None
            if self.config.has_option("auth", "refresh_token"):
                refresh_token = self.config.get("auth", "refresh_token")
            else:
                refresh_token = None

            self.auth_data = {
                "token": token,
                "auth_url": auth_url,
                "refresh_token": refresh_token
            }

    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        headers = {}

        if (self.auth_type == "basic" and "username" in self.auth_data and
                "password" in self.auth_data):
            credentials = (f"{self.auth_data['username']}:"
                          f"{self.auth_data['password']}")
            encoded = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        elif self.auth_type == "bearer" and "token" in self.auth_data:
            headers["Authorization"] = f"Bearer {self.auth_data['token']}"

        elif self.auth_type == "apikey" and "api_key" in self.auth_data:
            header_name = self.auth_data.get("header", "X-API-Key")
            headers[header_name] = self.auth_data["api_key"]

        elif self.auth_type == "oauth2" and "token" in self.auth_data:
            headers["Authorization"] = f"Bearer {self.auth_data['token']}"

        return headers

    def refresh_token_if_needed(self, session):
        """Refresh OAuth2 token if needed"""
        if (self.auth_type == "oauth2" and
                self.auth_data.get("auth_url") and
                self.auth_data.get("refresh_token")):
            try:
                response = session.post(
                    self.auth_data["auth_url"],
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self.auth_data["refresh_token"]
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    if "access_token" in data:
                        self.auth_data["token"] = data["access_token"]
                        logging.info("OAuth2 token refreshed successfully")
                        return True
            except Exception as e:
                logging.warning("Failed to refresh OAuth2 token: %s", e)
        return False

