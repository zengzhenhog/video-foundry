from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    step: str | None = None
    retryable: bool = False
    suggested_correction: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AppError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        step: str | None = None,
        retryable: bool = False,
        suggested_correction: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = ErrorDetail(
            code=code,
            message=message,
            step=step,
            retryable=retryable,
            suggested_correction=suggested_correction,
            details=details or {},
        )

    def to_response(self) -> dict[str, Any]:
        return ErrorResponse(error=self.detail).model_dump(mode="json")
