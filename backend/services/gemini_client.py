"""Shared Google Gen AI client construction.

Centralised here so no other module reads the API key directly and no error
message or log line can ever include it.
"""

from __future__ import annotations

import logging
from typing import Any

from google import genai
from google.genai import types

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Status codes worth retrying: rate limits and transient server failures.
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class GeminiNotConfiguredError(RuntimeError):
    """Raised when GEMINI_API_KEY has not been configured."""


class GeminiRequestError(RuntimeError):
    """Raised when a Gemini request cannot be completed."""


def create_client(api_key: str | None = None) -> genai.Client:
    """Build a Gemini client, or raise if no key is configured."""
    key = (api_key if api_key is not None else settings.gemini_api_key).strip()
    if not key:
        raise GeminiNotConfiguredError(
            "GEMINI_API_KEY is not configured. Add it to the .env file in the "
            "project root and restart the application."
        )
    timeout_ms = max(5, settings.gemini_timeout_seconds) * 1000
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(timeout=timeout_ms),
    )


def status_code(exc: Exception) -> int | None:
    """Best-effort HTTP status code from a Gen AI SDK exception."""
    code: Any = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    try:
        return int(code)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def is_retryable(exc: Exception) -> bool:
    """Whether retrying the same request could plausibly succeed."""
    return status_code(exc) in _RETRYABLE_STATUS_CODES


def describe_error(exc: Exception) -> str:
    """A short, secret-free description of a Gemini failure."""
    code = status_code(exc)
    if code in (400, 401, 403):
        return (
            "The Gemini API rejected the request or key. Check GEMINI_API_KEY "
            "in the .env file."
        )
    if code == 404:
        return (
            "The configured Gemini model is not available for this key. Check "
            "GEMINI_MODEL and GEMINI_EMBEDDING_MODEL in .env."
        )
    if code == 429:
        return "The Gemini API rate limit was reached. Please try again shortly."
    if code is not None and code >= 500:
        return "The Gemini service is temporarily unavailable. Please try again."
    return "The AI service request failed. Please try again."
