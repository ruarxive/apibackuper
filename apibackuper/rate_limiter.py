"""
Rate limiting for apibackuper
"""
import time
import logging
from typing import Optional
from collections import deque


class RateLimiter:
    """Simple token bucket rate limiter"""
    
    def __init__(self, requests_per_second: Optional[float] = None,
                 requests_per_minute: Optional[int] = None,
                 requests_per_hour: Optional[int] = None,
                 burst_size: int = 5):
        """
        Initialize rate limiter
        
        Args:
            requests_per_second: Max requests per second
            requests_per_minute: Max requests per minute
            requests_per_hour: Max requests per hour
            burst_size: Burst capacity
        """
        self.requests_per_second = requests_per_second
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size
        
        # Token bucket for per-second limiting
        self.tokens = float(burst_size) if requests_per_second else float('inf')
        self.last_update = time.time()
        self.rate = requests_per_second if requests_per_second else float('inf')
        
        # Sliding window for per-minute and per-hour limiting
        self.minute_requests = deque()
        self.hour_requests = deque()
        
        self.enabled = any([requests_per_second, requests_per_minute, requests_per_hour])
    
    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        if not self.enabled:
            return
        
        now = time.time()
        
        # Per-second rate limiting (token bucket)
        if self.requests_per_second:
            # Add tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(self.burst_size, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.rate
                if wait_time > 0:
                    logging.debug(f"Rate limit: waiting {wait_time:.2f} seconds")
                    time.sleep(wait_time)
                    self.tokens = 0.0
                else:
                    self.tokens = 0.0
            else:
                self.tokens -= 1.0
        
        # Per-minute rate limiting
        if self.requests_per_minute:
            # Remove requests older than 1 minute
            while self.minute_requests and self.minute_requests[0] < now - 60:
                self.minute_requests.popleft()
            
            if len(self.minute_requests) >= self.requests_per_minute:
                wait_time = 60 - (now - self.minute_requests[0])
                if wait_time > 0:
                    logging.debug(f"Rate limit: waiting {wait_time:.2f} seconds (minute limit)")
                    time.sleep(wait_time)
                    # Clean up again after waiting
                    while self.minute_requests and self.minute_requests[0] < time.time() - 60:
                        self.minute_requests.popleft()
            
            self.minute_requests.append(time.time())
        
        # Per-hour rate limiting
        if self.requests_per_hour:
            # Remove requests older than 1 hour
            while self.hour_requests and self.hour_requests[0] < now - 3600:
                self.hour_requests.popleft()
            
            if len(self.hour_requests) >= self.requests_per_hour:
                wait_time = 3600 - (now - self.hour_requests[0])
                if wait_time > 0:
                    logging.warning(f"Rate limit: waiting {wait_time:.2f} seconds (hour limit)")
                    time.sleep(wait_time)
                    # Clean up again after waiting
                    while self.hour_requests and self.hour_requests[0] < time.time() - 3600:
                        self.hour_requests.popleft()
            
            self.hour_requests.append(time.time())

