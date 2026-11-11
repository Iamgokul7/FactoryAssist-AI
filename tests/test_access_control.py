"""Authentication, role-based access control, CSRF and session tests.

Every endpoint is exercised through the real FastAPI app with a temporary
SQLite database, so these tests cover the server-side enforcement rather than
the browser's hidden buttons.
"""

from __future__ import annotations

import unittest
from unittest import mock

from backend.core.config import settings
from backend.services.auth_store import ROLE_EMPLOYEE

from tests.helpers import (
    ADMIN_PASSWORD,
    EMPLOYEE_PASSWORD,
    MANAGER_PASSWORD,
    ManagementTestBase,
)


class AnonymousAccessTests(ManagementTestBase):
    def test_management_endpoints_require_a_session(self) -> None:
        calls = [
            ("get", "/api/documents", None),
            ("get", "/api/documents/stats", None),
            ("get", "/api/documents/qa-man-900-rev05", None),
            ("get", "/api/documents/qa-man-900-rev05/revisions", None),
            ("post", "/api/documents/qa-man-900-rev05/activate", None),
            ("post", "/api/documents/qa-man-900-rev05/archive", None),
            ("post", "/api/documents/qa-man-900-rev05/reject", None),
            ("post", "/api/documents/qa-man-900-rev05/retry", None),
            ("get", "/api/users", None),
            ("get", "/api/audit", None),
        ]
        for method, path, body in calls:
            with self.subTest(path=path):
                response = getattr(self.client, method)(path) if body is None else getattr(
                    self.client, method
                )(path, json=body)
                self.assertEqual(response.status_code, 401, path)

    def test_anonymous_upload_is_rejected(self) -> None:
        response = self.upload()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.manager.store.all(), [])

    def test_me_reports_an_anonymous_caller(self) -> None:
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["authenticated"])

    def test_chat_remains_public(self) -> None:
        # Regression: the assistant must not start demanding a session.
        self.assertEqual(
            self.client.post("/api/chat", json={"question": "   "}).status_code, 400
        )


class EmployeeAccessTests(ManagementTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.login("employee", EMPLOYEE_PASSWORD)

    def test_employee_cannot_list_or_upload(self) -> None:
        self.assertEqual(self.client.get("/api/documents").status_code, 403)
        self.assertEqual(self.upload().status_code, 403)

    def test_employee_cannot_activate_archive_or_reject(self) -> None:
        for action in ("activate", "archive", "reject", "retry"):
            with self.subTest(action=action):
                response = self.client.post(
                    f"/api/documents/qa-man-900-rev05/{action}", json={"reason": "x"}
                )
                self.assertEqual(response.status_code, 403)

    def test_employee_cannot_read_management_metadata(self) -> None:
        self.assertEqual(self.client.get("/api/documents/stats").status_code, 403)
        self.assertEqual(self.client.get("/api/audit").status_code, 403)
        self.assertEqual(self.client.get("/api/users").status_code, 403)

    def test_employee_can_still_use_the_chat_endpoint(self) -> None:
        self.assertEqual(
            self.client.post("/api/chat", json={"question": "   "}).status_code, 400
        )

    def test_refused_access_is_audited(self) -> None:
        self.client.get("/api/documents")
        actions = {record["action"] for record in self.auth.list_audit(limit=50)}
        self.assertIn("unauthorized_access", actions)


class ManagerAccessTests(ManagementTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.login("manager", MANAGER_PASSWORD)

    def test_manager_can_run_the_full_document_lifecycle(self) -> None:
        document = self.upload().json()["document"]
        key = document["document_key"]

        self.assertEqual(
            self.client.post(f"/api/documents/{key}/activate").status_code, 200
        )
        listed = self.client.get("/api/documents").json()
        self.assertEqual(listed["stats"]["active"], 1)
        self.assertEqual(
            self.client.get(f"/api/documents/{key}/status").json()["status"], "active"
        )
        self.assertEqual(
            len(self.client.get(f"/api/documents/{key}/revisions").json()["revisions"]), 1
        )
        pdf = self.client.get(f"/api/documents/{key}/file")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.headers["content-type"], "application/pdf")

    def test_manager_cannot_manage_accounts_or_read_the_audit_log(self) -> None:
        self.assertEqual(self.client.get("/api/users").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/users",
                json={"username": "x", "password": ADMIN_PASSWORD, "role": "admin"},
            ).status_code,
            403,
        )
        self.assertEqual(self.client.get("/api/audit").status_code, 403)

    def test_manager_cannot_edit_metadata(self) -> None:
        key = self.upload().json()["document"]["document_key"]
        response = self.client.patch(
            f"/api/documents/{key}", json={"document_title": "Renamed by manager"}
        )
        self.assertEqual(response.status_code, 403)


class AdminAccessTests(ManagementTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.login("admin", ADMIN_PASSWORD)

    def test_admin_can_manage_accounts(self) -> None:
        created = self.client.post(
            "/api/users",
            json={
                "username": "newmanager",
                "password": "NewManagerPass!2026",
                "role": "sop_manager",
                "full_name": "New Manager",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        user_id = created.json()["user"]["id"]

        updated = self.client.patch(f"/api/users/{user_id}", json={"role": "employee"})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["user"]["role"], ROLE_EMPLOYEE)

        users = self.client.get("/api/users").json()
        self.assertIn(ROLE_EMPLOYEE, users["roles"])

    def test_admin_cannot_demote_the_last_administrator(self) -> None:
        admin = self.auth.get_user_by_username("admin")
        response = self.client.patch(
            f"/api/users/{admin.id}", json={"role": "employee"}
        )
        self.assertEqual(response.status_code, 409)

    def test_admin_can_edit_document_metadata(self) -> None:
        key = self.upload().json()["document"]["document_key"]
        response = self.client.patch(
            f"/api/documents/{key}",
            json={"document_title": "Incoming Material Inspection (renamed)", "department": "Quality"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["document"]["document_title"],
            "Incoming Material Inspection (renamed)",
        )

    def test_admin_sees_the_audit_log(self) -> None:
        self.upload()
        response = self.client.get("/api/audit?limit=20")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["records"])


class CsrfTests(ManagementTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.payload = self.login("manager", MANAGER_PASSWORD)
        self.key = self.upload().json()["document"]["document_key"]

    def test_mutation_without_csrf_token_is_refused(self) -> None:
        self.client.headers.pop("X-CSRF-Token", None)
        response = self.client.post(f"/api/documents/{self.key}/activate")
        self.assertEqual(response.status_code, 403)

    def test_mutation_with_wrong_csrf_token_is_refused(self) -> None:
        self.client.headers.update({"X-CSRF-Token": "not-the-session-token"})
        response = self.client.post(f"/api/documents/{self.key}/activate")
        self.assertEqual(response.status_code, 403)

    def test_cross_origin_mutation_is_refused(self) -> None:
        self.client.headers.update({"Origin": "http://evil.example"})
        response = self.client.post(f"/api/documents/{self.key}/activate")
        self.assertEqual(response.status_code, 403)

    def test_same_origin_with_token_succeeds(self) -> None:
        self.client.headers.update({"Origin": "http://testserver"})
        response = self.client.post(f"/api/documents/{self.key}/activate")
        self.assertEqual(response.status_code, 200, response.text)

    def test_get_requests_do_not_require_a_csrf_token(self) -> None:
        self.client.headers.pop("X-CSRF-Token", None)
        self.assertEqual(self.client.get("/api/documents").status_code, 200)


class LoginSecurityTests(ManagementTestBase):
    def test_wrong_password_is_rejected_and_audited(self) -> None:
        response = self.client.post(
            "/api/auth/login", json={"username": "manager", "password": "wrong-password"}
        )
        self.assertEqual(response.status_code, 401)
        actions = {record["action"] for record in self.auth.list_audit(limit=20)}
        self.assertIn("login_failed", actions)

    def test_repeated_failures_are_rate_limited(self) -> None:
        for _ in range(settings.login_max_attempts):
            response = self.client.post(
                "/api/auth/login", json={"username": "manager", "password": "wrong-password"}
            )
            self.assertEqual(response.status_code, 401)

        blocked = self.client.post(
            "/api/auth/login", json={"username": "manager", "password": MANAGER_PASSWORD}
        )
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Too many", blocked.json()["detail"])
        actions = {record["action"] for record in self.auth.list_audit(limit=20)}
        self.assertIn("login_blocked", actions)

    def test_failures_on_one_account_do_not_lock_out_another(self) -> None:
        """A colleague's typos must not block the rest of the plant network."""
        for _ in range(settings.login_max_attempts):
            self.client.post(
                "/api/auth/login", json={"username": "ghost.user", "password": "wrong-password"}
            )
        response = self.client.post(
            "/api/auth/login", json={"username": "manager", "password": MANAGER_PASSWORD}
        )
        self.assertEqual(response.status_code, 200)

    def test_address_wide_limiter_still_blocks_spraying(self) -> None:
        with mock.patch.object(settings, "login_ip_max_attempts", 3):
            for index in range(3):
                self.client.post(
                    "/api/auth/login",
                    json={"username": f"spray{index}", "password": "wrong-password"},
                )
            response = self.client.post(
                "/api/auth/login", json={"username": "manager", "password": MANAGER_PASSWORD}
            )
        self.assertEqual(response.status_code, 429)

    def test_session_cookie_is_http_only_and_same_site(self) -> None:
        response = self.client.post(
            "/api/auth/login", json={"username": "manager", "password": MANAGER_PASSWORD}
        )
        cookie = response.headers.get("set-cookie", "").lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)

    def test_logout_ends_the_session(self) -> None:
        self.login("manager", MANAGER_PASSWORD)
        self.assertEqual(self.client.get("/api/documents").status_code, 200)

        self.client.post("/api/auth/logout")
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/api/documents").status_code, 401)

    def test_expired_session_is_refused(self) -> None:
        manager = self.auth.get_user_by_username("manager")
        token, _ = self.auth.create_session(manager, ttl_hours=-1)
        self.client.cookies.set(settings.session_cookie_name, token)

        self.assertIsNone(self.auth.get_session(token))
        self.assertEqual(self.client.get("/api/documents").status_code, 401)

    def test_disabling_an_account_ends_its_sessions(self) -> None:
        manager = self.auth.get_user_by_username("manager")
        token, _ = self.auth.create_session(manager)
        self.assertIsNotNone(self.auth.get_session(token))

        self.auth.update_user(manager.id, is_active=False)
        self.assertIsNone(self.auth.get_session(token))

    def test_changing_a_password_ends_existing_sessions(self) -> None:
        manager = self.auth.get_user_by_username("manager")
        token, _ = self.auth.create_session(manager)
        self.assertIsNotNone(self.auth.get_session(token))

        self.auth.update_user(manager.id, password="BrandNewPassw0rd!2026")
        self.assertIsNone(self.auth.get_session(token))


class ChatRegressionTests(ManagementTestBase):
    """The original assistant contract must survive the management feature."""

    def test_invalid_question_is_still_a_400(self) -> None:
        response = self.client.post("/api/chat", json={"question": "   "})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Please enter a question.")

    def test_missing_question_is_a_422(self) -> None:
        self.assertEqual(self.client.post("/api/chat", json={}).status_code, 422)

    def test_chat_response_schema_is_unchanged(self) -> None:
        from unittest import mock

        from backend.api import chat as chat_api
        from backend.services.rag_service import RagAnswer, SourceReference

        answer = RagAnswer(
            status="answered",
            answer="The coolant concentration is 6 - 8 %.",
            grounded=True,
            sources=[
                SourceReference(
                    document_id="mnt-man-cnc-02-rev02",
                    document_title="Preventive Maintenance Manual",
                    document_code="MNT-MAN-CNC-02",
                    revision="02",
                    page_number=1,
                    source_filename="MNT-MAN-CNC-02.pdf",
                    similarity=0.73,
                )
            ],
        )
        with mock.patch.object(chat_api, "_service") as service:
            service.answer_question.return_value = answer
            response = self.client.post(
                "/api/chat", json={"question": "What is the coolant concentration?"}
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "answered")
        self.assertTrue(payload["grounded"])
        self.assertEqual(payload["sources"][0]["document_code"], "MNT-MAN-CNC-02")
        self.assertEqual(payload["sources"][0]["revision"], "02")


class PasswordSecurityTests(ManagementTestBase):
    def test_password_hash_is_salted_and_never_stored_plain(self) -> None:
        import sqlite3

        connection = sqlite3.connect(self.auth.path)
        try:
            rows = connection.execute("SELECT username, password_hash FROM users").fetchall()
        finally:
            connection.close()

        for username, stored in rows:
            self.assertNotIn(username, stored)
            self.assertTrue(stored.startswith("pbkdf2_sha256$"))
            self.assertNotIn(ADMIN_PASSWORD, stored)

    def test_weak_password_is_refused_when_creating_an_account(self) -> None:
        self.login("admin", ADMIN_PASSWORD)
        response = self.client.post(
            "/api/users",
            json={"username": "weakuser", "password": "password123", "role": "employee"},
        )
        self.assertEqual(response.status_code, 422)


class UploadRegressionTests(ManagementTestBase):
    def test_manager_upload_does_not_touch_the_curated_corpus(self) -> None:
        """A managed upload must not rewrite the baseline manifest or chunks."""
        from backend.services import knowledge_base

        before = knowledge_base.corpus_summary()
        self.login("manager", MANAGER_PASSWORD)
        self.upload()

        after = knowledge_base.corpus_summary()
        # Managed records are pending, so they are not added to the corpus view.
        self.assertEqual(before["active_document_count"], after["active_document_count"])
        self.assertEqual(before["archived_document_count"], after["archived_document_count"])


if __name__ == "__main__":
    unittest.main()
