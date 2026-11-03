from collections import defaultdict, deque
import os
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

WINDOW_SECONDS = 60
MAX_ATTEMPTS = 10
_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def reset_rate_limits() -> None:
    with _lock:
        _attempts.clear()


def enforce_auth_rate_limit(request: Request) -> None:
    if os.getenv("TESTING") == "1":
        return
    client = request.client.host if request.client else "unknown"
    key = f"{client}:{request.url.path}"
    now = monotonic()
    with _lock:
        attempts = _attempts[key]
        while attempts and now - attempts[0] >= WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many authentication attempts. Try again shortly.",
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )
        attempts.append(now)
