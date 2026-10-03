"""Tests for rate limiter"""
import time
import pytest
from unittest.mock import patch
from apibackuper.rate_limiter import RateLimiter


class TestRateLimiter:
    """Tests for RateLimiter class"""
    
    def test_init_no_limits(self):
        """Test initializing without limits"""
        limiter = RateLimiter()
        assert not limiter.enabled
        assert limiter.requests_per_second is None
        assert limiter.requests_per_minute is None
        assert limiter.requests_per_hour is None
    
    def test_init_with_second_limit(self):
        """Test initializing with per-second limit"""
        limiter = RateLimiter(requests_per_second=10.0)
        assert limiter.enabled
        assert limiter.requests_per_second == 10.0
        assert limiter.tokens == limiter.burst_size
    
    def test_init_with_minute_limit(self):
        """Test initializing with per-minute limit"""
        limiter = RateLimiter(requests_per_minute=60)
        assert limiter.enabled
        assert limiter.requests_per_minute == 60
        assert len(limiter.minute_requests) == 0
    
    def test_init_with_hour_limit(self):
        """Test initializing with per-hour limit"""
        limiter = RateLimiter(requests_per_hour=3600)
        assert limiter.enabled
        assert limiter.requests_per_hour == 3600
        assert len(limiter.hour_requests) == 0
    
    def test_init_with_all_limits(self):
        """Test initializing with all limits"""
        limiter = RateLimiter(
            requests_per_second=10.0,
            requests_per_minute=60,
            requests_per_hour=3600
        )
        assert limiter.enabled
        assert limiter.requests_per_second == 10.0
        assert limiter.requests_per_minute == 60
        assert limiter.requests_per_hour == 3600
    
    def test_wait_if_needed_disabled(self):
        """Test wait_if_needed when disabled"""
        limiter = RateLimiter()
        start_time = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start_time
        # Should not wait when disabled
        assert elapsed < 0.1
    
    def test_wait_if_needed_second_limit(self):
        """Test wait_if_needed with per-second limit"""
        limiter = RateLimiter(requests_per_second=2.0, burst_size=2)
        # First request should not wait
        start_time = time.time()
        limiter.wait_if_needed()
        elapsed1 = time.time() - start_time
        assert elapsed1 < 0.1
        
        # Consume all tokens
        limiter.wait_if_needed()
        
        # Next request should wait
        start_time = time.time()
        limiter.wait_if_needed()
        elapsed2 = time.time() - start_time
        # Should wait approximately 0.5 seconds (1/2 requests_per_second)
        assert elapsed2 >= 0.4
    
    def test_wait_if_needed_minute_limit(self):
        """Test wait_if_needed with per-minute limit.

        The historical version of this test ran for ~60 wall-clock seconds and
        hung pytest for that long. With ``time.sleep`` mocked we can verify
        the wait *would* have been triggered without actually sleeping.
        """
        limiter = RateLimiter(requests_per_minute=2)

        # Mock time.sleep so the test runs instantly.
        with patch('apibackuper.rate_limiter.time.sleep') as mock_sleep:
            limiter.wait_if_needed()
            limiter.wait_if_needed()
            limiter.wait_if_needed()
            assert mock_sleep.called, "expected time.sleep to be called"

    def test_wait_if_needed_hour_limit(self):
        """Test wait_if_needed with per-hour limit.

        Same fix as ``test_wait_if_needed_minute_limit``: mock ``time.sleep``
        so the test runs instantly instead of waiting ~3600 seconds.
        """
        limiter = RateLimiter(requests_per_hour=2)

        with patch('apibackuper.rate_limiter.time.sleep') as mock_sleep:
            limiter.wait_if_needed()
            limiter.wait_if_needed()
            limiter.wait_if_needed()
            assert mock_sleep.called, "expected time.sleep to be called"
    
    def test_token_bucket_refill(self):
        """Test that token bucket refills over time"""
        limiter = RateLimiter(requests_per_second=10.0, burst_size=5)
        
        # Consume all tokens
        for _ in range(5):
            limiter.wait_if_needed()
        
        # Wait a bit for tokens to refill
        time.sleep(0.2)
        
        # Should be able to make another request without long wait
        start_time = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start_time
        # Should not wait too long
        assert elapsed < 0.1
    
    def test_minute_window_cleanup(self):
        """Test that old requests are removed from minute window"""
        limiter = RateLimiter(requests_per_minute=10)
        
        # Add some requests
        for _ in range(5):
            limiter.wait_if_needed()
        
        assert len(limiter.minute_requests) == 5
        
        # Simulate time passing (mock time.time)
        with patch('time.time', return_value=time.time() + 70):
            limiter.wait_if_needed()
            # Old requests should be cleaned up
            assert len(limiter.minute_requests) <= 1
    
    def test_hour_window_cleanup(self):
        """Test that old requests are removed from hour window"""
        limiter = RateLimiter(requests_per_hour=10)

        # Add some requests
        for _ in range(5):
            limiter.wait_if_needed()

        assert len(limiter.hour_requests) == 5

        # Simulate time passing
        with patch('time.time', return_value=time.time() + 3700):
            limiter.wait_if_needed()
            # Old requests should be cleaned up
            assert len(limiter.hour_requests) <= 1

    def test_zero_per_second_does_not_divide_by_zero(self):
        """requests_per_second=0 must not crash the rate limiter."""
        limiter = RateLimiter(requests_per_second=0)
        # The constructor accepts 0 — the second_window is never
        # enabled, so the limiter falls back to no rate-limit at all.
        assert limiter.requests_per_second == 0
        # wait_if_needed must not raise (would have raised ZeroDivisionError
        # in the historical implementation).
        limiter.wait_if_needed()

    def test_zero_all_limits_disables_limiter(self):
        """All three limits at 0 = no rate limiting."""
        limiter = RateLimiter(
            requests_per_second=0,
            requests_per_minute=0,
            requests_per_hour=0,
        )
        # All three should be 0 — the limiter is effectively off.
        assert limiter.requests_per_second == 0
        assert limiter.requests_per_minute == 0
        assert limiter.requests_per_hour == 0
        # And it can be called many times without sleeping.
        for _ in range(20):
            limiter.wait_if_needed()

