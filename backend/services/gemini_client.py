"""Shared Google Gen AI client construction and error classification.

Centralised here so no other module reads the API key directly and no error
message or log line can ever include it.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from google import genai
from google.genai import types

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Status codes worth retrying: rate limits and transient server failures.
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Query-string material that could carry a credential into a log line.
_KEY_PARAM = re.compile(r"(?i)([?&](?:key|api_key|apikey|access_token)=)[^&\s]+")


class GeminiNotConfiguredError(RuntimeError):
    """Raised when GEMINI_API_KEY has not been configured."""


class GeminiRequestError(RuntimeError):
    """Raised when a Gemini request cannot be completed.

    ``message`` is safe to show a user; ``detail`` carries the HTTP status and
    a redacted API message for logs and API diagnostics.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        diagnostic: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.diagnostic = diagnostic

    @property
    def detail(self) -> str | None:
        """Short, secret-free diagnostic string for API responses."""
        if not self.code:
            return self.diagnostic
        return f"gemini {self.code}: {self.diagnostic}" if self.diagnostic else f"gemini {self.code}"


def create_client(
    api_key: str | None = None, *, timeout_seconds: int | None = None
) -> genai.Client:
    """Build a Gemini client, or raise if no key is configured."""
    key = (api_key if api_key is not None else settings.gemini_api_key).strip()
    if not key:
        raise GeminiNotConfiguredError(
            "GEMINI_API_KEY is not configured. Add it to the .env file in the "
            "project root and restart the application."
        )
    seconds = settings.gemini_timeout_seconds if timeout_seconds is None else timeout_seconds
    timeout_ms = max(5, seconds) * 1000
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


def status_label(exc: Exception) -> str | None:
    """The API status name (``INVALID_ARGUMENT``, ``NOT_FOUND``, ...)."""
    label = getattr(exc, "status", None)
    return label if isinstance(label, str) and label else None


def is_timeout(exc: Exception) -> bool:
    """Whether the request failed because it exceeded the configured timeout."""
    return isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower()


def is_retryable(exc: Exception) -> bool:
    """Whether retrying the same request could plausibly succeed.

    Timeouts are deliberately excluded: the client timeout is already long, and
    retrying would double the time a supervisor waits for an answer.
    """
    return status_code(exc) in _RETRYABLE_STATUS_CODES


def error_code(exc: Exception) -> str:
    """Compact ``code STATUS`` string for logs and API diagnostics."""
    code = status_code(exc)
    label = status_label(exc)
    if code is not None and label:
        return f"{code} {label}"
    if code is not None:
        return str(code)
    return type(exc).__name__


def redact(text: str) -> str:
    """Remove anything that looks like a credential from ``text``."""
    if not text:
        return ""
    cleaned = text.replace(settings.gemini_api_key.strip(), "***") if settings.gemini_api_key else text
    cleaned = _KEY_PARAM.sub(r"\1***", cleaned)
    return " ".join(cleaned.split())


def safe_message(exc: Exception) -> str:
    """The SDK's own error message, redacted and truncated for logging."""
    raw = getattr(exc, "message", None) or str(exc) or type(exc).__name__
    return redact(str(raw))[:300]


def describe_error(exc: Exception) -> str:
    """A short, user-facing explanation of a Gemini failure.

    Each failure category gets its own wording so a rejected request setting is
    never reported as a bad API key.
    """
    code = status_code(exc)
    if is_timeout(exc):
        return (
            "The AI service took too long to respond. Please try again, or make "
            "the question more specific."
        )
    if code == 400:
        return (
            "The AI service rejected the request as invalid. This is a request "
            "or model-setting problem, not an API key problem. Please contact "
            "the administrator."
        )
    if code in (401, 403):
        return (
            "The Gemini API rejected the credentials. Check GEMINI_API_KEY in "
            "the .env file and restart the application."
        )
    if code == 404:
        return (
            "The configured Gemini model is not available for this API key. "
            "Check GEMINI_MODEL in the .env file."
        )
    if code == 429:
        return "The Gemini API rate limit was reached. Please try again shortly."
    if code is not None and code >= 500:
        return "The Gemini service is temporarily unavailable. Please try again."
    return "The AI service request failed. Please try again."


# --- generation model availability -----------------------------------------

# The status endpoint must distinguish "a key exists" from "the configured
# model actually works". Listing models is the cheapest reliable probe, but it
# is still a network round trip, so results are cached and the probe uses a
# short timeout of its own.

MODEL_STATE_READY = "ready"
MODEL_STATE_NOT_CONFIGURED = "not_configured"
MODEL_STATE_UNAVAILABLE = "unavailable"
MODEL_STATE_UNAUTHORIZED = "unauthorized"
MODEL_STATE_UNKNOWN = "unknown"

_MODEL_PREFIX = "models/"
_PROBE_TIMEOUT_SECONDS = 10
_UNKNOWN_RETRY_SECONDS = 60
_UNAVAILABLE_DETAIL = (
    "{model} is not enabled for this API key. Check GEMINI_MODEL in the .env file."
)

_lock = threading.Lock()
_cache: tuple[float, "ModelAvailability"] | None = None


@dataclass(frozen=True, slots=True)
class ModelAvailability:
    """Result of probing whether the configured generation model is usable."""

    state: str
    available: bool | None
    detail: str | None = None
    checked_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_status": self.state,
            "model_available": self.available,
            "model_detail": self.detail,
            "model_checked_at": self.checked_at,
        }


def _normalise_model_name(name: str) -> str:
    name = (name or "").strip()
    return name[len(_MODEL_PREFIX) :] if name.startswith(_MODEL_PREFIX) else name


def _ttl_for(state: str) -> float:
    if state == MODEL_STATE_UNKNOWN:
        # A network blip should not look permanent for the whole TTL.
        return min(_UNKNOWN_RETRY_SECONDS, max(30, settings.gemini_model_check_ttl_seconds))
    return max(30, settings.gemini_model_check_ttl_seconds)


def check_generation_model(*, force: bool = False) -> ModelAvailability:
    """Report whether ``GEMINI_MODEL`` is usable with the configured key.

    Cached for ``GEMINI_MODEL_CHECK_TTL_SECONDS`` so dashboard refreshes do not
    produce a Gemini request each time. Never raises and never exposes the key.
    """
    global _cache

    if not settings.is_gemini_configured:
        return ModelAvailability(
            state=MODEL_STATE_NOT_CONFIGURED,
            available=False,
            detail="GEMINI_API_KEY is not set.",
        )

    now = time.monotonic()
    with _lock:
        if not force and _cache is not None and now < _cache[0]:
            return _cache[1]
        result = _probe_generation_model()
        _cache = (now + _ttl_for(result.state), result)
        return result


def reset_model_availability_cache() -> None:
    """Forget the cached probe (tests, or after changing the model at runtime)."""
    global _cache
    with _lock:
        _cache = None


def _probe_generation_model() -> ModelAvailability:
    """List models once and look for the configured generation model."""
    model = _normalise_model_name(settings.gemini_model)
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    try:
        client = create_client(
            timeout_seconds=min(_PROBE_TIMEOUT_SECONDS, max(5, settings.gemini_timeout_seconds))
        )
        match = None
        for candidate in client.models.list():
            if _normalise_model_name(str(getattr(candidate, "name", ""))) == model:
                match = candidate
                break
    except GeminiNotConfiguredError:
        return ModelAvailability(MODEL_STATE_NOT_CONFIGURED, False, "GEMINI_API_KEY is not set.")
    except Exception as exc:  # noqa: BLE001 - status must never fail
        code = status_code(exc)
        message = safe_message(exc)
        if code in (401, 403) or (code == 400 and "api key" in message.lower()):
            logger.warning("Gemini rejected the API key: %s", error_code(exc))
            return ModelAvailability(
                state=MODEL_STATE_UNAUTHORIZED,
                available=False,
                detail="Gemini rejected GEMINI_API_KEY. Check the key in the .env file.",
                checked_at=checked_at,
            )
        logger.warning(
            "Could not verify model %s: %s | %s", model, error_code(exc), message
        )
        return ModelAvailability(
            state=MODEL_STATE_UNKNOWN,
            available=None,
            detail=f"Could not verify the model ({error_code(exc)}).",
            checked_at=checked_at,
        )

    if match is None:
        return ModelAvailability(
            state=MODEL_STATE_UNAVAILABLE,
            available=False,
            detail=_UNAVAILABLE_DETAIL.format(model=model),
            checked_at=checked_at,
        )

    actions = getattr(match, "supported_actions", None) or []
    if actions and "generateContent" not in actions:
        return ModelAvailability(
            state=MODEL_STATE_UNAVAILABLE,
            available=False,
            detail=f"{model} is listed but does not support generateContent.",
            checked_at=checked_at,
        )

    return ModelAvailability(
        state=MODEL_STATE_READY, available=True, checked_at=checked_at
    )
