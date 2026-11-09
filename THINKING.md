# THINKING.md

Working notes for the FactoryAssist AI assignment.

**How to read this file.** Technical sections describe what was actually built
and why, based on the implementation in this repository, and are written so
every claim can be checked against the code. Sections that require the author's
own independent thinking — the initial journey, the AI critique, the reflection
and the closing retrospective — are marked `[USER INPUT REQUIRED]` and have not
been filled in. Nothing in those sections has been invented on the author's
behalf. Section 15 lists every question still waiting for an answer.

---

## 1. Understand the user

**Context from the brief (factual).** The primary user is a manufacturing
supervisor or shift lead at a plant that runs CNC turning centres. They work
under time pressure, often standing at a machine, and they need an answer they
can act on immediately: a coolant concentration, an alarm meaning, a lockout
rule, a dimensional tolerance.

**What makes this hard (factual).** The knowledge is already written down, but
in controlled PDFs rather than in a searchable system. Revisions circulate:
QC-SOP-014 Rev 03 was superseded by Rev 04 on 01-Jul-2026, and both files still
exist. A supervisor who asks a chatbot a question and receives a confident,
unsourced answer is worse off than before, especially on a safety procedure.

`[USER INPUT REQUIRED: Describe the supervisor you had in mind in your own
words — the shift pattern, the environment, the moments where they need this,
and how they look things up today. Add anything you observed or were told
directly.]`

---

## 2. Initial user journey (written independently, before using AI)

`[USER INPUT REQUIRED: Write your initial supervisor journey here in your own
words, before any AI critique — for example: supervisor notices an alarm →
walks to the machine panel → searches the maintenance manual PDF → finds a
revision that may be out of date → asks a colleague → acts. Describe the
friction points and what you thought the product should do at each step. This
must be your own reasoning, written independently, and is intentionally left
blank here.]`

---

## 3. AI critique of that journey

`[USER INPUT REQUIRED: Paste or summarise the critique you received when you
shared your journey with an AI assistant, including what it challenged and what
you disagreed with. This section must reflect a real conversation, not a
reconstruction.]`

---

## 4. Reflection: what changed after the critique

`[USER INPUT REQUIRED: Explain what you changed in your journey or your design
after the critique, and why. If you rejected part of the critique, say so and
explain your reasoning.]`

---

## 5. The AI challenge (technical)

Retrieval alone is not enough for this domain. Three specific problems had to be
solved:

1. **Traceability.** A supervisor must be able to verify an instruction. That
   required page-scoped chunking (chunks never cross a page boundary), metadata
   on every chunk, and citations built from the chunks actually used — not from
   text the model produced.
2. **Revision correctness.** Rev 03 and Rev 04 of QC-SOP-014 describe different
   sampling rules. Mixing them would produce a wrong inspection instruction.
   The manifest records which revision is active, archived revisions are kept
   out of the vector collection entirely, and retrieval re-checks each result
   against the manifest before it is used.
3. **Honest refusal.** The model will always produce fluent text. For an
   unanswerable question such as the factory's annual electricity consumption,
   the system must return a fixed fallback sentence with no sources rather than
   a plausible guess. This is enforced in the system prompt and again in the
   server logic, which discards unsupported answers instead of trusting them.

---

## 6. The improvement added, and why it was chosen

**What was added (factual, implemented).** Revision-aware, page-cited retrieval:
the corpus is filtered to the active revision of each document, and every answer
carries the document code, revision and page for the evidence it used. Archived
revisions remain available for reference but can never enter a normal answer.

**Why it matters (factual).** Without it, the system is a "chat with your PDFs"
demo. With it, an answer is checkable against a controlled document, and a
superseded instruction cannot silently become the answer.

`[USER INPUT REQUIRED: Explain in your own words why you chose this improvement
over the alternatives you considered (for example: OCR for scanned documents,
multi-document comparison, or an approval workflow), and what evidence from your
user understanding led you to prioritise it.]`

---

## 7. Architecture (factual)

The application is four stages with clean boundaries. Only the fast path — a
question — runs on every request; stages 1 and 2 are offline batch jobs.

```
Documents/{active,archived,sample_questions}/*.pdf
        │  (1) PyMuPDF, page by page
        ▼
data/processed/*.json        active_chunks · archived_chunks · manifest
        │  (2) Gemini embeddings, active chunks only
        ▼
vector_store/chroma_db       one cosine collection
        │  (3) query embedding + top-k search + revision re-check
        ▼
backend/services/rag_service.py
        │  (4) evidence-bound prompt → Gemini JSON answer
        ▼
POST /api/chat  →  frontend/js/app.js
```

| Stage | Entry point | Output |
| --- | --- | --- |
| Document processing | `python -m backend.services.document_pipeline` | JSON chunks + manifest |
| Indexing | `python -m backend.services.ingestion_service` | ChromaDB collection |
| Serving | `uvicorn backend.main:app` | `/api/chat`, `/api/status`, dashboard |
| Configuration | `backend/core/config.py` | One `Settings` object from `.env` |

A deliberate boundary: the serving process only ever *reads* the index. It
never extracts PDFs or embeds documents, so a chat request cannot slow down
ingestion or rewrite the corpus.

---

## 8. Technology choices (factual)

| Layer | Choice | Why this and not something else |
| --- | --- | --- |
| Backend | FastAPI + Uvicorn | Required by the brief; async I/O for the API, automatic OpenAPI docs; the one blocking call (the Gemini SDK) is pushed to a threadpool |
| Generation | `google-genai` 2.34.0, `gemini-3.5-flash-lite` | Same vendor as the embeddings, so one key and one SDK; low latency matters for a supervisor standing at a machine |
| Embeddings | `gemini-embedding-001` | Required by the brief; `RETRIEVAL_DOCUMENT`/`RETRIEVAL_QUERY` task types are supported natively |
| Vector store | ChromaDB 1.5.9, persistent, local | Required by the brief; file-based persistence, no server to run on a plant laptop; cosine space maps directly to a 0–1 similarity |
| PDF text | PyMuPDF 2.1 | Fast, page-accurate text extraction with no external binaries (no Java, no Poppler) |
| Config | Pydantic Settings + `.env` | Typed, validated at startup, one source of truth, nothing hardcoded in modules |
| Frontend | HTML5 + CSS + vanilla JS | No build step, no Node runtime, served from the same origin as the API; a plant laptop only needs Python |
| Tests | stdlib `unittest` | No extra dependency for an offline suite; `python -m unittest` works in a fresh virtualenv |

No React, Node.js, Next.js, Flask, LangChain or LlamaIndex is used, per the
brief. `requirements.txt` lists only what the code imports.

---

## 9. PDF processing (factual)

`backend/services/pdf_processor.py`

- **Page by page.** `page.get_text("text")` is called per page, so page numbers
  are preserved by construction rather than reconstructed later from text.
- **Nothing invented.** A page with no extractable text (a scan) is recorded as
  an extraction warning and left empty. No OCR, no placeholder text.
- **Failure isolation.** A password-protected, empty or corrupt PDF records an
  error on its own result object; the run continues with the other documents.
- **Text normalisation.** CRLF is normalised, trailing spaces stripped and runs
  of blank lines collapsed — this stabilises chunk boundaries across runs.
- **Identity verification.** Page 1 is checked for the document code, revision
  and effective date registered for that filename. A mismatch (for example a
  different revision dropped in with the old filename) becomes a warning instead
  of silently poisoning the corpus.
- **Registry, not filename parsing.** `document_registry.py` holds the verified
  identity of the five PDFs, read from the documents themselves. A PDF that is
  not in the registry is skipped with an error rather than guessed at, and a PDF
  in the wrong folder (active vs archived) is skipped too.

The original PDFs in `Documents/` are never modified, moved or deleted; the
pipeline only reads the three sub-folders and writes to `data/processed/`.

---

## 10. Chunking strategy (factual)

`backend/services/text_chunker.py`

- **Page-scoped.** A chunk is built from exactly one page, so a citation can
  always name a page. Chunks never span pages, documents or revisions.
- **Size.** 900 characters with 150 characters of overlap (`CHUNK_SIZE`,
  `CHUNK_OVERLAP`). That is roughly a paragraph or two of SOP prose — large
  enough to contain a complete instruction, small enough that retrieval can
  isolate one.
- **Natural boundaries.** The cut point is pulled back to a paragraph break,
  then a line break, then a space, but never below 75 % of the target size, so
  chunks do not collapse into headings or half-sentences. Overlap resumes at
  the start of the next word (`_snap_forward`), which guarantees forward
  progress even inside a long unbroken string.
- **Short tail merging.** If a page ends with a fragment smaller than 75 % of
  the target, it is merged into the previous chunk when the result stays under
  115 % of the target, and the duplicated overlap is removed. This avoids
  low-value retrieval units made of one line.
- **Stable ids.** `<document_id>-p<page>-c<index>`, e.g.
  `saf-sop-003-rev05-p001-c001`. The id is deterministic, so re-running the
  pipeline produces the same ids and the index can be updated in place.

Result for this corpus: 3 active documents (2 pages each) → 15 active chunks;
the archived revision produces 3 chunks of its own that are never embedded, and
the sample-questions sheet is extracted but never chunked. Extraction produced
0 warnings and 0 errors.

---

## 11. Embedding generation (factual)

`backend/services/embedding_service.py`

- Documents are embedded with task type `RETRIEVAL_DOCUMENT`; questions with
  `RETRIEVAL_QUERY`. Google recommends this asymmetry when the vectors are used
  for retrieval.
- Requests are batched (`EMBEDDING_BATCH_SIZE=24`) to stay well inside request
  limits and to make a partial failure cheap.
- Empty text is refused before a request is made — an empty embedding would sit
  in the index and match nothing meaningfully.
- The response is validated: the number of vectors must equal the number of
  inputs and no vector may be empty. A mismatch raises instead of storing
  half-aligned vectors.
- Transient failures (429, 5xx) are retried up to three times with linear
  backoff; permanent failures surface as `EmbeddingError` with a classified
  message. Timeouts are not retried — the client timeout is already 120 s.

Ingestion is incremental: `sha256(chunk_text)[:16]` is stored as `content_hash`
in Chroma metadata, so a re-run embeds only new or changed chunks and deletes
chunk ids that no longer exist. Re-running the indexer does not burn embedding
quota for an unchanged corpus.

---

## 12. Vector database implementation (factual)

`backend/services/vector_store.py`

- `chromadb.PersistentClient` on `vector_store/chroma_db`, one collection
  (`factoryassist_active_documents`) per deployment.
- **Cosine space.** `configuration={"hnsw": {"space": "cosine"}}`, and
  `embedding_function=None` because this application always supplies its own
  vectors. Chroma is used strictly as a vector index, never as an embedder —
  that keeps the embedding model single-sourced in `.env`.
- **Similarity conversion.** Chroma returns a cosine *distance*; the store
  converts it to `similarity = 1 - distance`, clamped to 0–1, so the threshold
  in `.env` reads the way a reviewer expects.
- **Flat metadata only.** `document_id`, `document_code`, `document_title`,
  `revision`, `document_status`, `source_filename`, `page_number`,
  `page_range`, `chunk_index`, `content_hash`. Chroma stores scalars, so no
  nested structures are attempted.
- **Idempotent writes.** `upsert` keyed by chunk id, so a re-run updates rather
  than duplicates. Deleting stale ids keeps the collection equal to the current
  corpus.
- **Only active chunks are ever written**, because the indexer reads
  `active_chunks.json`; `archived_chunks.json` is never opened by it. The
  archived revision exists in JSON and in the Knowledge Base view, nowhere else.

---

## 13. Retrieval approach (factual)

`backend/services/rag_service.py`

1. The question is embedded with `RETRIEVAL_QUERY`.
2. `top_k=5` chunks are requested with a Chroma `where` filter on
   `document_status == "active"` — the archived revision cannot be returned even
   if its vector existed.
3. Candidates below `RETRIEVAL_MIN_SIMILARITY=0.30` are discarded. If nothing
   survives, the request short-circuits to the fixed fallback answer with **no
   sources** and never calls the generation model.
4. **Defence in depth.** Every surviving chunk is re-checked against the
   manifest (`active_revisions()`); a chunk whose `document_id` is not the
   active revision for its `document_code` is dropped and logged as a warning.
   The query filter protects against a bad index; this check protects against a
   stale manifest or a hand-edited collection.
5. The top 5 of a 15-chunk corpus is a third of the corpus. With so few chunks,
   a higher `top_k` would add noise to the prompt rather than recall, and the
   similarity floor does most of the filtering — observed best-match
   similarities for the five answerable questions were 0.69–0.79.

---

## 14. Prompt engineering and grounding (factual)

The system instruction is strict by design and is not a generic "answer from the
context" prompt. It forbids outside knowledge, invented values, invented
procedures, and naming "evidence"/"chunks"; it requires the exact fallback
sentence when the evidence is insufficient, requires both values to be reported
when two documents conflict, and requires the answer in the language of the
question. It also permits quoting the document code and revision, which is what
makes an answer checkable.

The user message contains the question followed by numbered evidence blocks,
each carrying title, code, revision, page and filename. Numbering is what lets
the model return `used_source_indices` and lets the server cite only what was
used.

Generation is constrained further:

- `response_mime_type="application/json"` plus a `response_schema` with
  `answer`, `supported`, `used_source_indices` — the model cannot return prose
  that skips the support decision.
- `temperature=0.2` and `max_output_tokens=1024`: low variance, and no room for
  an essay when a supervisor needs two sentences.
- **Server-side enforcement.** `supported: false`, an empty answer, or an answer
  that opens with the fallback sentence all produce the canonical fallback with
  zero sources. The model's optimism cannot override the contract.
- **Citations come from chunks, not from text.** `_sources_for()` maps the
  returned indices onto the retrieved chunks, validates them against the
  evidence count, and de-duplicates by `(document_id, page)`. A model that
  invents a document number cannot invent a citation, because the model never
  writes citation text.

---

## 15. Gemini integration (factual, including the compatibility fix)

`backend/services/gemini_client.py`, `backend/services/rag_service.py`

- One shared client factory; no other module reads `GEMINI_API_KEY`. The client
  is lazy (created on first use) and reused.
- `models.generate_content` with `GenerateContentConfig`: system instruction,
  temperature, max output tokens, JSON mime type, response schema, thinking
  configuration.
- **The 400 investigation.** The first live run of `gemini-3.5-flash-lite`
  failed with `400 INVALID_ARGUMENT`. The API's message is opaque
  ("Request contains an invalid argument."), so the request was bisected against
  the live API one parameter at a time: no config, + temperature/tokens,
  + system instruction, + JSON mime, + schema — all accepted —
  **+ `thinking_budget=0` → 400**. Listing models confirmed the model itself was
  available and generation-capable, so the name was not at fault.
- **Root cause.** Gemini 3 replaced *thinking budget* with *thinking level* and
  rejects a budget value, including `0`, which older models accepted.
- **Fix.** Thinking configuration is now model-family aware: Gemini 3 and newer
  receive `thinking_level` from `GEMINI_THINKING_LEVEL` (default `low`); Gemini
  2.x and unversioned aliases receive no thinking hint at all and use the API
  default — sending `budget=0` to a 2.x model is not safe either. If any model
  still rejects the hint with 400, the request is retried once without it before
  the failure is reported.
- **Why not simply remove thinking config?** That would work today but silently
  change reasoning behaviour on future model families and hide the real
  incompatibility. Naming the capability explicitly keeps the choice visible in
  `.env` and documents the constraint in one place.

---

## 16. Error handling (factual)

Errors are typed and classified rather than collapsed into one message:

| Failure | Type | Reported to the user | Logged |
| --- | --- | --- | --- |
| No API key | `GeminiNotConfiguredError` | key missing, documents still ready | — |
| `400 INVALID_ARGUMENT` | `GeminiRequestError` | request/model-setting problem, explicitly *not* a key problem | `400 INVALID_ARGUMENT` + API message |
| `401` / `403` | `GeminiRequestError` | check `GEMINI_API_KEY` | `401 UNAUTHENTICATED` + API message |
| `404 NOT_FOUND` | `GeminiRequestError` | model unavailable, check `GEMINI_MODEL` | `404 NOT_FOUND` + API message |
| `429` | `GeminiRequestError` | rate limited, retry shortly | `429 RESOURCE_EXHAUSTED` |
| `5xx` | `GeminiRequestError` | service temporarily unavailable | code + API message |
| Timeout | `GeminiRequestError` | took too long | exception type |
| Embedding failure | `EmbeddingError` | couldn't search the documents | classified message |
| Index unavailable | `VectorStoreError` | run the ingestion command | exception type |

- **No misleading key errors.** The original single `describe_error()` told the
  user to check the API key for any failure, including a 400 caused by a request
  setting. That is fixed: each category has its own wording, and a 400 says so
  explicitly.
- **Redaction.** `redact()` strips the configured key and any `key=`/`api_key=`/
  `access_token=` query parameter before anything is logged or returned;
  `detail` is capped at 300 characters. The API returns `code STATUS` plus that
  redacted message, never a stack trace.
- **Degraded but running.** A missing key, empty index or unavailable model
  produces a clear status and message instead of a crash. `/api/status` keeps
  answering.
- **Retry policy.** 429/5xx are retried once for generation (2 s backoff) and up
  to three times for embeddings. Timeouts are not retried, so a supervisor is
  not made to wait twice for the same failure.
- **`DEBUG` is off by default** so an unexpected exception cannot return a
  traceback (and frame locals) to the browser.

---

## 17. Document version management (factual)

- `document_registry.py` is the only place a document's identity is declared,
  and every field was read from the PDF (code, revision, title, effective date).
- The manifest records `active_revisions: {document_code: document_id}` and the
  supersession links (`supersedes_document_id` / `superseded_by_document_id`).
- QC-SOP-014 Rev 04 (01-Jul-2026) is active; Rev 03 (15-Mar-2023) is archived.
  Rev 03's chunks are written to `archived_chunks.json` only.
- Three independent guards keep Rev 03 out of an answer: it is never embedded,
  the query filters on `document_status="active"`, and retrieval re-checks the
  manifest. The live six-question run cited Rev 04 only.
- The pipeline refuses a PDF whose folder disagrees with its registered status,
  so moving Rev 03 into `Documents/active/` produces an error instead of a
  duplicate corpus.

---

## 18. Testing and validation (factual)

**Offline tests** — 19 tests, stdlib `unittest`, no network, no key:

```bat
python -m unittest discover -s tests -t . -v
```

| File | Covers |
| --- | --- |
| `tests/test_gemini_integration.py` (10) | thinking config per model family, the 400 retry dropping the hint, 404 classification, per-category user messages, redaction, JSON parsing |
| `tests/test_status_availability.py` (9) | model-availability probe: ready/unavailable/unauthorized/unknown/not-configured, capability check, caching, no key in the payload |

**Static check** — `python -m compileall backend tests` (clean).

**Live validation** (real key, `gemini-3.5-flash-lite` + `gemini-embedding-001`,
15 chunks indexed):

| Question | Result |
| --- | --- |
| TX-200 coolant concentration | 6 – 8 %, MNT-MAN-CNC-02 Rev 02 p1 |
| Alarm AL-104 | way lube oil level low → ISO VG 68 to MAX, press RESET, Rev 02 p2 |
| LOTO lock removal | each authorised person removes only their own lock, SAF-SOP-003 Rev 05 p1 |
| BH-220 OD tolerance | ±0.050 mm at 90.000 mm nominal, QC-SOP-014 Rev 04 p2 |
| Spindle runout | monthly, by a maintenance technician, MNT Rev 02 p1 |
| Annual electricity consumption | `insufficient_evidence`, fallback sentence, no sources |

All six returned HTTP 200 in 1.5–2.3 s. QC-SOP-014 Rev 03 appeared in no
answer and no source list.

**Error path validated live** by running a second instance with
`GEMINI_MODEL=gemini-2.5-does-not-exist`: `/api/status` reported
`model_status: "unavailable"` with the correct guidance, and `/api/chat`
returned `status: "error"` with a 404 NOT_FOUND diagnostic and no key material.

**Status probe** validated for both outcomes: `ready` for the configured model,
`unavailable` for the bogus one, and repeated calls served from cache (three
requests in 0.15 s).

**UI check** in a browser: grounded answer with "Answered from documents" and
the source card (code, revision, page, filename); abstention with "No matching
evidence" and no source cards; service error rendered as "Service error"; the
model status shown as "Available" on System Info.

---

## 19. Important engineering decisions (factual)

| Decision | Choice | Reason |
| --- | --- | --- |
| Vector store | ChromaDB, local, persistent | Required; runs offline on a plant laptop |
| Chunk size | 900 chars, 150 overlap, page-scoped | Fits SOP paragraphs; keeps citations exact |
| Embedding model | `gemini-embedding-001` | Same provider as generation, no extra dependency |
| Retrieval | Top 5, cosine, `>= 0.30` | Small corpus; the threshold filters weak evidence |
| Grounding | Evidence-only prompt + server-side check | Model output alone is not trusted |
| Citations | Built from retrieved chunks, not model text | Prevents fabricated references |
| Revision safety | Excluded at ingestion, filtered at query, re-checked against the manifest | One guard is a mistake away from a wrong safety instruction |
| Thinking config | `thinking_level` for Gemini 3+, nothing for older models, one retry without it on 400 | Model-family capability, not a magic constant |
| Model status | Cached model-list probe (TTL 10 min, 10 s timeout, 60 s retry on unknown) | Distinguishes "key present" from "model usable" without a Gemini call per refresh |
| Frontend | Vanilla HTML/CSS/JS, same origin | No build step, no framework, no Node runtime |
| Config | Pydantic Settings from `.env` | One place for models, paths, limits |
| Failure handling | Degraded-but-running | Missing key or index produces clear messages, not crashes |
| `DEBUG` | Off by default | No tracebacks or frame locals in an HTTP response |
| Tests | stdlib `unittest` | Offline, no new dependency |

The registry stores document identity read from the PDFs themselves rather than
parsing filenames, and the pipeline cross-checks code/revision/effective date
against page 1 so a misfiled or replaced PDF raises a warning instead of
poisoning the corpus.

---

## 20. Limitations and future improvements (factual)

**Limitations**

- No OCR; scanned pages without a text layer are flagged, not read.
- Tables are flattened to text during extraction.
- Retrieval quality and the 0.30 similarity floor have been validated on 15
  chunks, not tuned on a large corpus.
- `top_k=5` of a 15-chunk corpus is a third of the corpus; it would need
  re-tuning before the corpus grows.
- Model availability is sampled: up to 10 minutes of staleness after a model is
  disabled, and a network failure reports `unknown` rather than guessing.
- `thinking_level=low` was chosen for latency; other levels were not benchmarked
  for answer quality.
- No authentication; the app is intended for a trusted local network only.
- Single collection per deployment; no document upload UI.
- No streaming responses; the UI waits for the complete answer (1.5–4 s here).

**Future improvements**

- OCR fallback (e.g. Tesseract) for scanned SOPs, keeping the same page metadata.
- Table-aware extraction, retaining row/column structure for tolerance tables.
- An evaluation harness over a question set with known answers, to tune
  retrieval and thresholds and to catch regressions.
- Read-only audit log of questions and cited documents for quality reviews.
- Optional authentication and per-role access before any wider deployment.
- Streaming responses if the corpus and answer length grow.

---

## 21. Final reflection

`[USER INPUT REQUIRED: Write the honest retrospective in your own words: what
worked, what was harder than expected, what you would do differently, and what
you would tell the next person building this. Do not describe the AI's answers
as your own reasoning.]`

---

## 22. Input still needed from the author

Six sections above cannot be written for you, because they describe your own
experience and judgement. Each placeholder names the question; the short version:

1. **§1 Your user.** Who is the supervisor you pictured, and how do they look
   things up today?
2. **§2 Initial journey.** The step-by-step journey you wrote *before* asking
   an AI for feedback.
3. **§3 AI critique.** What the AI challenged when you shared that journey, and
   where you disagreed.
4. **§4 What changed.** What you changed after the critique, and why.
5. **§6 Why this improvement.** Why revision-aware page citations over the
   alternatives you considered.
6. **§21 Final reflection.** Your retrospective: what was harder than expected,
   what you would do differently.

Nothing in those sections has been drafted, paraphrased or inferred on your
behalf.
