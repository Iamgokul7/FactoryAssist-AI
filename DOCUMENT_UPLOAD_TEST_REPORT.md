# FactoryAssist AI – Document Upload and Management Test Report

This report records the actual validation results for FactoryAssist AI's document-management functionality. All checks marked **PASS** were executed. Checks that were not executed are explicitly identified in Section 11.

**Project:** FactoryAssist AI
**Validation period:** 10–11 November 2026
**Environment:** Windows, Python virtual environment, `unittest`, FastAPI TestClient, and Chromium browser testing.

---

## 1. Automated Test Summary

The following commands were executed during validation.

```bash
./.venv/Scripts/python.exe -m compileall -q backend tests
./.venv/Scripts/python.exe -m unittest discover -s tests -t .
./.venv/Scripts/python.exe -m pip check
node --check frontend/js/app.js
```

### Results

| Check | Result |
|---|---|
| Python compilation | PASS |
| Automated test suite | PASS — 92 tests |
| Dependency consistency (`pip check`) | PASS |
| JavaScript syntax validation | PASS |

### Test Suite Breakdown

| Test Module | Tests | Result |
|---|---:|---|
| `tests/test_document_management.py` | 37 | PASS |
| `tests/test_access_control.py` | 36 | PASS |
| Existing chatbot and status tests | 19 | PASS |
| **Total** | **92** | **PASS** |

The full test suite completed in approximately 55.3 seconds.

---

## 2. Required Test Matrix

The following matrix maps the required document-management scenarios to their automated tests.

| # | Required Case | Covering Test(s) | Result |
|---:|---|---|---|
| 1 | Successful PDF upload | `test_successful_upload_is_pending_and_indexed` | PASS |
| 2 | Invalid file upload | `test_rejects_non_pdf_content`, `test_rejects_wrong_extension`, `test_rejects_wrong_mime_type`, `test_rejects_missing_file_field` | PASS |
| 3 | Corrupted PDF upload | `test_rejects_corrupted_pdf`, `test_rejected_corrupt_upload_leaves_no_stored_file` | PASS |
| 4 | Empty PDF upload | `test_rejects_empty_pdf` | PASS |
| 5 | PDF without extractable text | `test_rejects_pdf_without_extractable_text` | PASS |
| 6 | Missing or invalid metadata | `test_rejects_missing_metadata`, `test_rejects_invalid_metadata` | PASS |
| 7 | Duplicate upload | `test_rejects_duplicate_revision`, `test_rejects_identical_file_under_new_revision` | PASS |
| 8 | Uploading a new revision | `test_new_revision_stays_pending_while_current_stays_active` | PASS |
| 9 | Successful document processing | `test_successful_upload_is_pending_and_indexed` | PASS |
| 10 | Embedding failure | `test_embedding_failure_marks_failed_and_leaves_no_chunks` | PASS |
| 11 | ChromaDB failure | `test_chroma_failure_marks_failed` | PASS |
| 12 | Processing retry | `test_retry_reprocesses_a_failed_upload`, `test_retry_reuses_existing_embeddings`, `test_retry_is_refused_for_active_documents` | PASS |
| 13 | Pending documents excluded from retrieval | `test_pending_document_is_not_retrievable`, `test_pending_revision_of_active_code_is_not_retrievable` | PASS |
| 14 | Archived documents excluded from retrieval | `test_archived_document_is_not_retrievable` | PASS |
| 15 | Failed documents excluded from retrieval | `test_failed_document_is_not_retrievable` | PASS |
| 16 | Active documents available for retrieval | `test_active_document_is_retrievable` | PASS |
| 17 | Successful revision activation | `test_activation_archives_previous_revision_and_removes_its_chunks` | PASS |
| 18 | Previous revision archived after activation | Same activation test; record status and chunk removal are asserted | PASS |
| 19 | Only one active revision per document code | `test_only_one_active_revision_per_document_code` | PASS |
| 20 | Employee cannot access management APIs | `test_employee_cannot_list_or_upload`, `test_employee_cannot_activate_archive_or_reject`, `test_employee_cannot_read_management_metadata` | PASS |
| 21 | SOP_MANAGER permissions | `test_manager_can_run_the_full_document_lifecycle`, `test_manager_cannot_manage_accounts_or_read_the_audit_log`, `test_manager_cannot_edit_metadata` | PASS |
| 22 | ADMIN permissions | `test_admin_can_manage_accounts`, `test_admin_can_edit_document_metadata`, `test_admin_sees_the_audit_log`, `test_admin_can_force_archive_the_last_active_revision` | PASS |
| 23 | Audit log creation | `test_governance_actions_are_audited_without_secrets`, `test_validation_failure_is_audited`, `test_refused_access_is_audited`, `test_wrong_password_is_rejected_and_audited` | PASS |
| 24 | Existing chatbot API regression | `test_chat_remains_public`, `test_employee_can_still_use_the_chat_endpoint`, `test_invalid_question_is_still_a_400`, `test_missing_question_is_a_422`, `test_chat_response_schema_is_unchanged`, `test_manager_upload_does_not_touch_the_curated_corpus` | PASS |

---

## 3. Additional Security Test Cases

The following security scenarios were also covered.

| Case | Covering Test(s) | Result |
|---|---|---|
| Anonymous management access returns 401 | `test_management_endpoints_require_a_session`, `test_anonymous_upload_is_rejected`, `test_me_reports_an_anonymous_caller` | PASS |
| Employee activation and archival restrictions return 403 | `test_employee_cannot_activate_archive_or_reject` | PASS |
| Oversized PDF rejection | `test_rejects_oversized_upload` | PASS |
| Unrelated document relevance warning | `test_unrelated_document_is_flagged_but_not_auto_rejected` | PASS |
| Rejected document excluded from retrieval | `test_rejected_document_is_not_retrievable` | PASS |
| Rejected revision cannot be activated | `test_rejected_revision_cannot_be_activated` | PASS |
| Archived document excluded from retrieval | `test_archived_document_is_not_retrievable` | PASS |
| Expired session rejection | `test_expired_session_is_refused` | PASS |
| Logout revokes session | `test_logout_ends_the_session` | PASS |
| Disabling account revokes sessions | `test_disabling_an_account_ends_its_sessions` | PASS |
| Password change revokes existing sessions | `test_changing_a_password_ends_existing_sessions` | PASS |
| Session cookie flags | `test_session_cookie_is_http_only_and_same_site` | PASS |
| Missing or invalid CSRF token | `test_mutation_without_csrf_token_is_refused`, `test_mutation_with_wrong_csrf_token_is_refused` | PASS |
| Cross-origin mutation rejection | `test_cross_origin_mutation_is_refused` | PASS |
| Same-origin mutation with valid token | `test_same_origin_with_token_succeeds` | PASS |
| GET requests do not require CSRF token | `test_get_requests_do_not_require_a_csrf_token` | PASS |
| Per-account login rate limiting | `test_repeated_failures_are_rate_limited`, `test_failures_on_one_account_do_not_lock_out_another` | PASS |
| Address-wide login rate limiting | `test_address_wide_limiter_still_blocks_spraying` | PASS |
| Salted password storage | `test_password_hash_is_salted_and_never_stored_plain` | PASS |
| Weak password rejection | `test_weak_password_is_refused_when_creating_an_account` | PASS |
| Last-administrator protection | `test_admin_cannot_demote_the_last_administrator` | PASS |
| Interrupted processing recovery | `test_interrupted_processing_is_recovered_as_failed` | PASS |
| Dashboard status counters | `test_stats_count_each_status` | PASS |
| Last-active-revision archive guard | `test_cannot_archive_the_only_active_revision` | PASS |
| Rejected corrupt upload leaves no stored file | `test_rejected_corrupt_upload_leaves_no_stored_file` | PASS |

---

## 4. Live API Validation

The application was also exercised through HTTP requests against the running application.

The validation covered authentication, authorisation, document upload, document lifecycle operations, retrieval behaviour, and chatbot regression.

### Overall Result

**86 PASS, 1 FAIL, 2 INFO**

The single failed check involved retrieval of a sparse synthetic PDF after activation. The fixture was subsequently replaced with a denser document and the retrieval scenario passed. The failure and retest are documented in Section 5.

### Live Validation Results

| Area | Observed Behaviour | Result |
|---|---|---|
| Account creation | ADMIN, SOP_MANAGER, and EMPLOYEE accounts created successfully; weak passwords rejected with 422 | PASS |
| Login and current-session endpoint | Successful login returned role and CSRF information; incorrect password returned 401 | PASS |
| Anonymous management requests | Protected document, statistics, audit, and user endpoints returned 401 | PASS |
| Employee access | Management operations returned 403 | PASS |
| SOP_MANAGER access | Document lifecycle operations allowed; user and audit access denied | PASS |
| ADMIN access | Account management, audit access, metadata editing, and force archival allowed | PASS |
| CSRF protection | Missing token, incorrect token, and foreign Origin rejected with 403 | PASS |
| Session cookie | HttpOnly and SameSite=Lax flags verified | PASS |
| Valid PDF upload | Returned 201; document entered `pending_review` with four chunks and two pages | PASS |
| Pending document retrieval | Chat returned no sources for the pending document | PASS |
| Incorrect extension or MIME type | Returned 415 | PASS |
| Invalid signature, corrupted, empty, or blank PDF | Returned 400 with readable error messages | PASS |
| Duplicate revision or identical file content | Returned 409 | PASS |
| Invalid revision, metadata, or category | Returned 422 | PASS |
| Oversized upload | Returned 413 | PASS |
| Path traversal filename | Replaced with generated safe filename; no file written outside the upload directory | PASS |
| Revision activation | Returned 200; status changed to active and approval information was recorded | PASS |
| Rejection with reason | Returned 200; reason stored, document excluded from retrieval, later activation refused | PASS |
| Revision 01 to Revision 02 | Previous revision remained active while replacement was pending; activation archived the previous revision | PASS |
| Metadata editing | Manager request returned 403; administrator request returned 200 | PASS |
| Last-active-revision archive guard | Manager request rejected; administrator force archive succeeded | PASS |
| Retry guard | Retry on a non-failed revision rejected with 409 | PASS |
| Logout | Session ended and subsequent management request returned 401 | PASS |
| Session expiry | Expired session rejected with 401 | PASS |
| Password change | Old password rejected, new password accepted, existing sessions revoked | PASS |
| Login rate limiting | 429 returned after five failed attempts for one account | PASS |
| Audit content | Required actions recorded; no passwords, tokens, or key material present | PASS |
| Six original chatbot questions | Expected answers and abstention preserved | PASS |
| Archived `QC-SOP-014 Rev03` | Not retrieved or cited | PASS |
| Pending synthetic documents | Not cited before activation | PASS |
| Swagger HTTP 422 investigation | Malformed JSON and ordinary validation errors reproduced | PASS |

---

## 5. Activation and Searchability Failure: Investigation and Retest

One live validation check initially failed.

After activating a synthetic document revision, a direct chatbot question about that revision returned no sources.

### Root Cause

The first synthetic PDF contained sparse and repetitive text. Its best matching chunk scored below the configured retrieval threshold:

`RETRIEVAL_MIN_SIMILARITY = 0.30`

The retrieval system correctly discarded the low-scoring result.

This was a test-fixture issue rather than evidence of an activation or indexing failure.

### Retest

A denser synthetic PDF was prepared with more meaningful text and a distinctive test value:

`ZQXLIVE905` and `55 newton metres`.

The document was activated through the browser workflow.

The assistant subsequently returned the expected value and cited the correct document code, revision, and page.

A second synthetic document, `QA-LIVE-903 Rev02`, was also retrieved after activation. After the earlier revision was archived, only the active revision was returned.

### Retest Results

| Check | Result |
|---|---|
| Pending revision excluded from citations | PASS |
| Activated revision cited with document code, revision, and page | PASS |
| Only the newest active revision retrieved | PASS |
| Archived revision excluded from retrieval | PASS |

The original failure is retained in the report for transparency.

---

## 6. Swagger HTTP 422 Investigation

A `422 JSON decode error` was observed while testing the account-creation endpoint through Swagger.

The behaviour was investigated using the following requests.

| Request | Response |
|---|---|
| POST `/api/users` with truncated JSON | 422 JSON decode error |
| POST `/api/users` with valid JSON | 201 account created |
| POST `/api/users` with an existing username | 422 validation error |
| POST `/api/users` with a short password | 422 validation error |

### Conclusion

The JSON decode error was caused by malformed JSON submitted through the Swagger request editor.

The other 422 responses were expected validation behaviour for duplicate usernames and weak passwords.

No application code change was required for this issue.

The endpoint and request schema are documented in `ADMIN_SETUP_GUIDE.md`.

---

## 7. Defects Found and Fixed During Validation

The following issues were identified during live testing and corrected.

| Defect | Observed Behaviour | Fix | Verification |
|---|---|---|---|
| Login lockout was too broad | Failed attempts against one account could block other accounts sharing the same address | Added separate per-account and address-wide counters | Automated rate-limit tests and live login checks passed |
| Signed-out header displayed Sign out | Existing button CSS overrode the HTML `hidden` attribute | Added `[hidden] { display: none !important; }` to the global stylesheet | Computed-style check confirmed hidden controls were not displayed |
| Rejected corrupt upload left an orphan file | A Windows file-handle issue prevented cleanup | Changed PDF validation to open from memory and added retry-based file cleanup | Corrupt upload returned 400 and left no stored file |
| Dashboard counters became stale | Chunk count did not refresh immediately after upload or activation | Triggered status refresh after upload and governance actions | Header updated without requiring a manual page reload |

---

## 8. Browser Walkthrough

The management interface was tested through a Chromium browser session using real DOM interactions.

The walkthrough covered the main user journeys.

| Screen or Action | Observed Behaviour | Result |
|---|---|---|
| Signed-out dashboard | Chat and knowledge base available; management navigation hidden | PASS |
| Sign-in | Manager authenticated through the login form; name and role displayed | PASS |
| Document Management | Five dashboard counters and role-appropriate register actions displayed | PASS |
| Upload form | Form opened and closed correctly; required fields and PDF-only guidance displayed | PASS |
| Drag and drop | Selected PDF appeared in the upload area | PASS |
| Client-side validation | Incomplete form submission displayed a validation message without sending a request | PASS |
| Upload progress and result | Upload completed; document appeared as Pending Review | PASS |
| Search | Searching for `QA-LIVE-903` filtered the register to its revisions | PASS |
| Status filters | Active, Pending, Archived, Rejected, and Failed filters worked | PASS |
| Document details | Metadata, page and chunk counts, uploader, revision history, and warnings displayed | PASS |
| Activation | Confirmation completed; document moved to Active | PASS |
| Chat after activation | Newly activated revision was cited with its document code and page | PASS |
| New revision upload | New revision processed while the previous revision remained active | PASS |
| Archive | Revision archived and audit information updated | PASS |
| Reject with reason | Rejection reason recorded and visible in the audit trail | PASS |
| Sign-out | Session ended and management navigation disappeared | PASS |
| Employee session | Management navigation absent; protected management endpoints denied; chat remained available | PASS |
| Administrator session | Audit panel displayed management events without exposing secrets | PASS |
| Knowledge Base and System Info | Both views rendered successfully for an authenticated employee | PASS |
| Responsive layout | Mobile layout at 390 × 844 and desktop layout at 1440 px verified | PASS |
| Browser console | No unexpected JavaScript exceptions observed | PASS |

### Responsive Layout

At a viewport of 390 × 844:

- Sidebar collapsed into a menu button.
- Document detail modal fitted within the viewport.
- Text remained readable.

At a viewport of 1440 px:

- No horizontal overflow was observed.
- Sidebar width measured approximately 246 px.
- Main content width measured approximately 1177 px.

### Evidence Availability

The original validation run generated screenshots under the local `screenshots/validation-*` path.

These are validation artifacts from the test environment and are not assumed to be included in the public repository. The current public demo screenshots and recording are separate assets.

The browser walkthrough results above are the recorded validation evidence; the public demo video does not show every management operation.

---

## 9. Real-Embedding Validation

A separate embedding test was performed using temporary storage so the original curated knowledge base remained untouched.

A PDF was uploaded through `DocumentManager` using the real Gemini embedding service.

| Observation | Result |
|---|---|
| Upload completed with `pending_review` status | PASS |
| Chunk count and page metadata recorded | PASS |
| Similarity search filtered to `pending_review` | PASS — one hit, score 0.721 |
| Same query filtered to `active` | PASS — zero hits |
| Stored embedding dimension | PASS — 3072, matching `gemini-embedding-001` |

This confirmed that a pending document could be embedded and indexed without becoming available to active retrieval.

---

## 10. Chatbot Regression: Six Original Questions

The original chatbot behaviour was revalidated after implementing document management.

| # | Question | Observed Result | Status |
|---:|---|---|---|
| 1 | Coolant concentration for the CNC machine | 6–8%, `MNT-MAN-CNC-02` Rev02, page 1 | PASS |
| 2 | What to do when AL-104 appears | Top up ISO VG 68 way lube oil to MAX and press RESET, Rev02, page 2 | PASS |
| 3 | Who removes a lock during LOTO | Each authorised person removes only their own lock, `SAF-SOP-003` Rev05, page 1 | PASS |
| 4 | OD tolerance for BH-220 | ±0.050 mm, `QC-SOP-014` Rev04, page 2 | PASS |
| 5 | Spindle runout frequency and owner | Monthly, maintenance technician, `MNT-MAN-CNC-02` Rev02, page 1 | PASS |
| 6 | Annual factory electricity consumption | Correctly abstained with zero sources | PASS |

Archived `QC-SOP-014 Rev03` did not appear in any answer or citation.

One live question initially encountered a transient Gemini 503 response and succeeded on retry. This was an upstream service availability issue.

After temporary synthetic documents were retired, the original baseline was restored:

- 15 indexed chunks.
- 3 active documents.
- 1 archived revision.

---

## 11. Failure Handling and Not-Run Items

### Failure Handling Verified

| Scenario | Observed Behaviour |
|---|---|
| Gemini embedding failure | Document marked `FAILED`; safe error message stored; no active chunks left behind |
| Chroma write failure during upload | Document marked `FAILED`; retrieval restricted to active documents |
| Process interrupted during processing | Next application start marks interrupted `PROCESSING` records as failed |
| Rejected or corrupted upload | Stored file removed where applicable; failed attempt audited |
| Uploader-facing error | Short user-facing message returned without exposing internal exception details or filesystem paths |

### Not Run

The following items were not validated in this build.

| Item | Reason | Remaining Work |
|---|---|---|
| OCR for scanned PDFs | OCR is not implemented; scanned documents are rejected | Add OCR support if required |
| Multi-process or multi-worker deployment | Activation currently relies on an in-process lock | Introduce shared locking or database-level coordination before scaling out |
| Load and large-file performance testing | Not included in the validation scope | Run performance tests using large manuals and concurrent uploads |
| Session expiry through the full browser UI | Waiting for the default eight-hour expiry was not practical | Perform an end-to-end UI expiry test if required |

These items should not be interpreted as completed or production-validated capabilities.

---

## 12. Existing Data and Cleanup

The validation process preserved the original curated knowledge base.

The following conditions were confirmed after testing:

- The baseline of 15 active chunks, 3 active documents, and 1 archived revision was restored.
- Temporary `QA-LIVE-*` document records, chunks, and stored files created for validation were removed.
- The upload directory was empty after cleanup.
- Curated files under `data/knowledge_base/` were not modified.
- The automated test `test_manager_upload_does_not_touch_the_curated_corpus` verifies that managed uploads do not alter the curated corpus.

Validation also created temporary accounts and audit records.

- Two validation accounts, one SOP_MANAGER and one EMPLOYEE, remained after the run.
- Their randomly generated passwords were not retained.
- The temporary administrator used for validation was disabled.
- The plant administrator account was not modified.
- Audit records from validation were retained as evidence. They contain usernames, actions, and document keys, not credentials.

For a local environment where those validation accounts still exist, an administrator can reset an account password through:

```bash
python -m backend.services.auth_store reset-password --username <name>
```

Review the account list and audit records before using a shared or production environment.

---

**End of Report**