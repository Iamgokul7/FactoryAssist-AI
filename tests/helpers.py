"""Shared fixtures for the document-management and access-control tests.

Every test gets its own temporary managed directory, uploads directory, vector
store and SQLite database, so tests never touch the real plant corpus or the
developer's account database. Embeddings are produced by a deterministic stub:
no test calls the Gemini API or needs an API key.
"""

from __future__ import annotations

import gc
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import pymupdf
from fastapi.testclient import TestClient

from backend.api import deps
from backend.core import security as security_module
from backend.core.config import settings
from backend.main import app
from backend.services import auth_store as auth_module
from backend.services import management_store as documents_module
from backend.services.auth_store import ROLE_ADMIN, ROLE_EMPLOYEE, ROLE_SOP_MANAGER
from backend.services.document_manager import DocumentManager
from backend.services.embedding_service import EmbeddingError
from backend.services.vector_store import VectorStore, VectorStoreError

ADMIN_PASSWORD = "AdminPassw0rd!2026"
MANAGER_PASSWORD = "ManagerPassw0rd!2026"
EMPLOYEE_PASSWORD = "EmployeePassw0rd!2026"

DOCUMENT_CODE = "QA-MAN-900"
DOCUMENT_TITLE = "Incoming Material Inspection - Standard Operating Procedure"
MANUFACTURING_TEXT = (
    "QA-MAN-900 Revision 05. Incoming material inspection procedure. "
    "The operator inspects each bearing housing with a digital caliper and "
    "records the measurement on the machine inspection sheet. "
    "Quality department, shop floor, production supervisor, tolerance 0.05 mm."
)
UNRELATED_TEXT = (
    "Annual leave policy for office staff. Employees may request leave through "
    "the human resources portal. Approval rests with the line manager and the "
    "payroll team records absence balances at the end of each quarter."
)

# A structurally valid PDF whose page tree is empty, used for the "empty PDF"
# case. PyMuPDF opens it with page_count == 0.
ZERO_PAGE_PDF = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [] /Count 0 >>
endobj
trailer
<< /Root 1 0 R /Size 3 >>
%%EOF
"""


def pdf_bytes(text: str = MANUFACTURING_TEXT, *, pages: int = 1) -> bytes:
    """Build a small, real PDF containing ``text``."""
    document = pymupdf.open()
    try:
        for index in range(max(1, pages)):
            page = document.new_page()
            body = text if index == 0 else f"{text} (page {index + 1})"
            page.insert_textbox(
                pymupdf.Rect(50, 60, 545, 760),
                body,
                fontsize=10,
                fontname="helv",
            )
        return document.tobytes()
    finally:
        document.close()


def blank_pdf_bytes() -> bytes:
    """A PDF with one page and no text layer (the scanned-PDF case)."""
    document = pymupdf.open()
    try:
        document.new_page()
        return document.tobytes()
    finally:
        document.close()


class FakeEmbedder:
    """Deterministic stand-in for EmbeddingService."""

    is_configured = True

    def __init__(self, *, fail: bool = False, dimensions: int = 8) -> None:
        self.fail = fail
        self.dimensions = dimensions
        self.calls = 0
        self.texts_embedded = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.texts_embedded += len(texts)
        if self.fail:
            raise EmbeddingError("Simulated embedding outage")
        return [[0.1 + (index % 5) * 0.01] * self.dimensions for index, _ in enumerate(texts)]

    def embed_query(self, text: str) -> list[float]:
        return [0.1] * self.dimensions


class BrokenVectorStore(VectorStore):
    """Vector store whose writes always fail (ChromaDB outage simulation)."""

    def upsert(self, records: Any) -> None:  # type: ignore[override]
        raise VectorStoreError("Simulated vector store failure")

    def delete_by_document(self, document_id: str) -> int:  # type: ignore[override]
        raise VectorStoreError("Simulated vector store failure")


class ManagementTestBase(unittest.TestCase):
    """Isolated app instance with an administrator, manager and employee."""

    def setUp(self) -> None:
        # ChromaDB keeps memory-mapped files open on Windows, so removal is
        # best-effort: a leftover temp directory must never fail a test.
        self.temp_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp_directory.cleanup)
        root = Path(self.temp_directory.name)

        # The real KDF costs ~0.5 s per hash by design; tests only need the
        # format and verification path, so they use a low iteration count.
        fast_hash = lambda password, **kwargs: security_module.hash_password(  # noqa: E731
            password, iterations=1200
        )

        self.patchers = [
            mock.patch.object(auth_module, "hash_password", fast_hash),
            mock.patch.object(settings, "managed_data_directory", root / "managed"),
            mock.patch.object(settings, "uploads_directory", root / "uploads"),
            mock.patch.object(settings, "chroma_persist_directory", root / "chroma"),
            mock.patch.object(settings, "max_upload_size_mb", 5),
            mock.patch.object(settings, "session_ttl_hours", 8),
            mock.patch.object(settings, "login_max_attempts", 5),
            mock.patch.object(settings, "login_window_minutes", 15),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.addCleanup(self._stop_patchers)

        auth_module.reset_auth_store()
        documents_module.reset_document_store()
        deps.reset_document_manager()

        self.embedder = FakeEmbedder()
        self.vector_store = VectorStore()
        self.manager = DocumentManager(
            embedder=self.embedder, vector_store=self.vector_store
        )

        app.dependency_overrides[deps.get_document_manager] = lambda: self.manager
        self.addCleanup(app.dependency_overrides.clear)

        self.auth = auth_module.get_auth_store()
        self.auth.create_user("admin", ADMIN_PASSWORD, ROLE_ADMIN, full_name="Plant Admin")
        self.auth.create_user("manager", MANAGER_PASSWORD, ROLE_SOP_MANAGER, full_name="SOP Manager")
        self.auth.create_user("employee", EMPLOYEE_PASSWORD, ROLE_EMPLOYEE, full_name="Shop Floor")

        self.client = TestClient(app)

    def _stop_patchers(self) -> None:
        self.manager = None
        self.vector_store = None
        gc.collect()
        for patcher in reversed(self.patchers):
            patcher.stop()
        auth_module.reset_auth_store()
        documents_module.reset_document_store()
        deps.reset_document_manager()

    # --- session helpers ---

    def login(self, username: str = "manager", password: str = MANAGER_PASSWORD) -> dict[str, Any]:
        response = self.client.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.client.headers.update({"X-CSRF-Token": payload["csrf_token"]})
        return payload

    def logout(self) -> None:
        self.client.post("/api/auth/logout")
        self.client.cookies.clear()
        self.client.headers.pop("X-CSRF-Token", None)

    # --- upload helper ---

    def upload(
        self,
        *,
        code: str = DOCUMENT_CODE,
        revision: str = "05",
        title: str = DOCUMENT_TITLE,
        department: str = "Quality",
        category: str = "Manufacturing SOP",
        effective_date: str = "2026-11-01",
        description: str = "Inspection procedure",
        content: bytes | None = None,
        filename: str = "incoming-inspection-rev05.pdf",
        content_type: str = "application/pdf",
        include_file: bool = True,
        headers: dict[str, str] | None = None,
    ):
        fields = {
            "document_code": code,
            "document_title": title,
            "revision": revision,
            "department": department,
            "category": category,
            "effective_date": effective_date,
            "description": description,
        }
        files = (
            {"file": (filename, content if content is not None else pdf_bytes(), content_type)}
            if include_file
            else None
        )
        return self.client.post(
            "/api/documents/upload", data=fields, files=files, headers=headers or {}
        )

    # --- inspection helpers ---

    def indexed_statuses(self, document_key: str) -> list[str]:
        metadata = self.vector_store.metadata_for_document(document_key)
        return [str(item.get("document_status")) for item in metadata.values()]
