from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import threading
import time
from typing import TypeVar

from video_foundry.shared.errors import AppError


T = TypeVar("T")


@dataclass(frozen=True)
class ProviderRetryPolicy:
    max_attempts: int = 3
    base_delay_sec: float = 0.05
    backoff_multiplier: float = 2.0

    def delay_for_attempt(self, attempt: int) -> float:
        return self.base_delay_sec * (self.backoff_multiplier ** max(0, attempt - 1))


class ProviderRateLimiter:
    def __init__(
        self,
        *,
        max_calls: int,
        window_sec: float,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be at least 1.")
        if window_sec <= 0:
            raise ValueError("window_sec must be positive.")
        self.max_calls = max_calls
        self.window_sec = window_sec
        self._clock = clock or time.monotonic
        self._calls: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, provider_name: str, operation: str) -> None:
        bucket = f"{provider_name}:{operation}"
        now = self._clock()
        with self._lock:
            calls = [timestamp for timestamp in self._calls.get(bucket, []) if now - timestamp < self.window_sec]
            if len(calls) >= self.max_calls:
                raise AppError(
                    code="provider_rate_limited",
                    message="Provider rate limit reached.",
                    status_code=429,
                    step=operation,
                    retryable=True,
                    suggested_correction="Wait for the rate limit window to reset, then retry.",
                    details={
                        "provider": provider_name,
                        "operation": operation,
                        "max_calls": self.max_calls,
                        "window_sec": self.window_sec,
                    },
                )
            calls.append(now)
            self._calls[bucket] = calls


def run_provider_call(
    call: Callable[[], T],
    *,
    provider_name: str,
    operation: str,
    step: str,
    policy: ProviderRetryPolicy | None = None,
    limiter: ProviderRateLimiter | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> T:
    retry_policy = policy or ProviderRetryPolicy()
    sleep = sleeper or time.sleep
    last_error: AppError | Exception | None = None

    for attempt in range(1, retry_policy.max_attempts + 1):
        if limiter is not None:
            limiter.check(provider_name, operation)
        try:
            return call()
        except AppError as exc:
            last_error = exc
            if not exc.detail.retryable or attempt >= retry_policy.max_attempts:
                raise _provider_failure(
                    provider_name=provider_name,
                    operation=operation,
                    step=step,
                    attempts=attempt,
                    reason=exc.detail.message,
                    last_code=exc.detail.code,
                ) from exc
        except Exception as exc:
            last_error = exc
            if attempt >= retry_policy.max_attempts:
                raise _provider_failure(
                    provider_name=provider_name,
                    operation=operation,
                    step=step,
                    attempts=attempt,
                    reason="Provider request failed.",
                    exception_type=type(exc).__name__,
                ) from exc

        sleep(retry_policy.delay_for_attempt(attempt))

    raise _provider_failure(
        provider_name=provider_name,
        operation=operation,
        step=step,
        attempts=retry_policy.max_attempts,
        reason="Provider request failed.",
        exception_type=type(last_error).__name__ if last_error else None,
    )


def provider_name_for(provider: object) -> str:
    return str(getattr(provider, "provider_name", provider.__class__.__name__))


def _provider_failure(
    *,
    provider_name: str,
    operation: str,
    step: str,
    attempts: int,
    reason: str,
    last_code: str | None = None,
    exception_type: str | None = None,
) -> AppError:
    details: dict[str, object] = {
        "provider": provider_name,
        "operation": operation,
        "attempts": attempts,
    }
    if last_code:
        details["last_code"] = last_code
    if exception_type:
        details["exception_type"] = exception_type
    return AppError(
        code="provider_call_failed",
        message=reason,
        status_code=502,
        step=step,
        retryable=True,
        suggested_correction="Retry later or switch to another provider.",
        details=details,
    )
