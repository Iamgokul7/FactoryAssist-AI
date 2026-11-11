# Final submission report — FactoryAssist AI

> **Snapshot note (11 November 2026):** this file records the stage-6 audit, when
the suite held 19 tests. Stage 7 (document management, accounts, audit) was
validated afterwards; its results are in `DOCUMENT_UPLOAD_TEST_REPORT.md` and
`DOCUMENT_MANAGEMENT_IMPLEMENTATION_REPORT.md`, and the suite now holds 92
tests. The audit below is kept as the historical record; where the two disagree,
the stage-7 reports describe the current code.

Audit date: **10 November 2026**. Repository: `S:\BiztelAI Technologies. Assesment`,
branch `master`, HEAD `905ce5c`.

**Overall status: NOT YET SUBMISSION-READY.** All engineering and validation
work passes. Submission is blocked on three things only you can supply: your
confirmation of the personal reflections, your real Git author email (and the
commit itself), and — if the brief requires them — a recorded demo video and a
GitHub remote.

---

## 1. Project overview

FactoryAssist AI is a local, document-grounded copilot for manufacturing
supervisors. It answers questions about the plant's controlled SOPs and
maintenance manuals using retrieval-augmented generation over a small corpus of
PDFs, cites the document code, revision and page for every answer, refuses when
the evidence is insufficient, and keeps a superseded revision out of retrieval.

Delivered as a FastAPI application with a static multi-view dashboard (Dashboard,
AI Assistant, Knowledge Base, System Info) served from the same origin.

## 2. Technology stack

| Layer | Technology | Version |
| --- | --- | --- |
| Runtime | Python | 3.12 existing venv (3.14 verified in fresh install) |
| API | FastAPI / Uvicorn | 0.162.2 / 0.54.0 |
| Generation | Google Gen AI SDK, `gemini-3.5-flash-lite` | google-genai 2.34.0 |
| Embeddings | `gemini-embedding-001` | same SDK |
| Vector store | ChromaDB (persistent, cosine) | 1.5.9 |
| PDF extraction | PyMuPDF | 2.1 |
| Configuration | pydantic-settings + `.env` | 2.16.2 |
| Frontend | HTML, CSS, vanilla JavaScript | no build step |
| Tests | stdlib `unittest` | — |

No React, Next.js, Flask, LangChain or LlamaIndex is used.

## 3. Completed implementation — **PASS**

- PDF pipeline with a verified document registry, page-level extraction, chunk
  metadata and a manifest of active/archived revisions.
- Incremental ingestion: SHA-256 content hashes skip unchanged chunks; upsert by
  stable chunk ID.
- Retrieval: top-5, cosine similarity, 0.30 floor, active-status filter, second
  manifest check, and no generation call when evidence is empty.
- Grounded generation: strict JSON schema (`answer`, `supported`,
  `used_source_indices`), citations built from retrieved chunks only.
- Model-family thinking configuration (`thinking_level` for Gemini 3, none for
  2.x/aliases) with one retry without the hint on HTTP 400.
- Classified errors, redacted diagnostics, timeouts, retry of 429/5xx once.
- `/api/status` reports real model availability through a cached model-list
  probe (TTL 600 s, own 10 s timeout, `?refresh=true`).
- Dashboard surfaces model state (badge, KPI, System Info row) and error states.

## 4. PDF ingestion status — **PASS**

| Item | Value |
| --- | --- |
| Documents processed | 5 (3 active, 1 archived, 1 sample questions) |
| Pages extracted | 8 |
| Active chunks | 15 |
| Archived chunks | 3 (not embedded) |
| Extraction warnings / errors | 0 / 0 |
| Chunking | 900 characters, 150 overlap, page-scoped |

Source: `data/processed/document_manifest.json` (generated 09-Nov-2026
15:20 UTC).

## 5. RAG retrieval validation — **PASS**

- Collection `factoryassist_active_documents`, 15 records, persistence under
  `vector_store/chroma_db/`.
- Query filter `document_status == "active"`, threshold 0.30, top 5.
- Best-match similarity across the five answerable questions: **0.688–0.789**,
  comfortably above the floor; the electricity question's best match is 0.60
  but still produces no grounded answer because the model reports no support.
- **QC-SOP-014 Rev 03 appeared in no retrieval result, citation or answer in any
  test.**

## 6. Gemini integration status — **PASS**

| Check | Result |
| --- | --- |
| Key configured | yes (value never printed) |
| Generation model | `gemini-3.5-flash-lite` |
| Embedding model | `gemini-embedding-001` |
| `/api/status` model state | `ready` (live probe, 1.15 s with `refresh=true`) |
| Thinking configuration | `thinking_level=low` sent to Gemini 3 only |
| Unavailable-model behaviour | verified earlier: status `unavailable`, chat HTTP 404 diagnostic, UI shows "AI model unavailable" + "Service error" bubble with 0 sources |

## 7. Automated testing results — **PASS**

| Check | Command | Result |
| --- | --- | --- |
| Compilation | `python -m compileall backend tests` | exit 0 |
| Test suite | `python -m unittest discover -s tests -t .` | **19 tests, OK** (0.032 s) |
| Dependencies | `python -m pip check` | `No broken requirements found` |
| Fresh environment | see `FRESH_INSTALL_REPORT.md` | install + 19 tests pass |

## 8. Live test results — **PASS**

Executed against the running application on `http://127.0.0.1:8000`.

| # | Question | HTTP | Status | Time | Source cited |
| --- | --- | --- | --- | --- | --- |
| 1 | Coolant concentration | 200 | answered | 2.5 s | MNT-MAN-CNC-02 Rev 02, p1 (0.727) |
| 2 | AL-104 meaning/action | 200 | answered | 3.9 s | MNT-MAN-CNC-02 Rev 02, p2 (0.749) |
| 3 | LOTO lock removal | 200 | answered | 2.1 s | SAF-SOP-003 Rev 05, p1 (0.789) |
| 4 | BH-220 OD tolerance | 200 | answered | 5.1 s | QC-SOP-014 **Rev 04**, p2 (0.696) |
| 5 | Spindle runout | 200 | answered | 5.6 s | MNT-MAN-CNC-02 Rev 02, p1 (0.688) |
| 6 | Annual electricity | 200 | `insufficient_evidence` | 6.0 s | none |

Answers were correct in content: 6–8 % coolant; way lube low → ISO VG 68 to MAX
then RESET; each person removes only their own lock; ±0.050 mm at 90.000 mm with
a digital caliper; monthly by a maintenance technician; and the fixed fallback
sentence with zero sources for electricity.

Response times were slower than the earlier 1.5–2.3 s run (2.1–6.0 s here),
which is API latency variation; `THINKING.md` was updated to state both.

API input validation re-checked: whitespace question → `400 Please enter a
question.`; missing field → `422` with a standard validation detail.

## 9. Security checks — **PASS**

| Check | Result |
| --- | --- |
| Exact configured key in Git history | **none** |
| Exact key in working tree (excluding `.env`) | **none** |
| `AIza…` / `sk-…` patterns in tree or history | none |
| `.env` ever committed | **never** |
| `.env`, logs, `.venv`, `chroma_db`, `data/processed`, PDFs ignored | verified with `git check-ignore` |
| Tracked files | 47, no secrets, no PDFs, no database, no logs |
| Key in API responses / UI | none (only `configured: true`) |
| Error diagnostics | redacted, truncated to 300 chars |
| `DEBUG` | `False` in config, `.env.example` and `.env` |
| Auth | none — single-user local deployment (documented limitation) |

`vector_store/.gitkeep` is tracked intentionally to preserve the directory.

## 10. Documentation status

| Document | Status | Notes |
| --- | --- | --- |
| `THINKING.md` | **PASS (technical) / BLOCKED (personal)** | 22 sections numbered 1–22; 6 code fences balanced; all tables well-formed; §3 has the AI-critique introduction; §5.1–5.3 renamed; §7 diagram lists `sample_questions_extracted`; no secrets |
| `PERSONAL_REFLECTIONS_TO_CONFIRM.md` | **PASS** | 23 statements listed by section, with verified facts separated out |
| `README.md` | **PASS** | Setup, endpoints, status/model availability, tests, screenshots, security notes |
| `DEMO_SCRIPT.md` | **PASS** | Timed 2:45 narration + fallback guidance |
| `DEMO_RECORDING_CHECKLIST.md` | **PASS** | Pre-flight, screen hygiene, shot order, expected outputs |
| `FRESH_INSTALL_REPORT.md` | **PASS** | Clean-environment results |
| `GIT_SETUP_REQUIRED.md`, `GITHUB_SETUP_REQUIRED.md` | **PASS** | Exact commands, nothing executed |

The reflections in §1, §2, §3, §4, §6 and §21 remain **unconfirmed personal
statements**. They were preserved as written, not presented as verified. The
Section 3 sentence asserts an AI produced the critique; that is consistent with
the section title but still needs your confirmation (item 3.1 in
`PERSONAL_REFLECTIONS_TO_CONFIRM.md`).

## 11. Screenshot status — **PASS**

| File | Purpose | Size |
| --- | --- | --- |
| `01-dashboard.png` | Dashboard, KPIs, badges | 1280×900 |
| `02-assistant-coolant.png` | Coolant answer + citation | 1280×900 |
| `03-assistant-al104.png` | AL-104 answer + citation | 1280×900 |
| `04-assistant-loto.png` | LOTO answer + citation | 1280×900 |
| `05-source-citations.png` | Citation detail (QC-SOP-014 Rev 04 p2) | 1896×510 (2× crop) |
| `06-knowledge-base.png` | Active docs + archived Rev 03 | 1280×900 |
| `07-system-info.png` | Model availability, config, API surface | 1280×900 |
| `08-abstention-electricity.png` | Refusal, no sources | 1280×900 |

All eight exist, were opened and visually checked during this audit, and match
their documented purpose. They were captured from the running application; none
were regenerated in this run because none was missing or stale.

## 12. Demo video status — **NOT RUN**

No video file exists and none was recorded. `DEMO_SCRIPT.md` and
`DEMO_RECORDING_CHECKLIST.md` are ready; recording is yours to do.

## 13. Git status — **BLOCKED**

| Item | State |
| --- | --- |
| Branch | `master` |
| Commits | `905ce5c`, `aa1fbf5`, `c511a1a`, `083ac7b` (history intact) |
| `user.name` / `user.email` | `Gokul P` / **`your-email@example.com` (placeholder)** |
| Modified / untracked | `THINKING.md` modified; new audit documents untracked |
| Staged | documentation staged for review, **no commit created** |
| Remote | none |

Blocked on the author email; `GIT_SETUP_REQUIRED.md` has the exact commands.

## 14. GitHub status — **BLOCKED**

No remote is configured and no repository was created. Nothing was pushed or
published. `GITHUB_SETUP_REQUIRED.md` covers both the CLI and browser routes,
with private visibility recommended.

## 15. Remaining actions requiring your input

1. **Confirm the personal reflections** in `PERSONAL_REFLECTIONS_TO_CONFIRM.md`
   (items 1.1–1.4, 2.1–2.4, 3.1–3.4, 4.1–4.4, 6.1–6.3, 21.1–21.6), including
   item 3.1 about the AI-critique attribution.
2. **Set your real Git email** (`git config --local user.email …`).
3. **Commit** the staged documentation once (1) and (2) are done.
4. **Create the private GitHub repository and push**, if the submission requires
   it — only with your approval.
5. **Record the demo video**, if the brief requires one.
6. Optional: decide whether the report/audit files belong in the submission
   repository; they can be unstaged with `git restore --staged <file>`.

## What prevents submission today

- Unconfirmed personal reflections (content risk, not a technical failure).
- Placeholder Git author email, so no commit has been made.
- No remote configured (only matters if the submission is a GitHub link).
- No demo video (only matters if the brief requires a video).
