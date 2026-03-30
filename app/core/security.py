"""Security layer: API key authentication and rate limiting."""

import time
from collections import defaultdict
from typing import Dict, List, Tuple

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security.api_key import APIKeyHeader

from app.core.config import get_settings

settings = get_settings()

api_key_header_scheme = APIKeyHeader(name=settings.api_key_header, auto_error=False)

# In-memory rate limiter: {client_ip: [(timestamp, count), ...]}
_rate_limit_store: Dict[str, List[float]] = defaultdict(list)


def verify_api_key(api_key: str = Security(api_key_header_scheme)) -> str:
    """Validate API key if keys are configured; skip if no keys are set (open access)."""
    configured_keys: List[str] = settings.api_keys
    if not configured_keys:
        # No API keys configured → open access (useful for development)
        return "open"
    if api_key not in configured_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key


def _get_client_ip(request: Request) -> str:
    """Extract real client IP, accounting for reverse proxy X-Forwarded-For headers."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may be a comma-separated list; the first is the original client
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def check_rate_limit(request: Request) -> None:
    """Sliding-window rate limiter based on client IP."""
    client_ip: str = _get_client_ip(request)
    now = time.time()
    window = settings.rate_limit_window_seconds
    limit = settings.rate_limit_requests

    # Prune old timestamps outside the window
    timestamps = _rate_limit_store[client_ip]
    _rate_limit_store[client_ip] = [t for t in timestamps if now - t < window]

    if len(_rate_limit_store[client_ip]) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limit} requests per {window}s",
        )

    _rate_limit_store[client_ip].append(now)


def get_rate_limit_info(client_ip: str) -> Tuple[int, int]:
    """Return (requests_made, requests_remaining) in the current window."""
    now = time.time()
    window = settings.rate_limit_window_seconds
    limit = settings.rate_limit_requests
    timestamps = [t for t in _rate_limit_store[client_ip] if now - t < window]
    made = len(timestamps)
    return made, max(0, limit - made)
