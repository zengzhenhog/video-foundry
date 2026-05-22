from __future__ import annotations

from contextlib import contextmanager
import os
import threading
from collections.abc import Iterator

from video_foundry.shared.errors import AppError


class RenderConcurrencyLimiter:
    def __init__(self, max_concurrent: int = 1) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1.")
        self.max_concurrent = max_concurrent
        self._semaphore = threading.BoundedSemaphore(max_concurrent)
        self._lock = threading.Lock()
        self._active = 0

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._active

    @contextmanager
    def acquire(self, *, blocking: bool = True, timeout_sec: float | None = None) -> Iterator[None]:
        if timeout_sec is None:
            acquired = self._semaphore.acquire(blocking=blocking)
        else:
            acquired = self._semaphore.acquire(blocking=blocking, timeout=timeout_sec)
        if not acquired:
            raise AppError(
                code="render_concurrency_limit_reached",
                message="No render worker slot is currently available.",
                status_code=429,
                step="render_concurrency",
                retryable=True,
                suggested_correction="Wait for the active render to finish, then retry.",
                details={"max_concurrent": self.max_concurrent},
            )
        with self._lock:
            self._active += 1
        try:
            yield
        finally:
            with self._lock:
                self._active -= 1
            self._semaphore.release()


_GLOBAL_LIMITER: RenderConcurrencyLimiter | None = None
_GLOBAL_LOCK = threading.Lock()


def get_render_limiter() -> RenderConcurrencyLimiter:
    global _GLOBAL_LIMITER
    with _GLOBAL_LOCK:
        if _GLOBAL_LIMITER is None:
            raw_limit = os.environ.get("VIDEO_FOUNDRY_MAX_RENDER_JOBS", "1")
            try:
                limit = max(1, int(raw_limit))
            except ValueError:
                limit = 1
            _GLOBAL_LIMITER = RenderConcurrencyLimiter(limit)
        return _GLOBAL_LIMITER


def reset_render_limiter_for_tests(max_concurrent: int = 1) -> RenderConcurrencyLimiter:
    global _GLOBAL_LIMITER
    with _GLOBAL_LOCK:
        _GLOBAL_LIMITER = RenderConcurrencyLimiter(max_concurrent)
        return _GLOBAL_LIMITER
