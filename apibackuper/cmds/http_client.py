# -*- coding: utf-8 -*-
"""HTTP client for making API requests with authentication and rate limiting"""
import logging
from typing import Optional, Dict, Any

import requests

from ..auth import AuthHandler
from ..rate_limiter import RateLimiter


class HTTPClient:
    """HTTP client with authentication, rate limiting, and error handling"""
    
    def __init__(
        self,
        http_session: requests.Session,
        http_mode: str,
        flat_params: bool,
        verify_ssl: bool,
        connect_timeout: int,
        read_timeout: int,
        allow_redirects: bool,
        default_delay: int,
        logfile: str,
        auth_handler: Optional[AuthHandler] = None,
        rate_limiter: Optional[RateLimiter] = None
    ) -> None:
        """Initialize HTTP client"""
        self.http = http_session
        self.http_mode = http_mode
        self.flat_params = flat_params
        self.verify_ssl = verify_ssl
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.allow_redirects = allow_redirects
        self.default_delay = default_delay
        self.logfile = logfile
        self.auth_handler = auth_handler
        self.rate_limiter = rate_limiter
    
    def request(
        self,
        url: str,
        headers: Optional[Dict[str, str]],
        params: Dict[str, Any],
        flatten: Optional[Dict[str, str]] = None
    ) -> requests.Response:
        """Single http/https request with authentication and rate limiting"""
        try:
            # Apply rate limiting
            if self.rate_limiter:
                self.rate_limiter.wait_if_needed()
            
            # Merge auth headers
            if self.auth_handler:
                auth_headers = self.auth_handler.get_headers()
                if headers:
                    headers.update(auth_headers)
                else:
                    headers = auth_headers
            
            # Prepare request kwargs
            request_kwargs = {
                "verify": self.verify_ssl,
                "timeout": (self.connect_timeout, self.read_timeout),
                "allow_redirects": self.allow_redirects
            }
            
            if self.http_mode == "GET":
                if self.flat_params and len(params.keys()) > 0:
                    s = []
                    for key, value in flatten.items():
                        s.append("%s=%s" %
                                 (key, value.replace("'", '"').replace("True", "true")))
                    logging.info("url: %s" % (url + "?" + "&".join(s)))
                    if headers:
                        request_kwargs["headers"] = headers
                        response = self.http.get(url + "?" + "&".join(s), **request_kwargs)
                    else:
                        response = self.http.get(url + "?" + "&".join(s), **request_kwargs)
                else:
                    logging.info("url: %s, params: %s" % (url, str(params)))
                    if headers:
                        request_kwargs["headers"] = headers
                    request_kwargs["params"] = params
                    response = self.http.get(url, **request_kwargs)
            else:
                logging.debug("Request %s, params %s, headers %s" %
                              (url, str(params), str(headers)))
                if headers:
                    request_kwargs["headers"] = headers
                request_kwargs["json"] = params
                response = self.http.post(url, **request_kwargs)
            
            # Handle OAuth2 token refresh if needed
            if response.status_code == 401 and self.auth_handler and self.auth_handler.auth_type == "oauth2":
                if self.auth_handler.refresh_token_if_needed(self.http):
                    # Retry request with new token
                    auth_headers = self.auth_handler.get_headers()
                    if headers:
                        headers.update(auth_headers)
                    else:
                        headers = auth_headers
                    request_kwargs["headers"] = headers
                    if self.http_mode == "GET":
                        response = self.http.get(url, params=params, **request_kwargs)
                    else:
                        response = self.http.post(url, json=params, **request_kwargs)
            
            return response
        except requests.exceptions.Timeout as e:
            timeout_info = f"Connect timeout: {self.connect_timeout}s, Read timeout: {self.read_timeout}s"
            error_msg = (
                f"Request timeout while connecting to {url}\n"
                f"  Current timeout settings: {timeout_info}\n"
                f"  Error details: {str(e)}\n"
                f"  Suggestions:\n"
                f"    - Increase timeout values in [request] section:\n"
                f"      connect_timeout = {self.connect_timeout * 2}\n"
                f"      read_timeout = {self.read_timeout * 2}\n"
                f"    - Check network connectivity and API server status\n"
                f"    - Verify the URL is correct and accessible"
            )
            logging.error(f"Request timeout for URL {url}: {e}")
            raise RuntimeError(error_msg) from e
        except requests.exceptions.SSLError as e:
            error_msg = (
                f"SSL certificate verification failed for {url}\n"
                f"  Error details: {str(e)}\n"
                f"  Suggestions:\n"
                f"    - If this is a trusted server, disable SSL verification in [request] section:\n"
                f"      verify_ssl = False\n"
                f"    - Or provide a path to a trusted certificate bundle:\n"
                f"      verify_ssl = /path/to/certificate.pem\n"
                f"    - Update your system's certificate store\n"
                f"    - Check if the server's certificate has expired"
            )
            logging.error(f"SSL error for URL {url}: {e}")
            raise RuntimeError(error_msg) from e
        except requests.exceptions.ConnectionError as e:
            error_msg = (
                f"Failed to connect to {url}\n"
                f"  Error details: {str(e)}\n"
                f"  Suggestions:\n"
                f"    - Check your internet connection\n"
                f"    - Verify the URL is correct: {url}\n"
                f"    - Check if the API server is running and accessible\n"
                f"    - If using a proxy, verify proxy settings in [request] section\n"
                f"    - Check firewall settings"
            )
            logging.error(f"Connection error for URL {url}: {e}")
            raise RuntimeError(error_msg) from e
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if hasattr(e, 'response') and e.response else "unknown"
            error_msg = (
                f"HTTP error {status_code} for {url}\n"
                f"  Error details: {str(e)}\n"
            )
            if hasattr(e, 'response') and e.response:
                error_msg += f"  Response status: {e.response.status_code}\n"
                if e.response.status_code == 401:
                    error_msg += (
                        f"  Suggestions:\n"
                        f"    - Check authentication credentials in [auth] section\n"
                        f"    - Verify API key or token is valid and not expired\n"
                        f"    - Check if authentication type matches API requirements"
                    )
                elif e.response.status_code == 403:
                    error_msg += (
                        f"  Suggestions:\n"
                        f"    - Check if your account has permission to access this resource\n"
                        f"    - Verify API key has required permissions\n"
                        f"    - Check rate limiting or quota restrictions"
                    )
                elif e.response.status_code == 404:
                    error_msg += (
                        f"  Suggestions:\n"
                        f"    - Verify the URL is correct: {url}\n"
                        f"    - Check if the API endpoint exists\n"
                        f"    - Review API documentation for correct endpoint path"
                    )
                elif e.response.status_code == 429:
                    error_msg += (
                        f"  Suggestions:\n"
                        f"    - You are being rate limited. Wait before retrying\n"
                        f"    - Configure rate limiting in [rate_limit] section\n"
                        f"    - Increase delays between requests in [project] section:\n"
                        f"      default_delay = {self.default_delay * 2}"
                    )
                elif e.response.status_code >= 500:
                    error_msg += (
                        f"  Suggestions:\n"
                        f"    - This is a server error. The API may be temporarily unavailable\n"
                        f"    - Wait a few minutes and try again\n"
                        f"    - Check API status page if available\n"
                        f"    - Increase retry settings in [project] section"
                    )
            logging.error(f"HTTP error for URL {url}: {e}")
            raise RuntimeError(error_msg) from e
        except requests.exceptions.RequestException as e:
            error_msg = (
                f"Request failed for {url}\n"
                f"  Error details: {str(e)}\n"
                f"  Suggestions:\n"
                f"    - Check network connectivity\n"
                f"    - Verify URL and request parameters\n"
                f"    - Review configuration settings\n"
                f"    - Check logs for more details: {self.logfile}"
            )
            logging.error(f"Request error for URL {url}: {e}")
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = (
                f"Unexpected error while requesting {url}\n"
                f"  Error details: {str(e)}\n"
                f"  Error type: {type(e).__name__}\n"
                f"  Suggestions:\n"
                f"    - Check logs for more details: {self.logfile}\n"
                f"    - Verify configuration is correct\n"
                f"    - Try running with --verbose flag for more information"
            )
            logging.error(f"Unexpected error in request to {url}: {e}", exc_info=True)
            raise RuntimeError(error_msg) from e

