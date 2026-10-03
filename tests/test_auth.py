"""Tests for authentication handler"""
import os
import base64
import tempfile
import pytest
import configparser
from unittest.mock import Mock, patch, PropertyMock
from apibackuper.auth import AuthHandler


class TestAuthHandler:
    """Tests for AuthHandler class"""
    
    def test_init_no_auth_section(self):
        """Test initializing without auth section"""
        config = configparser.ConfigParser()
        handler = AuthHandler(config)
        assert handler.auth_type is None
        assert handler.auth_data == {}
    
    def test_init_basic_auth(self):
        """Test initializing with basic auth"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "basic")
        config.set("auth", "username", "testuser")
        config.set("auth", "password", "testpass")
        
        handler = AuthHandler(config)
        assert handler.auth_type == "basic"
        assert handler.auth_data["username"] == "testuser"
        assert handler.auth_data["password"] == "testpass"
    
    def test_init_basic_auth_password_file(self):
        """Test basic auth with password from file"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "basic")
        config.set("auth", "username", "testuser")
        
        # Create temporary password file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("testpass")
            password_file = f.name
        
        try:
            config.set("auth", "password_file", password_file)
            handler = AuthHandler(config)
            assert handler.auth_type == "basic"
            assert handler.auth_data["username"] == "testuser"
            assert handler.auth_data["password"] == "testpass"
        finally:
            os.unlink(password_file)
    
    def test_init_bearer_auth(self):
        """Test initializing with bearer token"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "bearer")
        config.set("auth", "token", "test_token_123")
        
        handler = AuthHandler(config)
        assert handler.auth_type == "bearer"
        assert handler.auth_data["token"] == "test_token_123"
    
    def test_init_bearer_auth_token_file(self):
        """Test bearer auth with token from file"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "bearer")
        
        # Create temporary token file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test_token_123")
            token_file = f.name
        
        try:
            config.set("auth", "token_file", token_file)
            handler = AuthHandler(config)
            assert handler.auth_type == "bearer"
            assert handler.auth_data["token"] == "test_token_123"
        finally:
            os.unlink(token_file)
    
    def test_init_apikey_auth(self):
        """Test initializing with API key"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "apikey")
        config.set("auth", "api_key", "test_api_key")
        config.set("auth", "api_key_header", "X-API-Key")
        
        handler = AuthHandler(config)
        assert handler.auth_type == "apikey"
        assert handler.auth_data["api_key"] == "test_api_key"
        assert handler.auth_data["header"] == "X-API-Key"
    
    def test_init_apikey_auth_default_header(self):
        """Test API key auth with default header"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "apikey")
        config.set("auth", "api_key", "test_api_key")
        
        handler = AuthHandler(config)
        assert handler.auth_type == "apikey"
        assert handler.auth_data["api_key"] == "test_api_key"
        assert handler.auth_data["header"] == "X-API-Key"  # Default
    
    def test_init_oauth2_auth(self):
        """Test initializing with OAuth2"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "oauth2")
        config.set("auth", "token", "test_access_token")
        config.set("auth", "auth_url", "https://auth.example.com/token")
        config.set("auth", "refresh_token", "test_refresh_token")
        
        handler = AuthHandler(config)
        assert handler.auth_type == "oauth2"
        assert handler.auth_data["token"] == "test_access_token"
        assert handler.auth_data["auth_url"] == "https://auth.example.com/token"
        assert handler.auth_data["refresh_token"] == "test_refresh_token"
    
    def test_get_headers_basic(self):
        """Test getting headers for basic auth"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "basic")
        config.set("auth", "username", "testuser")
        config.set("auth", "password", "testpass")
        
        handler = AuthHandler(config)
        headers = handler.get_headers()
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        # Decode and verify
        encoded = headers["Authorization"].split(" ")[1]
        decoded = base64.b64decode(encoded).decode()
        assert decoded == "testuser:testpass"
    
    def test_get_headers_bearer(self):
        """Test getting headers for bearer auth"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "bearer")
        config.set("auth", "token", "test_token_123")
        
        handler = AuthHandler(config)
        headers = handler.get_headers()
        
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_token_123"
    
    def test_get_headers_apikey(self):
        """Test getting headers for API key auth"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "apikey")
        config.set("auth", "api_key", "test_api_key")
        config.set("auth", "api_key_header", "X-Custom-Key")
        
        handler = AuthHandler(config)
        headers = handler.get_headers()
        
        assert "X-Custom-Key" in headers
        assert headers["X-Custom-Key"] == "test_api_key"
    
    def test_get_headers_oauth2(self):
        """Test getting headers for OAuth2"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "oauth2")
        config.set("auth", "token", "test_access_token")
        
        handler = AuthHandler(config)
        headers = handler.get_headers()
        
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_access_token"
    
    def test_get_headers_no_auth(self):
        """Test getting headers when no auth configured"""
        config = configparser.ConfigParser()
        handler = AuthHandler(config)
        headers = handler.get_headers()
        assert headers == {}
    
    def test_refresh_token_oauth2_success(self):
        """Test refreshing OAuth2 token successfully"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "oauth2")
        config.set("auth", "auth_url", "https://auth.example.com/token")
        config.set("auth", "refresh_token", "test_refresh_token")
        config.set("auth", "token", "old_token")
        
        handler = AuthHandler(config)
        
        # Mock session and response
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "new_token"}
        mock_session.post.return_value = mock_response
        
        result = handler.refresh_token_if_needed(mock_session)

        assert result is True
        assert handler.auth_data["token"] == "new_token"
        mock_session.post.assert_called_once()

    def test_refresh_token_oauth2_verify_override(self):
        """When ``verify_ssl`` is explicitly False in config, the
        ``verify=False`` kwarg is forwarded to requests.post."""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "oauth2")
        config.set("auth", "auth_url", "https://auth.example.com/token")
        config.set("auth", "refresh_token", "rt")
        config.set("auth", "token", "old")
        config.set("auth", "verify_ssl", "false")  # explicit override

        handler = AuthHandler(config)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "new"}
        mock_session = Mock()
        mock_session.post.return_value = mock_response

        result = handler.refresh_token_if_needed(mock_session, verify=False)
        assert result is True

        # The ``verify`` kwarg was passed with the configured value.
        call_kwargs = mock_session.post.call_args.kwargs
        assert call_kwargs.get("verify") is False
    
    def test_refresh_token_oauth2_failure(self):
        """Test refreshing OAuth2 token with failure"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "oauth2")
        config.set("auth", "auth_url", "https://auth.example.com/token")
        config.set("auth", "refresh_token", "test_refresh_token")
        config.set("auth", "token", "old_token")
        
        handler = AuthHandler(config)
        
        # Mock session with error response
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 400
        mock_session.post.return_value = mock_response
        
        result = handler.refresh_token_if_needed(mock_session)
        
        assert result is False
        assert handler.auth_data["token"] == "old_token"  # Unchanged
    
    def test_refresh_token_oauth2_exception(self):
        """Test refreshing OAuth2 token with exception"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "oauth2")
        config.set("auth", "auth_url", "https://auth.example.com/token")
        config.set("auth", "refresh_token", "test_refresh_token")
        
        handler = AuthHandler(config)
        
        # Mock session that raises exception
        mock_session = Mock()
        mock_session.post.side_effect = Exception("Network error")
        
        result = handler.refresh_token_if_needed(mock_session)
        
        assert result is False
    
    def test_refresh_token_not_oauth2(self):
        """Test refresh_token_if_needed with non-OAuth2 auth"""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "basic")
        config.set("auth", "username", "testuser")
        config.set("auth", "password", "testpass")
        
        handler = AuthHandler(config)
        mock_session = Mock()
        
        result = handler.refresh_token_if_needed(mock_session)

        assert result is False
        mock_session.post.assert_not_called()

    def test_refresh_token_rotates_when_idp_returns_new_one(self):
        """P2.24: a refresh response with a new ``refresh_token`` field
        must update ``self.auth_data['refresh_token']`` so the next
        refresh cycle uses it. Without this, a single-use refresh token
        would lock the user out after one rotation.
        """
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "oauth2")
        config.set("auth", "client_id", "my-client")
        config.set("auth", "client_secret", "secret")
        config.set("auth", "refresh_token", "old-refresh-token")
        config.set("auth", "auth_url", "https://idp.example.com/oauth/token")
        config.set("auth", "verify_ssl", "true")

        handler = AuthHandler(config)
        assert handler.auth_type == "oauth2"
        assert handler.auth_data["refresh_token"] == "old-refresh-token"

        # The IdP returns a new refresh_token alongside the new access_token.
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "refresh_token": "rotated-refresh-token",
        }
        mock_response.raise_for_status = Mock()

        mock_session = Mock()
        mock_session.post.return_value = mock_response

        result = handler.refresh_token_if_needed(mock_session)
        assert result is True
        # Both fields updated.
        assert handler.auth_data["token"] == "new-access-token"
        assert handler.auth_data["refresh_token"] == "rotated-refresh-token"

    def test_refresh_token_keeps_old_when_idp_omits_new_one(self):
        """If the IdP does NOT return a new ``refresh_token``, the
        existing one is reused. Some IdPs (RFC 6749 §6) only return
        a new refresh token when it actually rotated."""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "oauth2")
        config.set("auth", "client_id", "my-client")
        config.set("auth", "client_secret", "secret")
        config.set("auth", "refresh_token", "stable-refresh-token")
        config.set("auth", "auth_url", "https://idp.example.com/oauth/token")
        config.set("auth", "verify_ssl", "true")

        handler = AuthHandler(config)

        # No refresh_token field in the response.
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-access-token",
        }
        mock_response.raise_for_status = Mock()

        mock_session = Mock()
        mock_session.post.return_value = mock_response

        handler.refresh_token_if_needed(mock_session)
        assert handler.auth_data["token"] == "new-access-token"
        # Old refresh_token preserved.
        assert handler.auth_data["refresh_token"] == "stable-refresh-token"

    def test_refresh_token_missing_access_token_field(self):
        """When the IdP returns 200 but no ``access_token`` field,
        the refresh fails gracefully."""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "oauth2")
        config.set("auth", "client_id", "id")
        config.set("auth", "client_secret", "secret")
        config.set("auth", "refresh_token", "old")
        config.set("auth", "auth_url", "https://idp.example.com/oauth/token")
        config.set("auth", "verify_ssl", "true")

        handler = AuthHandler(config)

        # 200 OK, but no access_token in the body.
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"refresh_token": "new-rt"}
        mock_response.raise_for_status = Mock()

        mock_session = Mock()
        mock_session.post.return_value = mock_response

        result = handler.refresh_token_if_needed(mock_session)
        assert result is False
        # The stale access token (None) is NOT overwritten.
        assert handler.auth_data["token"] is None

    def test_refresh_token_response_not_json(self):
        """When the IdP returns 200 but non-JSON, the refresh fails."""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "oauth2")
        config.set("auth", "client_id", "id")
        config.set("auth", "client_secret", "secret")
        config.set("auth", "refresh_token", "old")
        config.set("auth", "auth_url", "https://idp.example.com/oauth/token")
        config.set("auth", "verify_ssl", "true")

        handler = AuthHandler(config)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("not JSON")
        mock_response.raise_for_status = Mock()

        mock_session = Mock()
        mock_session.post.return_value = mock_response

        result = handler.refresh_token_if_needed(mock_session)
        assert result is False

    def test_oauth2_token_from_file(self):
        """Token can be loaded from a file via ``token_file`` config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".token", delete=False) as f:
            f.write("file-loaded-token\n")
            token_path = f.name
        try:
            config = configparser.ConfigParser()
            config.add_section("auth")
            config.set("auth", "type", "oauth2")
            config.set("auth", "client_id", "id")
            config.set("auth", "client_secret", "secret")
            config.set("auth", "token_file", token_path)
            config.set("auth", "auth_url", "https://idp.example.com/oauth/token")
            config.set("auth", "verify_ssl", "true")

            handler = AuthHandler(config)
            assert handler.auth_data["token"] == "file-loaded-token"
        finally:
            os.unlink(token_path)

    def test_apikey_header_name_default_and_explicit(self):
        """API key auth uses ``X-API-Key`` header by default; can be overridden."""
        # Default header name
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "apikey")
        config.set("auth", "api_key", "secret-key")

        handler = AuthHandler(config)
        headers = handler.get_headers()
        assert headers == {"X-API-Key": "secret-key"}

        # Custom header name
        config.set("auth", "api_key_header", "X-Custom-Auth")
        handler = AuthHandler(config)
        headers = handler.get_headers()
        assert headers == {"X-Custom-Auth": "secret-key"}

    def test_refresh_token_unprintable_body(self):
        """When ``response.text`` is a Mock that raises on str()
        conversion, the body_preview fallback must catch and use
        the ``<unprintable body>`` placeholder."""
        config = configparser.ConfigParser()
        config.add_section("auth")
        config.set("auth", "type", "oauth2")
        config.set("auth", "client_id", "id")
        config.set("auth", "client_secret", "secret")
        config.set("auth", "refresh_token", "old")
        config.set("auth", "auth_url", "https://idp.example.com/oauth/token")
        config.set("auth", "verify_ssl", "true")

        handler = AuthHandler(config)

        # Status code != 200 triggers the warning path with body_preview.
        mock_response = Mock()
        mock_response.status_code = 500
        # ``response.text`` is itself a Mock whose str() raises.
        type(mock_response).text = PropertyMock(
            side_effect=Exception("boom"),
        )
        mock_response.raise_for_status = Mock()

        mock_session = Mock()
        mock_session.post.return_value = mock_response

        # The ``str(response.text)[:200]`` raises Exception which is
        # caught — refresh returns False, no crash.
        result = handler.refresh_token_if_needed(mock_session)
        assert result is False

