"""Tests for HTTP client"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import requests
from apibackuper.cmds.http_client import HTTPClient
from apibackuper.auth import AuthHandler
from apibackuper.rate_limiter import RateLimiter


class TestHTTPClient:
    """Tests for HTTPClient class"""
    
    def test_init(self, mock_requests_session):
        """Test initializing HTTP client"""
        client = HTTPClient(
            http_session=mock_requests_session,
            http_mode="GET",
            flat_params=False,
            verify_ssl=True,
            connect_timeout=10,
            read_timeout=30,
            allow_redirects=True,
            default_delay=0.5,
            logfile="test.log"
        )
        assert client.http_mode == "GET"
        assert client.verify_ssl is True
        assert client.connect_timeout == 10
        assert client.read_timeout == 30
    
    def test_request_get(self, mock_requests_session):
        """Test GET request"""
        client = HTTPClient(
            http_session=mock_requests_session,
            http_mode="GET",
            flat_params=False,
            verify_ssl=True,
            connect_timeout=10,
            read_timeout=30,
            allow_redirects=True,
            default_delay=0.5,
            logfile="test.log"
        )
        
        response = client.request(
            url="https://api.example.com/data",
            headers=None,
            params={"page": 1, "size": 10}
        )
        
        assert response.status_code == 200
        mock_requests_session.get.assert_called_once()
        call_kwargs = mock_requests_session.get.call_args[1]
        assert call_kwargs["params"] == {"page": 1, "size": 10}
    
    def test_request_post(self, mock_requests_session):
        """Test POST request"""
        client = HTTPClient(
            http_session=mock_requests_session,
            http_mode="POST",
            flat_params=False,
            verify_ssl=True,
            connect_timeout=10,
            read_timeout=30,
            allow_redirects=True,
            default_delay=0.5,
            logfile="test.log"
        )
        
        response = client.request(
            url="https://api.example.com/data",
            headers=None,
            params={"page": 1, "size": 10}
        )
        
        assert response.status_code == 200
        mock_requests_session.post.assert_called_once()
        call_kwargs = mock_requests_session.post.call_args[1]
        assert call_kwargs["json"] == {"page": 1, "size": 10}
    
    def test_request_with_auth(self, mock_requests_session):
        """Test request with authentication"""
        mock_auth = Mock(spec=AuthHandler)
        mock_auth.get_headers.return_value = {"Authorization": "Bearer token123"}
        
        client = HTTPClient(
            http_session=mock_requests_session,
            http_mode="GET",
            flat_params=False,
            verify_ssl=True,
            connect_timeout=10,
            read_timeout=30,
            allow_redirects=True,
            default_delay=0.5,
            logfile="test.log",
            auth_handler=mock_auth
        )
        
        response = client.request(
            url="https://api.example.com/data",
            headers=None,
            params={"page": 1}
        )
        
        assert response.status_code == 200
        call_kwargs = mock_requests_session.get.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer token123"
    
    def test_request_with_rate_limiter(self, mock_requests_session):
        """Test request with rate limiter"""
        mock_rate_limiter = Mock(spec=RateLimiter)
        mock_rate_limiter.wait_if_needed.return_value = None
        
        client = HTTPClient(
            http_session=mock_requests_session,
            http_mode="GET",
            flat_params=False,
            verify_ssl=True,
            connect_timeout=10,
            read_timeout=30,
            allow_redirects=True,
            default_delay=0.5,
            logfile="test.log",
            rate_limiter=mock_rate_limiter
        )
        
        response = client.request(
            url="https://api.example.com/data",
            headers=None,
            params={"page": 1}
        )
        
        assert response.status_code == 200
        mock_rate_limiter.wait_if_needed.assert_called_once()
    
    def test_request_oauth2_refresh(self, mock_requests_session):
        """Test OAuth2 token refresh on 401"""
        mock_auth = Mock(spec=AuthHandler)
        mock_auth.auth_type = "oauth2"
        mock_auth.get_headers.return_value = {"Authorization": "Bearer token123"}
        mock_auth.refresh_token_if_needed.return_value = True
        
        # First response is 401, second is 200
        response_401 = Mock()
        response_401.status_code = 401
        response_200 = Mock()
        response_200.status_code = 200
        response_200.json.return_value = {"data": "test"}
        
        mock_requests_session.get.side_effect = [response_401, response_200]
        
        client = HTTPClient(
            http_session=mock_requests_session,
            http_mode="GET",
            flat_params=False,
            verify_ssl=True,
            connect_timeout=10,
            read_timeout=30,
            allow_redirects=True,
            default_delay=0.5,
            logfile="test.log",
            auth_handler=mock_auth
        )
        
        response = client.request(
            url="https://api.example.com/data",
            headers=None,
            params={"page": 1}
        )
        
        assert response.status_code == 200
        assert mock_requests_session.get.call_count == 2
        mock_auth.refresh_token_if_needed.assert_called_once()
    
    def test_request_timeout_error(self, mock_requests_session):
        """Test handling timeout error"""
        mock_requests_session.get.side_effect = requests.exceptions.Timeout("Connection timeout")
        
        client = HTTPClient(
            http_session=mock_requests_session,
            http_mode="GET",
            flat_params=False,
            verify_ssl=True,
            connect_timeout=10,
            read_timeout=30,
            allow_redirects=True,
            default_delay=0.5,
            logfile="test.log"
        )
        
        with pytest.raises(RuntimeError) as exc_info:
            client.request(
                url="https://api.example.com/data",
                headers=None,
                params={"page": 1}
            )
        
        assert "timeout" in str(exc_info.value).lower()
    
    def test_request_ssl_error(self, mock_requests_session):
        """Test handling SSL error"""
        mock_requests_session.get.side_effect = requests.exceptions.SSLError("SSL verification failed")
        
        client = HTTPClient(
            http_session=mock_requests_session,
            http_mode="GET",
            flat_params=False,
            verify_ssl=True,
            connect_timeout=10,
            read_timeout=30,
            allow_redirects=True,
            default_delay=0.5,
            logfile="test.log"
        )
        
        with pytest.raises(RuntimeError) as exc_info:
            client.request(
                url="https://api.example.com/data",
                headers=None,
                params={"page": 1}
            )
        
        assert "ssl" in str(exc_info.value).lower()
    
    def test_request_connection_error(self, mock_requests_session):
        """Test handling connection error"""
        mock_requests_session.get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        client = HTTPClient(
            http_session=mock_requests_session,
            http_mode="GET",
            flat_params=False,
            verify_ssl=True,
            connect_timeout=10,
            read_timeout=30,
            allow_redirects=True,
            default_delay=0.5,
            logfile="test.log"
        )
        
        with pytest.raises(RuntimeError) as exc_info:
            client.request(
                url="https://api.example.com/data",
                headers=None,
                params={"page": 1}
            )
        
        assert "connect" in str(exc_info.value).lower()
    
    def test_request_flat_params(self, mock_requests_session):
        """Test request with flat params"""
        client = HTTPClient(
            http_session=mock_requests_session,
            http_mode="GET",
            flat_params=True,
            verify_ssl=True,
            connect_timeout=10,
            read_timeout=30,
            allow_redirects=True,
            default_delay=0.5,
            logfile="test.log"
        )
        
        flatten = {"page": "1", "size": "10"}
        response = client.request(
            url="https://api.example.com/data",
            headers=None,
            params={},
            flatten=flatten
        )
        
        assert response.status_code == 200
        # Should append params to URL
        call_args = mock_requests_session.get.call_args[0]
        assert "?" in call_args[0]
        assert "page=1" in call_args[0]
        assert "size=10" in call_args[0]
    
    def test_request_with_custom_headers(self, mock_requests_session):
        """Test request with custom headers"""
        client = HTTPClient(
            http_session=mock_requests_session,
            http_mode="GET",
            flat_params=False,
            verify_ssl=True,
            connect_timeout=10,
            read_timeout=30,
            allow_redirects=True,
            default_delay=0.5,
            logfile="test.log"
        )
        
        custom_headers = {"X-Custom-Header": "custom-value"}
        response = client.request(
            url="https://api.example.com/data",
            headers=custom_headers,
            params={"page": 1}
        )
        
        assert response.status_code == 200
        call_kwargs = mock_requests_session.get.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["X-Custom-Header"] == "custom-value"
    
    def test_request_headers_merge_with_auth(self, mock_requests_session):
        """Test merging custom headers with auth headers"""
        mock_auth = Mock(spec=AuthHandler)
        mock_auth.get_headers.return_value = {"Authorization": "Bearer token123"}
        
        client = HTTPClient(
            http_session=mock_requests_session,
            http_mode="GET",
            flat_params=False,
            verify_ssl=True,
            connect_timeout=10,
            read_timeout=30,
            allow_redirects=True,
            default_delay=0.5,
            logfile="test.log",
            auth_handler=mock_auth
        )
        
        custom_headers = {"X-Custom-Header": "custom-value"}
        response = client.request(
            url="https://api.example.com/data",
            headers=custom_headers,
            params={"page": 1}
        )
        
        assert response.status_code == 200
        call_kwargs = mock_requests_session.get.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer token123"
        assert call_kwargs["headers"]["X-Custom-Header"] == "custom-value"

