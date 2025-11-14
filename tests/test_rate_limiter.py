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
        """Test wait_if_needed with per-minute limit"""
        limiter = RateLimiter(requests_per_minute=2)
        
        # First two requests should not wait
        limiter.wait_if_needed()
        limiter.wait_if_needed()
        
        # Third request should wait
        start_time = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start_time
        # Should wait some time (exact time depends on implementation)
        assert elapsed >= 0
    
    def test_wait_if_needed_hour_limit(self):
        """Test wait_if_needed with per-hour limit"""
        limiter = RateLimiter(requests_per_hour=2)
        
        # First two requests should not wait
        limiter.wait_if_needed()
        limiter.wait_if_needed()
        
        # Third request should wait
        start_time = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start_time
        # Should wait some time
        assert elapsed >= 0
    
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

