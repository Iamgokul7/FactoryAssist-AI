# Document upload and management test report

Actual results. Everything marked PASS was executed in this environment; anything
not executed is marked NOT RUN and listed in §9.

Environment: Windows, Python from `.venv`, `unittest`, FastAPI `TestClient`,
temporary data directories. Live checks ran against the real application on
`http://127.0.0.1:8000` with the real Chroma collection and the real Gemini key;
the browser walkthrough used a Chromium session against that same server.

Date of this run: 2026-11-10 / 2026-11-11.

Commands and final results:

```bash
./.venv/Scripts/python.exe -m compileall -q backend tests            # exit 0
./.venv/Scripts/python.exe -m unittest discover -s tests -t .        # Ran 92 tests ... OK (55.3 s)
./.venv/Scripts/python.exe -m pip check                              # No broken requirements found.
node --check frontend/js/app.js                                      # exit 0
```

Suite breakdown:

| Module | Tests | Result |
| --- | --- | --- |
| `tests/test_document_management.py` | 37 | OK |
| `tests/test_access_control.py` | 36 | OK |
| Pre-existing suite (`test_gemini_integration`, `test_status_availability`) | 19 | OK |
| **Total** | **92** | **OK (55.3 s)** |

---

## 1. Required test matrix

Each row is one required case from the brief, the test(s) that cover it and the
observed result.

| # | Required case | Covering test(s) | Result |
| --- | --- | --- | --- |
| 1 | Successful PDF upload | `test_successful_upload_is_pending_and_indexed` | PASS |
| 2 | Invalid file upload | `test_rejects_non_pdf_content`, `test_rejects_wrong_extension`, `test_rejects_wrong_mime_type`, `test_rejects_missing_file_field` | PASS |
| 3 | Corrupted PDF upload | `test_rejects_corrupted_pdf`, `test_rejected_corrupt_upload_leaves_no_stored_file` | PASS |
| 4 | Empty PDF upload | `test_rejects_empty_pdf` | PASS |
| 5 | PDF with no extractable text | `test_rejects_pdf_without_extractable_text` | PASS |
| 6 | Missing required metadata | `test_rejects_missing_metadata`, `test_rejects_invalid_metadata` | PASS |
| 7 | Duplicate upload | `test_rejects_duplicate_revision`, `test_rejects_identical_file_under_new_revision` | PASS |
| 8 | Uploading a new revision | `test_new_revision_stays_pending_while_current_stays_active` | PASS |
| 9 | Successful document processing | `test_successful_upload_is_pending_and_indexed` (status, chunk count, page metadata) | PASS |
| 10 | Failed embedding operation | `test_embedding_failure_marks_failed_and_leaves_no_chunks` | PASS |
| 11 | Failed ChromaDB operation | `test_chroma_failure_marks_failed` | PASS |
| 12 | Processing retry | `test_retry_reprocesses_a_failed_upload`, `test_retry_reuses_existing_embeddings`, `test_retry_is_refused_for_active_documents` | PASS |
| 13 | Pending documents excluded from retrieval | `test_pending_document_is_not_retrievable`, `test_pending_revision_of_active_code_is_not_retrievable` | PASS |
| 14 | Archived documents excluded from retrieval | `test_archived_document_is_not_retrievable` | PASS |
| 15 | Failed documents excluded from retrieval | `test_failed_document_is_not_retrievable` | PASS |
| 16 | Active documents available for retrieval | `test_active_document_is_retrievable` | PASS |
| 17 | Successful revision activation | `test_activation_archives_previous_revision_and_removes_its_chunks` | PASS |
| 18 | Previous revision archived after activation | same test (record status and chunk removal both asserted) | PASS |
| 19 | Only one active revision per document ID | `test_only_one_active_revision_per_document_code` | PASS |
| 20 | Employee cannot access management APIs | `test_employee_cannot_list_or_upload`, `test_employee_cannot_activate_archive_or_reject`, `test_employee_cannot_read_management_metadata` | PASS |
| 21 | SOP_MANAGER permissions | `test_manager_can_run_the_full_document_lifecycle`, `test_manager_cannot_manage_accounts_or_read_the_audit_log`, `test_manager_cannot_edit_metadata` | PASS |
| 22 | ADMIN permissions | `test_admin_can_manage_accounts`, `test_admin_can_edit_document_metadata`, `test_admin_sees_the_audit_log`, `test_admin_can_force_archive_the_last_active_revision` | PASS |
| 23 | Audit log creation | `test_governance_actions_are_audited_without_secrets`, `test_validation_failure_is_audited`, `test_refused_access_is_audited`, `test_wrong_password_is_rejected_and_audited` | PASS |
| 24 | Existing chatbot API regression | `test_chat_remains_public`, `test_employee_can_still_use_the_chat_endpoint`, `test_invalid_question_is_still_a_400`, `test_missing_question_is_a_422`, `test_chat_response_schema_is_unchanged`, `test_manager_upload_does_not_touch_the_curated_corpus` | PASS |

## 2. Additional security cases from the security brief

| Case | Covering test(s) | Result |
| --- | --- | --- |
| Anonymous management access (401) | `test_management_endpoints_require_a_session`, `test_anonymous_upload_is_rejected`, `test_me_reports_an_anonymous_caller` | PASS |
| Employee activation / archival refusal (403) | `test_employee_cannot_activate_archive_or_reject` | PASS |
| Oversized PDF | `test_rejects_oversized_upload` | PASS |
| Unrelated / non-manufacturing document | `test_unrelated_document_is_flagged_but_not_auto_rejected` | PASS |
| Rejected document not retrievable | `test_rejected_document_is_not_retrievable` | PASS |
| Rejected revision cannot be activated | `test_rejected_revision_cannot_be_activated` | PASS |
| Archived document not retrievable | `test_archived_document_is_not_retrievable` | PASS |
| Session expiry | `test_expired_session_is_refused` | PASS |
| Session revocation (logout, disable, password change) | `test_logout_ends_the_session`, `test_disabling_an_account_ends_its_sessions`, `test_changing_a_password_ends_existing_sessions` | PASS |
| Cookie flags | `test_session_cookie_is_http_only_and_same_site` | PASS |
| CSRF (missing token, wrong token, cross-origin) | `test_mutation_without_csrf_token_is_refused`, `test_mutation_with_wrong_csrf_token_is_refused`, `test_cross_origin_mutation_is_refused`, `test_same_origin_with_token_succeeds`, `test_get_requests_do_not_require_a_csrf_token` | PASS |
| Login rate limiting, per account | `test_repeated_failures_are_rate_limited`, `test_failures_on_one_account_do_not_lock_out_another` | PASS |
| Login rate limiting, address-wide | `test_address_wide_limiter_still_blocks_spraying` | PASS |
| Password storage | `test_password_hash_is_salted_and_never_stored_plain`, `test_weak_password_is_refused_when_creating_an_account` | PASS |
| Last-administrator protection | `test_admin_cannot_demote_the_last_administrator` | PASS |
| Interrupted processing recovery | `test_interrupted_processing_is_recovered_as_failed` | PASS |
| Dashboard counters | `test_stats_count_each_status` | PASS |
| Only-active-archive guard | `test_cannot_archive_the_only_active_revision` | PASS |
| Rejected upload leaves no stored file | `test_rejected_corrupt_upload_leaves_no_stored_file` | PASS |

## 3. Live validation against the running application

Server: `backend.main:app` on `http://127.0.0.1:8000`, real `.env`, real Chroma
collection, real Gemini calls. A temporary harness drove the public HTTP API
exactly as the frontend does (cookie session, CSRF header, Origin header) and
created its own randomly generated accounts; passwords were kept in memory and a
temp file for the browser step, never printed here.

Result: **86 PASS, 1 FAIL, 2 INFO**. The single FAIL is explained in §4 and was
retested successfully.

| Area | Observed | Result |
| --- | --- | --- |
| Account creation via `POST /api/users` | 201 for ADMIN, SOP_MANAGER and EMPLOYEE accounts; weak passwords rejected 422 | PASS |
| Login / `/api/auth/me` | 200 with role and CSRF token; wrong password 401 | PASS |
| Anonymous management calls | `/api/documents`, `/api/documents/stats`, `/api/audit`, `/api/users` all 401 | PASS |
| Employee calls | upload, list, stats, audit, users, activate, reject, archive, retry, metadata all 403 | PASS |
| Manager calls | users and audit 403; document lifecycle 200 | PASS |
| Admin calls | users, audit, metadata PATCH, force archive all 200 | PASS |
| CSRF | missing token 403, wrong token 403, foreign `Origin` 403 | PASS |
| Cookie flags | `HttpOnly`, `SameSite=Lax`, no `Secure` on plain HTTP | PASS |
| Valid upload | 201, `pending_review`, 4 chunks, 2 pages, stored under a generated name | PASS |
| Pending not searchable | chat for that code returned no sources | PASS |
| Wrong extension / wrong MIME | 415 | PASS |
| Bad signature / corrupt / zero-page / blank PDF | 400 with a readable message | PASS |
| Duplicate revision / identical bytes | 409 | PASS |
| Invalid revision, metadata, category | 422 | PASS |
| Oversized upload | 413 | PASS |
| Path traversal in filename | neutralised to a generated safe name; no file written outside `documents/uploads` | PASS |
| Activation | 200, status `active`, `approved_by` recorded, audit event written | PASS |
| Reject with reason | 200, status `rejected`, reason stored, not searchable, activation refused 409 | PASS |
| Revision 01 → 02 | 01 stayed active while 02 was pending; after activating 02, 01 became `archived`; exactly one active | PASS |
| Manager metadata edit | 403; ADMIN 200 | PASS |
| Archive guard | manager archiving the last active revision 409; ADMIN force archive 200; not searchable afterwards | PASS |
| Retry guard | retry on a non-failed revision 409 | PASS |
| Logout | 200, session cookie cleared, next management call 401 | PASS |
| Session expiry | expired session row → 401 | PASS |
| Password change | old password 401, new password 200, old sessions revoked | PASS |
| Rate limiting | 429 after five failed attempts for one account (limit fixed during this run, see §6) | PASS |
| Audit content | all required actions present; no passwords, tokens or key material | PASS |
| Six original questions | all correct, including the abstention; citations correct | PASS |
| Archived QC-SOP-014 Rev 03 | never cited or retrieved | PASS |
| Synthetic documents in chat | never cited before activation | PASS |
| HTTP 422 reported in Swagger | reproduced as malformed JSON, not an application defect (§5) | PASS |

## 4. The activation-searchability FAIL and its retest

One check failed: after activating a synthetic revision, a direct chat question
about it returned no sources. The cause was the fixture, not the pipeline: the
first synthetic PDF repeated its text so sparsely that Chroma scored the best
chunk below `RETRIEVAL_MIN_SIMILARITY = 0.30`, so retrieval correctly discarded
it.

Reproduced with a denser fixture (`ZQXLIVE905 … 55 newton metres`, ~5 000
characters) activated through the browser: the assistant answered
"…55 newton metres … (QA-LIVE-905, Revision 01)" and cited the correct revision
and page. A second document (`QA-LIVE-903` Rev 02) was also cited after
activation, and after archiving Rev 01 only Rev 02 was returned.

| Check | Result |
| --- | --- |
| Pending revision is not cited | PASS |
| Activated revision is cited with code, revision and page | PASS |
| After activation, only the newest active revision is cited | PASS |
| Archived revision is no longer cited | PASS |

## 5. The HTTP 422 "JSON decode error" from Swagger

Investigated against the running server with the ADMIN session:

| Request | Response |
| --- | --- |
| `POST /api/users` with `{"username": "broken", ` (truncated JSON) | 422 `JSON decode error` |
| `POST /api/users` with a valid body | 201, account created |
| `POST /api/users` with an existing username | 422 validation error on the field |
| `POST /api/users` with a short password | 422 validation error on the field |

Conclusion: the 422 came from malformed JSON sent by the client (an unfinished
edit in the Swagger body editor), and from ordinary Pydantic validation on
duplicates/weak input. It is not an application defect; no code change was
needed. The route, body schema and error shape are documented in
`ADMIN_SETUP_GUIDE.md` §3.

## 6. Bugs found during live validation and fixed

| Bug | Symptom | Fix | Verification |
| --- | --- | --- | --- |
| Login lockout was address-wide | Five failures on one account made every account from the same IP return 429, because the limiter counted failures only by `username+IP` and any login from that IP matched | Per-account counter (5, `LOGIN_RATE_LIMIT_ATTEMPTS`) plus a separate address-wide counter (20, new `LOGIN_IP_MAX_ATTEMPTS`); both checked on login and both audited | Two new tests: `test_failures_on_one_account_do_not_lock_out_another`, `test_address_wide_limiter_still_blocks_spraying`; live login as a different account succeeded |
| Signed-out header still showed "Sign out" | `.btn { display: inline-flex }` overrode the `hidden` attribute, so hidden controls stayed visible | Global `[hidden] { display: none !important; }` in `frontend/css/styles.css` | Computed style check: `display: none` when signed out; screenshot `screenshots/validation-dashboard-anon-fixed.png` |
| Rejected corrupt upload left an orphan file | `Could not remove rejected upload: PermissionError` in `server.log`; a `qa-bad-04…pdf` stayed in `documents/uploads/` on Windows | PDF validation now opens from memory (`pymupdf.open(stream=…)`) so no handle is held, and `_remove_quietly` retries five times with a short backoff | Live corrupt upload returned 400 and left the uploads directory empty; regression test `test_rejected_corrupt_upload_leaves_no_stored_file` |
| Stale counters after an action | The header still showed the old chunk count after upload/activation until a manual refresh | `loadStatus()` called after upload and after governance actions | Header changed to "26 chunks indexed" immediately after activation, without a reload |

## 7. Browser walkthrough (real Chromium against the live server)

The whole UI was driven with real DOM events on `http://127.0.0.1:8000`; native
`confirm()`/`prompt()` dialogs were answered in-page because the automation
dismisses browser modals.

| Screen / action | Observed | Result |
| --- | --- | --- |
| Dashboard while signed out | Chat and knowledge base available; sign-out button hidden after the CSS fix; no management nav | PASS |
| Sign in | Manager logged in through the form; header showed name and role | PASS |
| Document Management | Five KPI counters (total, active, pending, archived, failed), register rows with role-appropriate actions, no audit panel for a manager | PASS |
| Upload form | Opens, hides, shows drop zone, required-field markers and the PDF-only hint | PASS |
| Drag and drop | A real `DataTransfer` drop showed `qa-live-905-rev02.pdf · 0.00 MB` | PASS |
| Client validation | Submitting an incomplete form showed "Fill in every required field marked with *." and no request was sent | PASS |
| Upload progress + result | Real upload processed; toast "QA-LIVE-905 Rev 01 processed and is awaiting review…"; row appeared as Pending review | PASS |
| Search | Typing `QA-LIVE-903` reduced the register to its two revisions | PASS |
| Status filters | Chips filtered to Active/Pending/Archived/Rejected/Failed and marked themselves selected | PASS |
| Document details | Modal showed metadata, page/chunk counts, uploader, approval/archival fields, original filename, description, relevance warning and revision history | PASS |
| Activate | Confirmed in-page; toast "QA-LIVE-905 Rev 01 is now active…"; row moved to Active | PASS |
| Chat after activation | The new revision was cited with code, revision 01 and page 1 | PASS |
| Upload revision 02 | Processed while Rev 01 stayed Active | PASS |
| Archive | Rev 01 archived by the manager while Rev 02 was pending; record and audit updated | PASS |
| Reject with reason | Prompt reason stored; row moved to Rejected; reason visible in the audit trail | PASS |
| Sign out | Session ended; management nav and sign-out button disappeared | PASS |
| Employee session | Document Management nav absent; `/api/documents` and `/api/audit` returned 403 in the page; chat still answered | PASS |
| Admin session | Audit panel rendered 50 records including login, upload, processing, rejection, activation and archival, with no secrets | PASS |
| Knowledge Base and System Info | Both rendered for a signed-in employee | PASS |
| Responsive layout | At 390 × 844 the sidebar collapses to a menu button, the detail modal fits the viewport and text is readable; at 1440 px there is no horizontal overflow (sidebar 246 px, main 1177 px) | PASS |
| Console | Only the deliberate 429 (before the limiter fix) and the deliberate 403 probes; no JavaScript exceptions | PASS |

Evidence images: `screenshots/validation-dashboard-anon.png`,
`validation-dashboard-anon-fixed.png`, `validation-register-manager.png`,
`validation-detail-modal.png`, `validation-detail-mobile.png`.

**Limitation of the evidence:** the embedded browser panel is narrower than the
page, so `validation-register-manager.png` is cropped to the left ~380 px;
desktop layout was therefore verified with measured layout metrics
(`scrollWidth === clientWidth`, sidebar and main widths) rather than from that
image.

## 8. Real-embedding validation (temporary directories, real Gemini API)

A PDF was uploaded through `DocumentManager` in a temporary store, so the live
corpus was untouched.

| Observation | Result |
| --- | --- |
| Upload completes with status `pending_review` | PASS |
| Chunk count / page metadata | 1 chunk, page recorded | PASS |
| Similarity search filtered to `pending_review` | 1 hit, score 0.721 | PASS |
| Same query filtered to `active` | 0 hits | PASS |
| Stored embedding dimension | 3072, matching `gemini-embedding-001` | PASS |

## 9. Chatbot regression — the six original questions

| # | Question | Observed | Result |
| --- | --- | --- | --- |
| 1 | Coolant concentration for the CNC machine | 6–8 %, `MNT-MAN-CNC-02` Rev 02, p. 1 | PASS |
| 2 | What to do when AL-104 appears | Top up ISO VG 68 way lube oil to MAX and press RESET, Rev 02, p. 2 | PASS |
| 3 | Who removes a lock during LOTO | Each authorised person removes only their own lock, `SAF-SOP-003` Rev 05, p. 1 | PASS |
| 4 | OD tolerance for BH-220 | ±0.050 mm, `QC-SOP-014` Rev 04, p. 2 | PASS |
| 5 | Spindle runout frequency and owner | Monthly, maintenance technician, `MNT-MAN-CNC-02` Rev 02, p. 1 | PASS |
| 6 | Annual factory electricity consumption | Abstained, 0 sources | PASS |

Archived `QC-SOP-014` Rev 03 did not appear in any answer or citation. During the
live run one question returned a transient Gemini `503` and succeeded on retry;
that is upstream availability, not an application defect.

After all synthetic documents were retired, `GET /api/status` reports
**15 indexed chunks, 3 active documents, 1 archived revision** — the baseline.

## 10. Failure handling observed

| Scenario | Behaviour |
| --- | --- |
| Gemini embedding outage | Document becomes `failed`, safe message stored, no chunks left behind |
| Chroma write failure mid-upload | Document becomes `failed`; retrieval requires `document_status=active` |
| Process killed mid-processing | Next start marks `PROCESSING` records failed |
| Rejected/corrupted upload | File removed (with retries), no record created, attempt audited |
| Uploader error message | Short, user-facing text; exception classes and paths never reach the client |

## 11. Not run

| Item | Why | What remains |
| --- | --- | --- |
| OCR for scanned PDFs | Not implemented; scanned files are rejected with a clear message | Out of scope for this build |
| Multi-process / multi-worker deployment | Design assumes one process holding the document lock | Run one Uvicorn worker, or add a real lock store before scaling out |
| Load or large-file performance testing | Not requested; a 25 MB cap exists | Upload a large manual and watch latency |
| Session-expiry flow through the UI | Would require waiting 8 hours; expiry was verified by expiring the session row at API level | Optional |

## 12. Notes on the existing data

- Baseline of 15 active chunks, 3 active documents and 1 archived revision is
  intact; every `QA-LIVE-*` record, chunk and stored file created for this
  validation was removed and the uploads directory is empty.
- Curated `data/knowledge_base/` files were not modified; no test writes into
  them (`test_manager_upload_does_not_touch_the_curated_corpus`).
- Accounts created for validation: `sop.manager.test` (SOP_MANAGER) and
  `employee.test` (EMPLOYEE) remain, with randomly generated passwords that were
  not recorded; reset either with
  `python -m backend.services.auth_store reset-password --username <name>`.
  The extra administrator `admin.validation` used for the ADMIN flows has been
  **disabled**; `plant.admin` was never modified.
- Audit rows from the validation run are retained as evidence; they contain
  usernames, actions and document keys, never credentials.
