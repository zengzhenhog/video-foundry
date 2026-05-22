from __future__ import annotations

from pathlib import Path

import pytest

from video_foundry.shared.cache import FileCache, build_cache_key
from video_foundry.shared.errors import AppError
from video_foundry.shared.provider_runtime import (
    ProviderRateLimiter,
    ProviderRetryPolicy,
    run_provider_call,
)


def test_file_cache_uses_hashed_keys_without_sensitive_values(tmp_path: Path) -> None:
    key = build_cache_key("provider", {"prompt": "hello", "api_key": "secret-value"})
    cache = FileCache(tmp_path / "cache", namespace="provider")

    path = cache.set_json(key, {"value": "cached"})

    assert "secret-value" not in str(path)
    assert cache.get_json(key) == {"value": "cached"}
    assert cache.clear() == 1
    assert cache.get_json(key) is None


def test_provider_call_retries_retryable_errors() -> None:
    attempts = 0

    def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise AppError(
                code="temporary_provider_error",
                message="Temporary failure.",
                status_code=502,
                step="provider",
                retryable=True,
            )
        return "ok"

    result = run_provider_call(
        flaky,
        provider_name="mock",
        operation="script_generation",
        step="script_generation",
        policy=ProviderRetryPolicy(max_attempts=2, base_delay_sec=0),
        sleeper=lambda _delay: None,
    )

    assert result == "ok"
    assert attempts == 2


def test_provider_rate_limiter_returns_structured_error() -> None:
    limiter = ProviderRateLimiter(max_calls=1, window_sec=60, clock=lambda: 100.0)
    limiter.check("mock", "voice_generation")

    with pytest.raises(AppError) as exc_info:
        limiter.check("mock", "voice_generation")

    assert exc_info.value.detail.code == "provider_rate_limited"
    assert exc_info.value.detail.details["provider"] == "mock"

