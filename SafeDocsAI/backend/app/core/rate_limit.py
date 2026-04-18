"""
Simple in-memory rate limiting for API endpoints.
For production, consider using Redis with slowapi or fastapi-limiter.
"""

import time
from functools import wraps
from typing import Optional
from fastapi import HTTPException, Request
from collections import defaultdict


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, requests: int = 100, window: int = 60):
        """
        Args:
            requests: Maximum number of requests allowed
            window: Time window in seconds
        """
        self.requests = requests
        self.window = window
        self.clients: dict[str, list[float]] = defaultdict(list)
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request from client is allowed."""
        now = time.time()
        window_start = now - self.window
        
        # Get client's recent requests
        client_requests = self.clients[client_id]
        
        # Remove old requests outside the window
        client_requests[:] = [t for t in client_requests if t > window_start]
        
        # Check if under limit
        if len(client_requests) < self.requests:
            client_requests.append(now)
            return True
        
        return False
    
    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for client."""
        now = time.time()
        window_start = now - self.window
        client_requests = self.clients[client_id]
        client_requests[:] = [t for t in client_requests if t > window_start]
        return max(0, self.requests - len(client_requests))
    
    def get_retry_after(self, client_id: str) -> int:
        """Get seconds until next request is allowed."""
        client_requests = self.clients[client_id]
        if not client_requests:
            return 0
        oldest = min(client_requests)
        return max(0, int(oldest + self.window - time.time()))


# Global rate limiters
auth_limiter = RateLimiter(requests=10, window=60)  # 10 auth attempts per minute
chat_limiter = RateLimiter(requests=30, window=60)  # 30 chat requests per minute
api_limiter = RateLimiter(requests=100, window=60)  # 100 general API requests per minute


def get_client_id(request: Request) -> str:
    """Get client identifier from request."""
    # Try to get from X-Forwarded-For header (for proxied requests)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    # Fall back to direct client IP
    if request.client:
        return request.client.host
    
    return "unknown"


def rate_limit(limiter: RateLimiter, error_message: Optional[str] = None):
    """
    Decorator for rate limiting FastAPI endpoints.
    
    Usage:
        @app.get("/api/some-endpoint")
        @rate_limit(chat_limiter)
        async def my_endpoint():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find request in args/kwargs
            request: Optional[Request] = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                for value in kwargs.values():
                    if isinstance(value, Request):
                        request = value
                        break
            
            if request:
                client_id = get_client_id(request)
                if not limiter.is_allowed(client_id):
                    raise HTTPException(
                        status_code=429,
                        detail=error_message or "Rate limit exceeded",
                        headers={"Retry-After": str(limiter.get_retry_after(client_id))}
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


async def check_rate_limit(request: Request, limiter: RateLimiter) -> None:
    """
    Check rate limit for a request.
    Raises HTTPException if limit exceeded.
    """
    client_id = get_client_id(request)
    if not limiter.is_allowed(client_id):
        raise HTTPException(
            status_code=429,
            detail="Too many requests",
            headers={
                "Retry-After": str(limiter.get_retry_after(client_id)),
                "X-RateLimit-Limit": str(limiter.requests),
                "X-RateLimit-Remaining": str(limiter.get_remaining(client_id)),
            }
        )
