# FactoryAssist AI – Document Management Implementation Report

This report describes the document-management functionality implemented in FactoryAssist AI, how it integrates with the existing architecture, the validation performed, and the limitations that remain.

**Project:** FactoryAssist AI
**Stage:** 7 – Document Management
**Report date:** 11 November 2026

---

## 1. Features Implemented

### Dashboard and Document Register

- Added a Document Management screen to the existing application sidebar, following the established design system.
- Added dashboard counters for total, active, pending-review, archived, and failed documents.
- Implemented a searchable and filterable document register.
- Added document details with metadata, processing information, PDF downloads, revision history, warnings, and role-dependent actions.

### Document Upload

- Implemented drag-and-drop and file-browser upload.
- Added an XMLHttpRequest-based upload progress indicator.
- Added a metadata form containing document code, revision, title, department, category, effective date, and description.
- Implemented server-side validation covering:
  - File extension and MIME type.
  - PDF signature (`%PDF-`).
  - Configured file-size limit.
  - PDF readability through PyMuPDF.
  - Page count and extractable text.
  - Document-code and revision formats.
  - Duplicate document-code and revision combinations.
  - Identical file content.
  - Duplicates of documents already present in the curated assignment corpus.
- Generated safe, unique storage filenames using the format:

  `\<code>-rev\<NN>-<8 hex>.pdf`

- Stored uploaded documents under `Documents/uploads/`.
- Avoided using client-supplied filenames as filesystem paths.
- Reused the existing ingestion pipeline:

  `pdf_processor.extract_document` → `text_chunker.chunk_document` → `EmbeddingService` → `VectorStore`

### Document Governance

Implemented the following document statuses:

- `PROCESSING`
- `PENDING_REVIEW`
- `ACTIVE`
- `ARCHIVED`
- `REJECTED`
- `FAILED`

Only documents with the `ACTIVE` status are eligible for retrieval.

The management workflow supports:

- Document activation and approval.
- Rejection with an optional reason.
- Archiving.
- Retrying failed uploads.
- Metadata editing by administrators.
- Revision history by document code.
- A keyword-based manufacturing-relevance indicator.

The activation routine enforces a single active revision per document code.

### Authentication and Security

- Implemented password hashing using PBKDF2-HMAC-SHA256 with 600,000 iterations and per-password salts.
- Implemented opaque session tokens stored as SHA-256 fingerprints.
- Configured session cookies with:
  - `HttpOnly`
  - `SameSite=Lax`
  - `Secure` when using HTTPS
  - Configurable expiration
- Implemented session revocation on logout, password changes, role changes, and account disabling.
- Added per-session CSRF tokens for mutation requests.
- Added Origin/Host validation.
- Implemented login rate limiting using failed-login audit records:
  - Five failed attempts per account.
  - Twenty failed attempts per client address within the configured window.
- Implemented three server-enforced roles:
  - `ADMIN`
  - `SOP_MANAGER`
  - `EMPLOYEE`
- Protected management endpoints against anonymous and unauthorised access.
- Added security response headers to reduce common browser-side risks.

Unauthenticated requests receive `401` responses, while authenticated users without the required permissions receive `403` responses.

### Audit Trail

Implemented a SQLite-backed audit trail covering:

- Successful and failed sign-in attempts.
- Sign-out events.
- Upload attempts and validation failures.
- Document-processing results.
- Review and approval actions.
- Activation and archival.
- Metadata changes.
- Account and role changes.
- Refused management requests.

Passwords, session tokens, and API keys are not written to the audit log.

---

## 2. Existing Files Modified

| File | Changes |
|---|---|
| `backend/main.py` | Managed-directory initialisation, optional administrator bootstrap, interrupted-upload recovery, router registration, and security-header middleware |
| `backend/core/config.py` | Managed data directory, upload directory, upload-size limit, session TTL, cookie settings, rate-limit configuration, and administrator bootstrap settings |
| `backend/services/vector_store.py` | Added document-management helpers, including `count(where)`, `metadata_for_document`, `delete_by_document`, `set_document_status`, `update_chunk_metadata`, and `managed_chunk_ids` |
| `backend/services/knowledge_base.py` | Merged managed document records into the manifest view so managed revisions supersede corresponding manifest entries |
| `backend/services/ingestion_service.py` | Prevented CLI ingestion from deleting chunks that it does not own |
| `backend/api/health.py` | Added live active-chunk reporting and Stage 7 information |
| `frontend/index.html` | Added sidebar navigation, authentication controls, document-management view, upload form, register, audit panel, login and detail modals, notifications, and API information |
| `frontend/js/app.js` | Added session and CSRF handling, upload progress, register rendering, filtering, document details, revision history, lifecycle actions, audit view, and notifications |
| `requirements.txt` | Added `python-multipart` for form uploads |
| `.env.example` | Added configuration settings with placeholders only |
| `.gitignore` | Added managed data and uploaded-document storage exclusions |
| `README.md` | Updated project documentation and feature information |
| `THINKING.md` | Added document-management architecture decisions |
| `DEMO_SCRIPT.md` | Updated the demonstration script |

The new management-screen styles are located in:

`frontend/css/management.css`

The existing stylesheet, `frontend/css/styles.css`, also received a visibility fix:

```css
[hidden] {
    display: none !important;
}
```

This prevents the existing button display styling from overriding the HTML `hidden` attribute and exposing signed-out controls.

---

## 3. New Files

| File | Purpose |
|---|---|
| `backend/core/security.py` | Password hashing, verification, password policy, token generation, token hashing, and constant-time comparison |
| `backend/services/auth_store.py` | SQLite account, session, audit, rate-limit, and administrator-bootstrap functionality; includes account-management CLI commands |
| `backend/services/management_store.py` | Document statuses, categories, document records, atomic JSON writes, revision handling, counters, and public document views |
| `backend/services/document_manager.py` | Document validation, PDF inspection, ingestion, retry, activation, archival, rejection, metadata management, and crash recovery |
| `backend/api/deps.py` | Session resolution, manager and administrator dependencies, CSRF validation, Origin checks, and shared authentication dependencies |
| `backend/api/auth.py` | Login, logout, current-session information, password changes, account-management routes, and audit endpoint |
| `backend/api/documents.py` | Document register, statistics, metadata, upload, detail, status, revision, file, activation, archival, rejection, retry, and metadata routes |
| `frontend/css/management.css` | Styling for the document-management interface |
| `tests/helpers.py` | Shared test utilities and temporary-environment setup |
| `tests/test_document_management.py` | Document-management workflow tests |
| `tests/test_access_control.py` | Authentication, authorisation, and access-control tests |
| `DOCUMENT_MANAGEMENT_GUIDE.md` | Manager-facing document lifecycle guide |
| `ADMIN_SETUP_GUIDE.md` | Administrator setup and account-management guide |
| `DOCUMENT_UPLOAD_TEST_REPORT.md` | Detailed document-management validation results |

---

## 4. API Endpoints

The following endpoints were added for authentication and document management.

| Method | Endpoint | Access |
|---|---|---|
| POST | `/api/auth/login` | Public; rate limited |
| POST | `/api/auth/logout` | Authenticated session + CSRF |
| GET | `/api/auth/me` | Public; reports anonymous or authenticated state |
| POST | `/api/auth/change-password` | Authenticated session + CSRF |
| GET | `/api/users` | ADMIN |
| POST | `/api/users` | ADMIN |
| PATCH | `/api/users/{user_id}` | ADMIN |
| GET | `/api/audit` | ADMIN |
| GET | `/api/documents` | ADMIN, SOP_MANAGER |
| GET | `/api/documents/stats` | ADMIN, SOP_MANAGER |
| GET | `/api/documents/meta` | ADMIN, SOP_MANAGER |
| POST | `/api/documents/upload` | ADMIN, SOP_MANAGER |
| GET | `/api/documents/{key}` | ADMIN, SOP_MANAGER |
| GET | `/api/documents/{key}/status` | ADMIN, SOP_MANAGER |
| GET | `/api/documents/{key}/revisions` | ADMIN, SOP_MANAGER |
| GET | `/api/documents/{key}/file` | ADMIN, SOP_MANAGER |
| POST | `/api/documents/{key}/activate` | ADMIN, SOP_MANAGER |
| POST | `/api/documents/{key}/archive` | ADMIN, SOP_MANAGER; ADMIN required to archive the last active revision |
| POST | `/api/documents/{key}/reject` | ADMIN, SOP_MANAGER |
| POST | `/api/documents/{key}/retry` | ADMIN, SOP_MANAGER |
| PATCH | `/api/documents/{key}` | ADMIN |

Here, `{key}` represents a document revision record ID, for example:

`qc-sop-014-rev05`

Existing chatbot and status endpoints were retained.

---

## 5. Authentication and Permissions

Accounts, sessions, and audit records are stored in:

`data/managed/app.db`

Credentials are not hardcoded into the application or committed to the repository.

The initial administrator can be created through environment-based bootstrap settings or the account-management CLI.

### Session Configuration

The session cookie uses:

- `HttpOnly`
- `SameSite=Lax`
- `Secure` when the request uses HTTPS, or when `SESSION_COOKIE_SECURE=true`
- `Path=/`
- A configurable session lifetime, defaulting to eight hours

### Request Protection

Every state-changing request requires a valid `X-CSRF-Token` matching the authenticated session.

When an Origin header is present, it must match the request host.

### Role Permissions

| Capability | ADMIN | SOP_MANAGER | EMPLOYEE |
|---|---|---|---|
| Manage user accounts | Yes | No | No |
| Read audit trail | Yes | No | No |
| Edit document metadata | Yes | No | No |
| Upload documents | Yes | Yes | No |
| Review and activate documents | Yes | Yes | No |
| Reject and archive documents | Yes | Yes | No |
| Access chatbot | Yes | Yes | Yes |

Access restrictions are enforced by backend dependencies and endpoint checks, not merely by hiding interface controls.

Unauthorised access attempts are recorded in the audit trail with the available caller information.

---

## 6. Upload and Processing Workflow

The upload workflow is implemented through `POST /api/documents/upload`.

The processing sequence is:

1. Validate the caller's role, CSRF token, and submitted metadata.
2. Read the uploaded file within the configured size limit.
3. Validate the extension, MIME type, PDF signature, readability, page count, and extractable text.
4. Check for duplicate document identities and duplicate file content.
5. Save the PDF under a generated, safe filename in `Documents/uploads/`.
6. Create and persist a `PROCESSING` document record before indexing begins.
7. Extract document text and page information through the existing PDF-processing service.
8. Split the extracted content using the existing chunking service.
9. Attach document metadata to each chunk, including document code, revision, department, category, effective date, uploader, page information, and status.
10. Generate embeddings using the existing `EmbeddingService`.
11. Store the chunks through the existing `VectorStore`, initially marked as `pending_review` and managed.
12. Update the document record to `PENDING_REVIEW` with its page and chunk counts.
13. Refresh the document register.

If processing fails, the record is marked `FAILED` with a safe error message.

Partial chunks are deleted where possible. If any remain, retrieval filtering prevents non-active chunks from being returned as active content.

---

## 7. Revision Management Workflow

The revision-management workflow preserves the currently active document while a replacement is being reviewed.

### Uploading a New Revision

Uploading a new revision under an existing document code does not immediately change the active revision.

Both records can coexist:

- The existing revision remains active.
- The new revision remains pending review.
- The assistant continues retrieving the active revision until the replacement is approved.

### Activation Sequence

Activation follows this sequence:

1. Verify that the new revision is pending review.
2. Verify that its indexed chunk count matches the document record.
3. Mark the new revision's chunks as active.
4. Perform an atomic document-record update:
   - Set the new revision to `ACTIVE`.
   - Record the approver and approval timestamp.
   - Set the previous active revision to `ARCHIVED`.
5. Delete the previous revision's chunks from the index.

If the atomic document-record update fails, the chunk statuses are rolled back and the previous revision remains active.

If deletion of the previous revision's chunks fails, stale non-active chunks may remain. Subsequent activation operations retry the cleanup.

A process-wide lock serialises activation operations within the running application process.

Archiving the only active revision requires administrator privileges and an explicit override.

---

## 8. Tests and Validation Results

The implementation was validated through automated tests, API checks, browser workflows, and regression testing.

| Check | Result |
|---|---|
| `compileall backend tests` | PASS |
| Full automated test suite: 92 tests | PASS — 73 new tests and 19 existing tests |
| Live HTTP validation using real accounts, Gemini, and Chroma | 86 passed, 1 fixture-related failure, 2 informational results; the fixture-related case was subsequently retested successfully |
| Browser walkthrough of management functionality | PASS |
| `node --check frontend/js/app.js` | PASS |
| `pip check` | PASS — no broken requirements reported |
| Live `/api/status` endpoint | PASS |
| Frontend file delivery | PASS |
| `/docs` API documentation | PASS |
| Anonymous access to `/api/documents`, `/api/audit`, and `/api/users` | PASS — requests correctly denied |
| Six original chatbot questions | PASS, with one retry after a transient Gemini 503 response |
| Real-embedding upload in a temporary vector store | PASS — pending document was not retrievable as active content; vectors had 3072 dimensions |

Detailed test-case mappings and validation commands are documented in:

`DOCUMENT_UPLOAD_TEST_REPORT.md`

### Defect Found During Validation

One issue was discovered in the automated test harness.

`tests/helpers.py` referenced `ROLE_EMPLOYEE` without importing it. This caused 70 tests to error during test setup.

The missing import was added, and the full test suite was rerun successfully.

### Demo Coverage

The recorded demonstration includes:

- Dashboard and knowledge-base views.
- System information.
- Three chatbot questions and their citations.
- An abstention example.
- Authentication and role-gated navigation.
- The document upload form.

The upload form is populated in the recording, but the upload is not submitted. Therefore, the recording does not demonstrate a completed upload, activation, rejection, or archival workflow.

Those management operations were validated separately through testing and browser walkthroughs.

---

## 9. Original Chatbot Regression

The document-management implementation was tested against the original chatbot behaviour to ensure that existing functionality remained intact.

The six original questions retained their expected behaviour:

- Five questions were answered using the active curated knowledge base with relevant citations.
- One question correctly abstained because the knowledge base did not contain supporting information.
- Archived revision `QC-SOP-014 Rev03` was not returned in chatbot responses.

The original curated corpus remained unchanged:

- 15 active chunks.
- 3 archived chunks.
- No duplicate ingestion.
- No reset of the original knowledge base.

The following test verifies that managed-document uploads do not modify the curated corpus:

`test_manager_upload_does_not_touch_the_curated_corpus`

The original `data/knowledge_base/` directory was left untouched.

---

## 10. Known Limitations

The implementation has the following limitations.

1. **Synchronous processing:** PDF extraction and embedding run inside the upload request. Large manuals can take longer to process, and the browser waits for the request to complete. A background processing queue would be a suitable future improvement.

2. **Single-process assumption:** Activation uses an in-process lock. Deployments using multiple Uvicorn workers would require database-level coordination or another shared locking mechanism.

3. **No OCR:** Scanned and image-only PDFs are rejected because OCR is not implemented.

4. **Public chatbot access:** The chatbot does not require authentication in this build. Only document management and its protected operations require an authorised account. This preserves the original assignment behaviour.

5. **Keyword-based relevance classifier:** The manufacturing-relevance check uses a keyword heuristic. It is a review aid, not an approval mechanism or security boundary.

6. **Not a full document-management system:** The application does not currently provide document version diffing, scheduled effective dates, per-department document access controls, or digital signatures.

7. **Scale and performance:** The implementation uses local SQLite, JSON metadata, uploaded files, and a local vector store. Large-scale multi-plant deployment and concurrent multi-worker operation have not been established through load testing.

---

## 11. How to Run

Run the application from the project root with the Python virtual environment available.

### Linux / macOS / Git Bash

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Windows PowerShell

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open the application at:

`http://127.0.0.1:8000`

### Initial Administrator Setup

Create the first administrator using the configured `INITIAL_ADMIN_USERNAME` and `INITIAL_ADMIN_PASSWORD` environment variables, or use the account-management CLI:

```bash
python -m backend.services.auth_store create-admin --username <name>
```

Follow the CLI prompts and administrator setup instructions in `ADMIN_SETUP_GUIDE.md`.

---

## 12. Repository and Publication Status

The project repository has already been created and pushed to GitHub. Initial project commits and the banner asset commit are present in the remote repository.

The latest documentation revisions and demonstration assets are separate working-tree changes and have not yet been committed or pushed.

No deployment to a production hosting environment is claimed in this report.

The Gemini API key was not printed or included in this report. Configuration values and credentials must remain outside the public repository.

---

**End of Report**