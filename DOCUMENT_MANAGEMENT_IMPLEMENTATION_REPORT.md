# Document management implementation report

What was built inside the existing FactoryAssist AI project, how it fits the
existing architecture, what was tested, and what is still limited.

Date: 2026-11-10 · Project: `S:\BiztelAI Technologies. Assesment` · Stage: 7

---

## 1. Features implemented

**Dashboard and register**
- Document Management screen in the existing sidebar, using the existing design
  tokens and components.
- Counters for total, active, pending review, archived and failed documents.
- Searchable, filterable register (code, title, revision, department, effective
  date, status, upload date, uploader, actions).
- Detail view with metadata, processing facts, PDF download, revision history,
  warnings and the actions available for the caller's role.

**Upload**
- Drag-and-drop and browse upload with a real XHR progress bar.
- Metadata form: document code, revision, title, department, category, effective
  date, description.
- Server-side validation: extension, MIME type, `%PDF-` signature, size cap,
  PyMuPDF readability, at least one page with extractable text, code/revision
  format, duplicate code+revision, identical file content, and curated-corpus
  duplicates.
- Safe unique storage names (`<code>-rev<NN>-<8 hex>.pdf`) inside
  `Documents/uploads/`; the client filename is never used as a path.
- Processing reuses the existing pipeline: `pdf_processor.extract_document` →
  `text_chunker.chunk_document` → `EmbeddingService` → `VectorStore`.

**Governance**
- Statuses `PROCESSING`, `PENDING_REVIEW`, `ACTIVE`, `ARCHIVED`, `REJECTED`,
  `FAILED`, with only `ACTIVE` retrievable.
- Approve/activate, reject (with reason), archive, retry, metadata edit, and an
  optional manufacturing-relevance flag from a keyword classifier.
- Revision history per document code, with exactly one active revision enforced
  by the activation routine.

**Security**
- PBKDF2-HMAC-SHA256 passwords (600 000 iterations, per-password salt).
- Opaque session tokens stored only as SHA-256 fingerprints, HttpOnly +
  SameSite=Lax cookies, `Secure` on HTTPS, expiry and full revocation on logout,
  password change, role change or disable.
- Per-session CSRF token required on every mutation, plus Origin/Host comparison.
- Login rate limiting driven by failed-login audit rows: five failures per account and twenty per client address in the same window, so one account cannot lock out everyone behind a shared IP.
- Three roles enforced server-side: `ADMIN`, `SOP_MANAGER`, `EMPLOYEE`.
  401 for anonymous, 403 for insufficient role, both audited.
- Security headers added by middleware (no sniff, no framing, no referrer).

**Audit**
- SQLite audit trail: sign-in success/failure, sign-out, upload attempts,
  validation failures, processing results, review actions, activation, archival,
  metadata edits, account/role changes and refused management calls.
- No passwords, tokens or API keys are written to the log.

## 2. Existing files modified

| File | Change |
| --- | --- |
| `backend/main.py` | Lifespan creates managed dirs, bootstraps the optional admin and recovers interrupted uploads; registers auth/document routers; security-header middleware |
| `backend/core/config.py` | Managed data dir, upload dir, size cap, session TTL, cookie mode, rate-limit settings, bootstrap admin variables |
| `backend/services/vector_store.py` | `count(where)`, `metadata_for_document`, `delete_by_document`, `set_document_status`, `update_chunk_metadata`, `managed_chunk_ids` — no change to existing method signatures |
| `backend/services/knowledge_base.py` | Manifest view merges managed records; managed codes supersede manifest entries so citations never show a superseded revision |
| `backend/services/ingestion_service.py` | No longer deletes chunks it does not own, so a CLI re-ingest cannot delete managed documents |
| `backend/api/health.py` | Reports live active-chunk count and stage 7 |
| `frontend/index.html` | Sidebar item, auth area, document view, upload form/drop zone, register, audit panel, login and detail modals, toast container, API table |
| `frontend/js/app.js` | Session/CSRF handling, upload with progress, register rendering and filters, details, revision history, activate/archive/reject/retry, audit view, toasts |
| `requirements.txt` | `python-multipart` for form uploads |
| `.env.example` | New settings with placeholders only |
| `.gitignore` | `data/managed/`, upload directory |
| `README.md`, `THINKING.md`, `DEMO_SCRIPT.md` | Feature docs, architecture decisions (§23), demo segment |

The new screen's styles live in `frontend/css/management.css`, linked after the
original stylesheet. `frontend/css/styles.css` received one global fix during
final validation: `[hidden] { display: none !important; }`, because
`.btn { display: inline-flex }` overrode the `hidden` attribute and the
signed-out header still showed the sign-out button.

## 3. New files

| File | Purpose |
| --- | --- |
| `backend/core/security.py` | Password hashing/verification, password policy, token generation and hashing, constant-time compare |
| `backend/services/auth_store.py` | SQLite accounts, sessions, audit, rate-limit queries, bootstrap, CLI (`create-admin`, `reset-password`, `set-role`, `list-users`) |
| `backend/services/management_store.py` | Statuses, categories, document records with atomic JSON writes, revisions, counters, public view |
| `backend/services/document_manager.py` | Validation, PDF inspection, ingestion through the existing services, retry, activation transaction, archive/reject, metadata, crash recovery |
| `backend/api/deps.py` | Session resolution from cookie, `require_manager`, `require_admin`, CSRF and Origin checks, shared manager dependency |
| `backend/api/auth.py` | Login, logout, me, change-password, account admin routes, audit endpoint |
| `backend/api/documents.py` | Document, stats, meta, upload, detail, status, revisions, file, activate, archive, reject, retry, metadata routes |
| `frontend/css/management.css` | Styles for the new screen |
| `tests/helpers.py`, `tests/test_document_management.py`, `tests/test_access_control.py` | 70 new tests and their temporary-environment harness |
| `DOCUMENT_MANAGEMENT_GUIDE.md`, `ADMIN_SETUP_GUIDE.md`, `DOCUMENT_UPLOAD_TEST_REPORT.md`, this report | Documentation |

## 4. API endpoints

| Method | Path | Access |
| --- | --- | --- |
| POST | `/api/auth/login` | public (rate limited) |
| POST | `/api/auth/logout` | session + CSRF |
| GET | `/api/auth/me` | public (reports anonymous) |
| POST | `/api/auth/change-password` | session + CSRF |
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
| POST | `/api/documents/{key}/archive` | ADMIN, SOP_MANAGER (last active revision: ADMIN only) |
| POST | `/api/documents/{key}/reject` | ADMIN, SOP_MANAGER |
| POST | `/api/documents/{key}/retry` | ADMIN, SOP_MANAGER |
| PATCH | `/api/documents/{key}` | ADMIN |

`{key}` is the revision record id (for example `qc-sop-014-rev05`). Existing chat
and status endpoints are unchanged.

## 5. Authentication and permissions

- Accounts and sessions live in `data/managed/app.db`; no credentials exist in
  code or in the repository. Bootstrap is either `.env` variables consumed once,
  or `python -m backend.services.auth_store create-admin`.
- Session cookie: `HttpOnly`, `SameSite=Lax`, `Secure` when the request is HTTPS
  (or forced with `SESSION_COOKIE_SECURE=true`), `Path=/`, TTL 8 h by default.
- Every mutation needs `X-CSRF-Token` matching the session, and an `Origin` that
  matches `Host` when `Origin` is present.
- Role matrix (also in `ADMIN_SETUP_GUIDE.md`): ADMIN manages accounts and
  metadata; SOP_MANAGER handles the document lifecycle; EMPLOYEE has chat only.
- Refusals are audited with the caller's username and IP.

## 6. Upload and processing workflow

1. `POST /api/documents/upload` validates role, CSRF and form fields (Pydantic).
2. The file is read under the size cap and checked: extension, MIME type,
   signature, PyMuPDF open, page count, extractable text, duplicate checks.
3. It is written to `Documents/uploads/` under a generated safe name.
4. A `PROCESSING` record is created and committed before indexing starts, so a
   crash leaves a recoverable state rather than a half-record.
5. Text and page numbers come from the existing `extract_document`; chunks from
   `chunk_document`; metadata (code, revision, department, category, effective
   date, uploader, pages, status) is attached to every chunk.
6. Existing `EmbeddingService` embeds the chunks and existing `VectorStore`
   writes them with `document_status: "pending_review"` and `managed: "yes"`.
7. The record becomes `PENDING_REVIEW` with page/chunk counts; the dashboard
   refreshes.
8. Any failure marks the record `FAILED` with a safe message; partial chunks are
   deleted or, at worst, remain non-retrievable because retrieval filters on
   `document_status = active`.

## 7. Revision management workflow

- Uploading an existing code with a new revision does not touch the active
  revision; both records coexist, only one is active.
- Activation, in order: verify the pending record and its chunk count → mark its
  chunks active → single atomic write flipping the new record to `ACTIVE` (with
  approver and timestamp) and the previous active to `ARCHIVED` → delete the old
  revision's chunks.
- If the atomic write fails, chunk statuses are rolled back and the old revision
  stays active. If chunk deletion fails, only stale, non-active chunks remain and
  the next activation retries cleanup.
- A process-wide lock serialises activation so two concurrent approvals cannot
  both win.
- Archiving the only active revision requires ADMIN and an explicit flag.

## 8. Tests and results

| Check | Result |
| --- | --- |
| `compileall backend tests` | PASS |
| Full suite: 92 tests (73 new, 19 existing) | PASS — `Ran 92 tests in 55.3s ... OK` |
| Live HTTP validation (real accounts, real Gemini, real Chroma) | PASS — 86 pass / 1 fixture-related fail, retested green (see test report §3–§4) |
| Browser walkthrough of the management UI | PASS — upload, drag-and-drop, validation, search, filters, details, activate, archive, reject, audit, mobile layout |
| `node --check frontend/js/app.js` | PASS |
| `pip check` | PASS — no broken requirements |
| Live `/api/status`, frontend files, `/docs` | PASS |
| Anonymous 401 on `/api/documents`, `/api/audit`, `/api/users` | PASS |
| Six original questions | PASS (Q2 needed a retry after a transient Gemini 503) |
| Real-embedding upload in a temp store | PASS — pending, not retrievable as active, 3072-dim vectors |

Per-case mapping and the exact commands are in `DOCUMENT_UPLOAD_TEST_REPORT.md`.

One defect was found and fixed during final validation: `tests/helpers.py` used
`ROLE_EMPLOYEE` without importing it, which made 70 tests error in `setUp`. The
import was added and the suite rerun to green.

## 9. Original chatbot regression

All six questions behave as before: five answered from the active corpus with
correct citations, the sixth abstains with no sources. Archived Rev 03 of
`QC-SOP-014` never appears. The corpus is unchanged at 15 active chunks and 3
archived chunks — no reset, no duplicate ingestion, `data/knowledge_base/`
untouched (asserted by `test_manager_upload_does_not_touch_the_curated_corpus`).

## 10. Limitations

1. **Synchronous processing.** Extraction and embedding run inside the upload
   request; a very large manual makes the browser wait. A background queue is the
   natural next step.
3. **Single-process assumption.** Activation uses an in-process lock. Multiple
   Uvicorn workers would need a database-level lock.
4. **No OCR.** Scanned PDFs are rejected with a clear message.
5. **Chat is still public.** Only management is authenticated. This preserves the
   original assignment behaviour; gating chat behind sign-in is a deliberate
   product decision, not an oversight.
6. **Keyword classifier.** The manufacturing-relevance check is a heuristic used
   as a review hint, never as the security boundary.
7. **Not a full DMS.** No version diffing, no scheduled effective dates, no
   per-department document ACLs, no digital signatures.

## 11. How to run

```bash
# from the project root, with the virtual environment available
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Windows PowerShell equivalent:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open <http://127.0.0.1:8000>. Create the first administrator with
`INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD`, or
`python -m backend.services.auth_store create-admin --username <name>`.

Nothing was committed, pushed, published or deployed, and the Gemini API key was
neither printed nor modified.
