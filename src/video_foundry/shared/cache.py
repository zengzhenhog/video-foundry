from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from video_foundry.shared.errors import AppError
from video_foundry.shared.schemas import SENSITIVE_CONFIG_KEY_FRAGMENTS


class FileCache:
    def __init__(self, root_dir: Path, *, namespace: str) -> None:
        self.root_dir = Path(root_dir)
        self.namespace = _safe_namespace(namespace)
        self.cache_dir = self.root_dir / self.namespace

    def get_json(self, key: str) -> dict[str, Any] | None:
        path = self._path_for_key(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AppError(
                code="cache_entry_invalid",
                message="Cache entry JSON is corrupted.",
                status_code=500,
                step="cache",
                retryable=True,
                suggested_correction="Clear the cache and retry the request.",
            ) from exc
        if not isinstance(data, dict):
            raise AppError(
                code="cache_entry_invalid",
                message="Cache entry must contain an object.",
                status_code=500,
                step="cache",
                retryable=True,
                suggested_correction="Clear the cache and retry the request.",
            )
        return data

    def set_json(self, key: str, payload: dict[str, Any]) -> Path:
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    def clear(self) -> int:
        if not self.cache_dir.exists():
            return 0
        removed = sum(1 for item in self.cache_dir.rglob("*") if item.is_file())
        shutil.rmtree(self.cache_dir)
        return removed

    def _path_for_key(self, key: str) -> Path:
        safe_key = _safe_key(key)
        return self.cache_dir / f"{safe_key}.json"


def build_cache_key(namespace: str, payload: dict[str, Any]) -> str:
    safe_payload = _redact_sensitive_values(payload)
    encoded = json.dumps(
        {"namespace": namespace, "payload": safe_payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _redact_sensitive_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key).lower()
            if any(fragment in key_text for fragment in SENSITIVE_CONFIG_KEY_FRAGMENTS):
                redacted[str(key)] = "[redacted]"
            else:
                redacted[str(key)] = _redact_sensitive_values(nested)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive_values(item) for item in value]
    return value


def _safe_key(value: str) -> str:
    if len(value) == 64 and all(character in "0123456789abcdef" for character in value):
        return value
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_namespace(value: str) -> str:
    normalized = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)
    return normalized.strip("_") or "default"
