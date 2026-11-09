"""Offline tests for the model-availability probe used by ``GET /api/status``.

The Gemini client is replaced with a fake, so these tests never touch the
network and never need an API key.
"""

from __future__ import annotations

import unittest
from unittest import mock

from backend.core.config import settings
from backend.services import gemini_client
from backend.services.gemini_client import (
    MODEL_STATE_NOT_CONFIGURED,
    MODEL_STATE_READY,
    MODEL_STATE_UNAUTHORIZED,
    MODEL_STATE_UNAVAILABLE,
    MODEL_STATE_UNKNOWN,
    check_generation_model,
    reset_model_availability_cache,
)


class ApiError(Exception):
    """Stand-in for a Google Gen AI SDK error."""

    def __init__(self, code: int, status: str, message: str = "API error") -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.message = message


class FakeModel:
    def __init__(self, name: str, actions: list[str] | None = None) -> None:
        self.name = name
        self.supported_actions = actions if actions is not None else ["generateContent"]


class FakeModels:
    def __init__(self, models: list[FakeModel] | None = None, error: Exception | None = None) -> None:
        self._models = models or []
        self._error = error
        self.list_calls = 0

    def list(self):
        self.list_calls += 1
        if self._error is not None:
            raise self._error
        return list(self._models)


class FakeClient:
    def __init__(self, models: FakeModels) -> None:
        self.models = models


class ModelAvailabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_model_availability_cache()
        patcher = mock.patch.object(settings, "gemini_api_key", "test-key-not-real")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(reset_model_availability_cache)

    def probe(self, models: FakeModels):
        with mock.patch.object(
            gemini_client, "create_client", return_value=FakeClient(models)
        ):
            return check_generation_model(force=True)

    def test_model_listed_with_prefix_is_ready(self) -> None:
        models = FakeModels([FakeModel("models/gemini-3.5-flash-lite")])
        with mock.patch.object(settings, "gemini_model", "gemini-3.5-flash-lite"):
            result = self.probe(models)
        self.assertEqual(result.state, MODEL_STATE_READY)
        self.assertTrue(result.available)
        self.assertIsNone(result.detail)
        self.assertIsNotNone(result.checked_at)

    def test_model_listed_without_prefix_is_ready(self) -> None:
        models = FakeModels([FakeModel("gemini-3.5-flash-lite")])
        with mock.patch.object(settings, "gemini_model", "gemini-3.5-flash-lite"):
            result = self.probe(models)
        self.assertEqual(result.state, MODEL_STATE_READY)

    def test_missing_model_is_unavailable_and_names_the_setting(self) -> None:
        models = FakeModels([FakeModel("models/gemini-2.5-flash")])
        with mock.patch.object(settings, "gemini_model", "gemini-9.9-ghost"):
            result = self.probe(models)
        self.assertEqual(result.state, MODEL_STATE_UNAVAILABLE)
        self.assertFalse(result.available)
        self.assertIn("GEMINI_MODEL", result.detail or "")

    def test_model_without_generate_content_is_unavailable(self) -> None:
        models = FakeModels(
            [FakeModel("models/gemini-embedding-001", actions=["embedContent"])]
        )
        with mock.patch.object(settings, "gemini_model", "gemini-embedding-001"):
            result = self.probe(models)
        self.assertEqual(result.state, MODEL_STATE_UNAVAILABLE)
        self.assertIn("generateContent", result.detail or "")

    def test_rejected_key_is_unauthorized(self) -> None:
        models = FakeModels(error=ApiError(403, "PERMISSION_DENIED", "API key not valid"))
        result = self.probe(models)
        self.assertEqual(result.state, MODEL_STATE_UNAUTHORIZED)
        self.assertFalse(result.available)

    def test_transient_failure_is_unknown_not_unavailable(self) -> None:
        models = FakeModels(error=ApiError(503, "UNAVAILABLE", "service busy"))
        result = self.probe(models)
        self.assertEqual(result.state, MODEL_STATE_UNKNOWN)
        self.assertIsNone(result.available)
        self.assertIn("503", result.detail or "")

    def test_missing_key_is_not_configured_without_a_request(self) -> None:
        models = FakeModels([FakeModel("models/gemini-3.5-flash-lite")])
        with mock.patch.object(settings, "gemini_api_key", ""):
            result = self.probe(models)
        self.assertEqual(result.state, MODEL_STATE_NOT_CONFIGURED)
        self.assertFalse(result.available)
        self.assertEqual(models.list_calls, 0)

    def test_result_is_cached_between_requests(self) -> None:
        models = FakeModels([FakeModel("models/gemini-3.5-flash-lite")])
        with mock.patch.object(settings, "gemini_model", "gemini-3.5-flash-lite"):
            with mock.patch.object(
                gemini_client, "create_client", return_value=FakeClient(models)
            ):
                first = check_generation_model()
                second = check_generation_model()
        self.assertEqual(first.state, MODEL_STATE_READY)
        self.assertEqual(first, second)
        self.assertEqual(models.list_calls, 1)

    def test_detail_and_dict_never_contain_the_key(self) -> None:
        models = FakeModels(error=ApiError(503, "UNAVAILABLE", "service busy"))
        result = self.probe(models)
        payload = result.as_dict()
        self.assertEqual(
            set(payload), {"model_status", "model_available", "model_detail", "model_checked_at"}
        )
        self.assertNotIn("test-key-not-real", str(payload))


if __name__ == "__main__":
    unittest.main()
