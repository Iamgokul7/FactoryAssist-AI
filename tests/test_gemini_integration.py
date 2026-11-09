"""Focused tests for Gemini request building and error handling.

These never call the Gemini API: the live six-question check is a separate,
manual run against a configured key. Run with:

    python -m unittest discover -s tests -t . -v
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from backend.services.gemini_client import (
    GeminiRequestError,
    describe_error,
    error_code,
    is_retryable,
    is_timeout,
    redact,
)
from backend.services.rag_service import (
    RagService,
    RetrievedChunk,
    _parse_response,
    model_major_version,
    thinking_config,
)


class FakeApiError(Exception):
    """Stand-in for a google.genai ClientError, with the same public fields."""

    def __init__(self, code: int, status: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.message = message


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="mnt-1",
        text="Maintain coolant concentration at 6 to 8 %.",
        document_id="mnt-man-cnc-02-rev02",
        document_title="CNC Maintenance Manual",
        document_code="MNT-MAN-CNC-02",
        revision="02",
        document_status="active",
        source_filename="MNT-MAN-CNC-02.pdf",
        page_number=1,
        similarity=0.72,
    )


class FakeModels:
    """Returns a valid JSON answer, failing the first call if asked to."""

    def __init__(self, fail_first_with: Exception | None = None) -> None:
        self.configs: list[Any] = []
        self._fail_first_with = fail_first_with

    def generate_content(self, *, model: str, contents: str, config: Any) -> Any:
        self.configs.append(config)
        if self._fail_first_with is not None and len(self.configs) == 1:
            raise self._fail_first_with
        return SimpleNamespace(
            parsed={
                "answer": "The coolant concentration for the TX-200 is 6 to 8 %.",
                "supported": True,
                "used_source_indices": [1],
            },
            text=None,
        )


class FakeClient:
    def __init__(self, fail_first_with: Exception | None = None) -> None:
        self.models = FakeModels(fail_first_with)


def _service(client: Any) -> RagService:
    """A RagService wired to a fake client, avoiding Chroma and the network."""
    service = RagService.__new__(RagService)
    service._client = client
    return service


class ThinkingConfigTests(unittest.TestCase):
    def test_gemini_3_gets_thinking_level_and_no_budget(self) -> None:
        config = thinking_config("gemini-3.5-flash-lite")
        self.assertIsNotNone(config)
        self.assertIsNone(config.thinking_budget)
        self.assertEqual(config.thinking_level.value.lower(), "low")

    def test_older_models_get_no_thinking_hint(self) -> None:
        # thinking_budget=0 is not valid on every 2.x model, so omit the hint.
        self.assertIsNone(thinking_config("gemini-2.5-flash"))
        self.assertIsNone(thinking_config("gemini-flash-latest"))

    def test_model_version_parsing(self) -> None:
        self.assertEqual(model_major_version("models/gemini-3-flash-preview"), 3)
        self.assertEqual(model_major_version("gemini-2.5-flash"), 2)
        self.assertIsNone(model_major_version("gemini-flash-latest"))


class GenerationRetryTests(unittest.TestCase):
    def test_400_on_thinking_config_is_retried_without_it(self) -> None:
        client = FakeClient(
            fail_first_with=FakeApiError(
                400, "INVALID_ARGUMENT", "Request contains an invalid argument."
            )
        )
        answer, supported, indices = _service(client)._generate("q", [_chunk()])

        self.assertTrue(supported)
        self.assertEqual(indices, [1])
        self.assertIn("6 to 8", answer)
        self.assertEqual(len(client.models.configs), 2)
        self.assertIsNotNone(client.models.configs[0].thinking_config)
        self.assertIsNone(client.models.configs[1].thinking_config)

    def test_hard_failure_is_classified_not_reported_as_a_key_problem(self) -> None:
        client = FakeClient(
            fail_first_with=FakeApiError(
                404, "NOT_FOUND", "models/gemini-9 is not found for API version v1beta"
            )
        )
        with self.assertRaises(GeminiRequestError) as caught:
            _service(client)._generate("q", [_chunk()])

        error = caught.exception
        self.assertEqual(error.code, "404 NOT_FOUND")
        self.assertIn("model is not available", str(error))
        self.assertNotIn("GEMINI_API_KEY", str(error))
        self.assertIn("404", error.detail or "")


class ErrorClassificationTests(unittest.TestCase):
    def test_each_category_has_its_own_message(self) -> None:
        invalid = describe_error(FakeApiError(400, "INVALID_ARGUMENT", "bad"))
        credentials = describe_error(FakeApiError(401, "UNAUTHENTICATED", "bad"))
        missing = describe_error(FakeApiError(404, "NOT_FOUND", "bad"))
        limited = describe_error(FakeApiError(429, "RESOURCE_EXHAUSTED", "bad"))
        unavailable = describe_error(FakeApiError(503, "UNAVAILABLE", "bad"))
        timeout = describe_error(TimeoutError("timed out"))

        self.assertIn("not an API key problem", invalid)
        self.assertIn("GEMINI_API_KEY", credentials)
        self.assertIn("GEMINI_MODEL", missing)
        self.assertIn("rate limit", limited)
        self.assertIn("temporarily unavailable", unavailable)
        self.assertIn("too long", timeout)
        self.assertEqual(len({invalid, credentials, missing, limited, unavailable, timeout}), 6)

    def test_retryable_and_timeout_detection(self) -> None:
        self.assertTrue(is_retryable(FakeApiError(503, "UNAVAILABLE", "busy")))
        self.assertFalse(is_retryable(FakeApiError(400, "INVALID_ARGUMENT", "bad")))
        self.assertFalse(is_retryable(TimeoutError("timed out")))
        self.assertTrue(is_timeout(TimeoutError("timed out")))

    def test_error_code_and_redaction(self) -> None:
        self.assertEqual(
            error_code(FakeApiError(400, "INVALID_ARGUMENT", "bad")), "400 INVALID_ARGUMENT"
        )
        self.assertEqual(redact("see https://x/y?key=SECRET123&alt=json"), "see https://x/y?key=***&alt=json")


class ResponseParsingTests(unittest.TestCase):
    def test_parsed_payload_is_used(self) -> None:
        response = SimpleNamespace(
            parsed={"answer": "42", "supported": True, "used_source_indices": [1, 1, 9]}
        )
        answer, supported, indices = _parse_response(response, source_count=3)
        self.assertEqual((answer, supported, indices), ("42", True, [1]))

    def test_fenced_json_text_is_accepted(self) -> None:
        response = SimpleNamespace(parsed=None, text='```json\n{"answer": "6-8%", "supported": true}\n```')
        answer, supported, indices = _parse_response(response, source_count=2)
        self.assertEqual((answer, supported, indices), ("6-8%", True, []))


if __name__ == "__main__":
    unittest.main()
