"""Tests for upload validation, processing and revision governance.

These tests run entirely offline: embeddings are stubbed and each test owns a
temporary ChromaDB store and upload directory.
"""

from __future__ import annotations

import unittest

from backend.api import deps
from backend.core.config import settings
from backend.main import app
from backend.services import management_store
from backend.services.document_manager import (
    DocumentManager,
    recover_interrupted_processing,
)

from tests.helpers import (
    DOCUMENT_CODE,
    MANUFACTURING_TEXT,
    UNRELATED_TEXT,
    BrokenVectorStore,
    ManagementTestBase,
    ZERO_PAGE_PDF,
    blank_pdf_bytes,
    pdf_bytes,
)


class UploadValidationTests(ManagementTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.login("manager", "ManagerPassw0rd!2026")

    def test_rejects_non_pdf_content(self) -> None:
        response = self.upload(content=b"this is not a pdf at all")
        self.assertEqual(response.status_code, 400)
        self.assertIn("PDF", response.json()["detail"])
        self.assertEqual(self.manager.store.all(), [])

    def test_rejects_wrong_extension(self) -> None:
        response = self.upload(filename="procedure.txt")
        self.assertEqual(response.status_code, 415)

    def test_rejects_wrong_mime_type(self) -> None:
        response = self.upload(content_type="text/plain")
        self.assertEqual(response.status_code, 415)

    def test_rejects_corrupted_pdf(self) -> None:
        response = self.upload(content=b"%PDF-1.7\n1 0 obj << broken")
        self.assertEqual(response.status_code, 400)
        self.assertIn("corrupted", response.json()["detail"].lower())

    def test_rejects_empty_pdf(self) -> None:
        response = self.upload(content=ZERO_PAGE_PDF)
        self.assertEqual(response.status_code, 400)
        self.assertIn("no pages", response.json()["detail"].lower())

    def test_rejected_corrupt_upload_leaves_no_stored_file(self) -> None:
        before = set(settings.uploads_directory.glob("*"))
        response = self.upload(
            content=b"%PDF-1.7\n" + b"not really a pdf" * 100,
            filename="broken-rev05.pdf",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(settings.uploads_directory.glob("*")), before)

    def test_rejects_pdf_without_extractable_text(self) -> None:
        response = self.upload(content=blank_pdf_bytes())
        self.assertEqual(response.status_code, 400)
        self.assertIn("no extractable text", response.json()["detail"].lower())

    def test_rejects_oversized_upload(self) -> None:
        oversized = b"%PDF-1.4\n" + b"0" * (5 * 1024 * 1024 + 64)
        response = self.upload(content=oversized)
        self.assertEqual(response.status_code, 413)

    def test_rejects_missing_file_field(self) -> None:
        response = self.upload(include_file=False)
        self.assertEqual(response.status_code, 422)

    def test_rejects_missing_metadata(self) -> None:
        response = self.client.post(
            "/api/documents/upload",
            data={"document_code": DOCUMENT_CODE},
            files={"file": ("doc.pdf", pdf_bytes(), "application/pdf")},
        )
        self.assertEqual(response.status_code, 422)

    def test_rejects_invalid_metadata(self) -> None:
        cases = [
            {"code": "not a code!"},
            {"revision": "abc"},
            {"revision": "0"},
            {"category": "Random Policy"},
            {"effective_date": "2026-13-01"},
            {"title": "x"},
        ]
        for case in cases:
            with self.subTest(case=case):
                response = self.upload(**case)
                self.assertEqual(response.status_code, 422, response.text)

    def test_rejects_duplicate_revision(self) -> None:
        self.assertEqual(self.upload().status_code, 201)
        response = self.upload(content=pdf_bytes("QA-MAN-900 Revision 05 different body"))
        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json()["detail"])

    def test_rejects_identical_file_under_new_revision(self) -> None:
        content = pdf_bytes()
        self.assertEqual(self.upload(revision="05", content=content).status_code, 201)
        response = self.upload(revision="06", content=content)
        self.assertEqual(response.status_code, 409)
        self.assertIn("already been uploaded", response.json()["detail"])


class ProcessingTests(ManagementTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.login("manager", "ManagerPassw0rd!2026")

    def test_successful_upload_is_pending_and_indexed(self) -> None:
        response = self.upload()
        self.assertEqual(response.status_code, 201, response.text)
        document = response.json()["document"]

        self.assertEqual(document["status"], "pending_review")
        self.assertEqual(document["document_key"], "qa-man-900-rev05")
        self.assertGreaterEqual(document["chunk_count"], 1)
        self.assertEqual(document["page_count"], 1)
        self.assertTrue(document["processed_at"])

        stored = management_store.get_document_store().require("qa-man-900-rev05")
        self.assertTrue(stored["stored_path"] and stored["stored_path"].endswith(".pdf"))
        self.assertEqual(
            self.indexed_statuses("qa-man-900-rev05"),
            ["pending_review"] * document["chunk_count"],
        )

    def test_embedding_failure_marks_failed_and_leaves_no_chunks(self) -> None:
        self.embedder.fail = True
        response = self.upload()
        self.assertEqual(response.status_code, 201)
        document = response.json()["document"]

        self.assertEqual(document["status"], "failed")
        self.assertIn("embedding service", (document["error"] or "").lower())
        self.assertEqual(document["chunk_count"], 0)
        self.assertEqual(self.vector_store.count(), 0)

    def test_chroma_failure_marks_failed(self) -> None:
        app.dependency_overrides[deps.get_document_manager] = lambda: DocumentManager(
            embedder=self.embedder, vector_store=BrokenVectorStore()
        )

        response = self.upload()
        self.assertEqual(response.status_code, 201)
        document = response.json()["document"]
        self.assertEqual(document["status"], "failed")
        self.assertIn("index could not be updated", (document["error"] or "").lower())
        self.assertEqual(self.vector_store.count(), 0)

    def test_retry_reprocesses_a_failed_upload(self) -> None:
        self.embedder.fail = True
        first = self.upload().json()["document"]
        self.assertEqual(first["status"], "failed")

        self.embedder.fail = False
        response = self.client.post(f"/api/documents/{first['document_key']}/retry")
        self.assertEqual(response.status_code, 200, response.text)
        document = response.json()["document"]
        self.assertEqual(document["status"], "pending_review")
        self.assertGreaterEqual(document["chunk_count"], 1)
        self.assertEqual(document["error"], None)

    def test_retry_reuses_existing_embeddings(self) -> None:
        document = self.upload().json()["document"]
        calls_after_upload = self.embedder.calls
        self.assertEqual(calls_after_upload, 1)

        response = self.client.post(f"/api/documents/{document['document_key']}/retry")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.embedder.calls, calls_after_upload)
        self.assertEqual(response.json()["document"]["chunk_count"], document["chunk_count"])

    def test_retry_is_refused_for_active_documents(self) -> None:
        document = self.upload().json()["document"]
        self.client.post(f"/api/documents/{document['document_key']}/activate")
        response = self.client.post(f"/api/documents/{document['document_key']}/retry")
        self.assertEqual(response.status_code, 409)

    def test_unrelated_document_is_flagged_but_not_auto_rejected(self) -> None:
        response = self.upload(content=pdf_bytes(UNRELATED_TEXT), title="Office Leave Policy")
        self.assertEqual(response.status_code, 201, response.text)
        document = response.json()["document"]

        self.assertEqual(document["status"], "pending_review")
        self.assertFalse(document["classification"]["related"])
        self.assertTrue(document["classification"]["warning"])
        self.assertTrue(any("does not look like" in warning for warning in document["warnings"]))

    def test_interrupted_processing_is_recovered_as_failed(self) -> None:
        document = self.upload().json()["document"]
        key = document["document_key"]
        management_store.get_document_store().update(key, status="processing")

        recovered = recover_interrupted_processing()
        self.assertEqual(recovered, 1)
        record = management_store.get_document_store().require(key)
        self.assertEqual(record["status"], "failed")
        self.assertIn("interrupted", (record["error"] or "").lower())

    def test_stats_count_each_status(self) -> None:
        active = self.upload(revision="05").json()["document"]
        self.client.post(f"/api/documents/{active['document_key']}/activate")
        self.upload(
            revision="06",
            content=pdf_bytes(MANUFACTURING_TEXT + " revision six"),
        )

        stats = self.client.get("/api/documents/stats").json()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["active"], 1)
        self.assertEqual(stats["pending_review"], 1)


class RevisionLifecycleTests(ManagementTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.login("manager", "ManagerPassw0rd!2026")

    def _upload(self, revision: str, body: str | None = None):
        return self.upload(
            revision=revision,
            content=pdf_bytes(body or f"{MANUFACTURING_TEXT} revision {revision}"),
        ).json()["document"]

    def test_new_revision_stays_pending_while_current_stays_active(self) -> None:
        rev05 = self._upload("05")
        self.client.post(f"/api/documents/{rev05['document_key']}/activate")

        rev06 = self._upload("06")
        self.assertEqual(rev06["status"], "pending_review")

        revisions = {
            item["revision"]: item
            for item in self.client.get(
                f"/api/documents/{rev06['document_key']}/revisions"
            ).json()["revisions"]
        }
        self.assertEqual(revisions["05"]["status"], "active")
        self.assertEqual(revisions["06"]["status"], "pending_review")

    def test_activation_archives_previous_revision_and_removes_its_chunks(self) -> None:
        rev05 = self._upload("05")
        self.client.post(f"/api/documents/{rev05['document_key']}/activate")

        rev06 = self._upload("06")
        response = self.client.post(f"/api/documents/{rev06['document_key']}/activate")
        self.assertEqual(response.status_code, 200, response.text)

        store = management_store.get_document_store()
        archived = store.require(rev05["document_key"])
        activated = store.require(rev06["document_key"])

        self.assertEqual(archived["status"], "archived")
        self.assertEqual(archived["superseded_by_document_key"], rev06["document_key"])
        self.assertEqual(activated["status"], "active")
        self.assertEqual(activated["supersedes_document_key"], rev05["document_key"])
        self.assertEqual(activated["approved_by"], "manager")
        self.assertTrue(activated["approved_at"])
        self.assertEqual(self.vector_store.metadata_for_document(rev05["document_key"]), {})

    def test_only_one_active_revision_per_document_code(self) -> None:
        for revision in ("05", "06", "07"):
            document = self._upload(revision)
            self.client.post(f"/api/documents/{document['document_key']}/activate")

        revisions = management_store.get_document_store().revisions_of(DOCUMENT_CODE)
        active = [item for item in revisions if item["status"] == "active"]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["revision"], "07")
        self.assertEqual(
            sorted(item["status"] for item in revisions if item["revision"] != "07"),
            ["archived", "archived"],
        )

    def test_activation_requires_processing_to_have_completed(self) -> None:
        key = self._upload("05")["document_key"]
        management_store.get_document_store().update(key, status="failed")
        response = self.client.post(f"/api/documents/{key}/activate")
        self.assertEqual(response.status_code, 409)

    def test_cannot_archive_the_only_active_revision(self) -> None:
        document = self._upload("05")
        self.client.post(f"/api/documents/{document['document_key']}/activate")

        response = self.client.post(f"/api/documents/{document['document_key']}/archive")
        self.assertEqual(response.status_code, 409)
        self.assertIn("only active revision", response.json()["detail"])

    def test_admin_can_force_archive_the_last_active_revision(self) -> None:
        document = self._upload("05")
        self.client.post(f"/api/documents/{document['document_key']}/activate")

        self.logout()
        self.login("admin", "AdminPassw0rd!2026")
        response = self.client.post(
            f"/api/documents/{document['document_key']}/archive?force=true"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["document"]["status"], "archived")
        self.assertEqual(self.vector_store.count(), 0)

    def test_rejected_revision_cannot_be_activated(self) -> None:
        document = self._upload("05")
        response = self.client.post(
            f"/api/documents/{document['document_key']}/reject",
            json={"reason": "Wrong revision format"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["document"]["status"], "rejected")

        activate = self.client.post(f"/api/documents/{document['document_key']}/activate")
        self.assertEqual(activate.status_code, 409)
        self.assertEqual(self.vector_store.metadata_for_document(document["document_key"]), {})


class RetrievalExclusionTests(ManagementTestBase):
    """The security property: only approved, active chunks are retrievable."""

    def setUp(self) -> None:
        super().setUp()
        self.login("manager", "ManagerPassw0rd!2026")

    def _retrieved_keys(self) -> set[str]:
        chunks = self.vector_store.query(
            self.embedder.embed_query("inspection"),
            top_k=10,
            where={"document_status": "active"},
        )
        return {chunk.document_id for chunk in chunks}

    def test_pending_document_is_not_retrievable(self) -> None:
        document = self.upload().json()["document"]
        self.assertEqual(document["status"], "pending_review")
        self.assertGreater(self.vector_store.count(), 0)
        self.assertEqual(self._retrieved_keys(), set())

    def test_active_document_is_retrievable(self) -> None:
        document = self.upload().json()["document"]
        self.client.post(f"/api/documents/{document['document_key']}/activate")
        self.assertIn(document["document_key"], self._retrieved_keys())

    def test_archived_document_is_not_retrievable(self) -> None:
        document = self.upload().json()["document"]
        key = document["document_key"]
        self.client.post(f"/api/documents/{key}/activate")
        self.assertIn(key, self._retrieved_keys())

        # Only an administrator may retire the last active revision.
        self.logout()
        self.login("admin", "AdminPassw0rd!2026")
        response = self.client.post(f"/api/documents/{key}/archive?force=true")
        self.assertEqual(response.status_code, 200, response.text)

        self.assertNotIn(key, self._retrieved_keys())
        self.assertEqual(self.vector_store.metadata_for_document(key), {})

    def test_rejected_document_is_not_retrievable(self) -> None:
        document = self.upload().json()["document"]
        key = document["document_key"]
        self.client.post(f"/api/documents/{key}/reject", json={"reason": "duplicate"})
        self.assertEqual(self.vector_store.metadata_for_document(key), {})
        self.assertNotIn(key, self._retrieved_keys())

    def test_failed_document_is_not_retrievable(self) -> None:
        self.embedder.fail = True
        document = self.upload().json()["document"]
        self.assertEqual(document["status"], "failed")
        self.assertEqual(self.vector_store.count(), 0)
        self.assertNotIn(document["document_key"], self._retrieved_keys())

    def test_pending_revision_of_active_code_is_not_retrievable(self) -> None:
        rev05 = self.upload(revision="05").json()["document"]
        self.client.post(f"/api/documents/{rev05['document_key']}/activate")

        rev06 = self.upload(
            revision="06", content=pdf_bytes(MANUFACTURING_TEXT + " revision six")
        ).json()["document"]

        retrieved = self._retrieved_keys()
        self.assertIn(rev05["document_key"], retrieved)
        self.assertNotIn(rev06["document_key"], retrieved)


class AuditTrailTests(ManagementTestBase):
    def test_governance_actions_are_audited_without_secrets(self) -> None:
        self.login("manager", "ManagerPassw0rd!2026")
        document = self.upload().json()["document"]
        key = document["document_key"]
        self.client.post(f"/api/documents/{key}/activate")

        self.logout()
        self.login("admin", "AdminPassw0rd!2026")
        response = self.client.get("/api/audit?limit=50")
        self.assertEqual(response.status_code, 200)

        records = response.json()["records"]
        actions = {record["action"] for record in records}
        self.assertTrue(
            {
                "login_success",
                "upload_received",
                "processing_succeeded",
                "revision_activated",
            }.issubset(actions),
            actions,
        )

        body = response.text.lower()
        for secret in ("adminpassw0rd", "managerpassw0rd", "csrf", "password_hash"):
            self.assertNotIn(secret, body)

        upload_records = [r for r in records if r["action"] == "upload_received"]
        self.assertEqual(upload_records[0]["document_key"], key)
        self.assertEqual(upload_records[0]["revision"], "05")


class ValidationFailureAuditTests(ManagementTestBase):
    def test_validation_failure_is_audited(self) -> None:
        self.login("manager", "ManagerPassw0rd!2026")
        self.upload(content=b"not a pdf")

        self.logout()
        self.login("admin", "AdminPassw0rd!2026")
        actions = {record["action"] for record in self.client.get("/api/audit").json()["records"]}
        self.assertIn("upload_validation_failed", actions)


if __name__ == "__main__":
    unittest.main()
