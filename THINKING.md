# THINKING.md

Working notes for the FactoryAssist AI assignment.

## How to read this document

This document explains the problem FactoryAssist AI addresses, the
design and implementation choices behind it, how the application works,
and the main lessons from development and validation.

The technical sections describe the implemented application and its
recorded test results. The project rationale is written as a
retrospective explanation of the design, not as a claim of first-hand
manufacturing experience. AI tools were used as development assistance;
the implementation, configuration, testing and final project decisions
should be understood in that context.

------------------------------------------------------------------------

## 1. Problem being addressed

FactoryAssist AI is designed around a practical information-retrieval
problem: manufacturing procedures and maintenance instructions are often
stored in PDF documents, and finding a specific instruction can require
searching through several pages.

The assignment's sample documents include information about coolant
concentration, machine alarms, lockout/tagout (LOTO), dimensional
tolerances and maintenance schedules. These are examples of questions
for which a user needs a specific, verifiable instruction rather than a
general answer.

A second issue is document revision control. More than one revision of
an SOP may be present, even when an older revision has been superseded.
For example, QC-SOP-014 Rev 03 was replaced by Rev 04. A retrieval
system must not treat both revisions as equally current.

FactoryAssist AI addresses these problems by providing a
natural-language interface over a controlled document collection. The
answer should remain connected to the source document so that a user can
verify the instruction.

## 2. Intended workflow

The application is designed for a user who needs to look up a
manufacturing or maintenance instruction.

The intended workflow is:

1.  The user has a question about a machine, process, quality
    requirement or safety procedure.
2.  The user asks the question through the chat interface.
3.  The application searches the indexed, active documents for relevant
    passages.
4.  The answer is generated from the retrieved evidence.
5.  The interface displays the answer with document and page references.
6.  If the documents do not provide enough evidence, the application
    returns a fixed fallback instead of guessing.

This workflow does not replace an approved procedure, a qualified
technician or a manufacturer's instructions. Its purpose is to make the
supplied documents easier to search while preserving source
traceability.

## 3. Why a basic PDF chatbot is not enough

A simple chatbot connected to PDFs can still produce unreliable results
if it does not account for document status and evidence quality.

The main risks considered in this project were:

-   Retrieving a passage from an outdated revision.
-   Producing an answer that sounds plausible but is not supported by
    the supplied documents.
-   Giving a user an answer without showing where it came from.
-   Answering a question even though the indexed documents do not
    contain the required information.

These risks shaped the design. Retrieval, revision validation, citations
and refusal behaviour are treated as core parts of the application
rather than optional enhancements.

## 4. Main design priorities

The implementation focuses on three priorities:

-   **Use the approved revision:** normal retrieval must use active
    documents and must validate retrieved records against the current
    document manifest.
-   **Make answers traceable:** citations are built from retrieved
    document metadata, including document code, revision and page.
-   **Avoid unsupported answers:** when the available evidence is
    insufficient, the application returns a fixed fallback response.

For example, QC-SOP-014 Rev 04 is the active revision and should be used
instead of the archived Rev 03 for normal questions.

## 5. Main technical challenges

The project brings together document processing, semantic retrieval and
answer generation. Three challenges are especially important.

### 5.1 Traceability

A user should be able to check the source of an instruction. The
application uses page-level chunking and stores document metadata with
each chunk. Citations are assembled by the backend from the retrieved
records rather than being invented by the language model.

### 5.2 Revision correctness

Different revisions can contain different requirements. The application
therefore uses a document manifest, active-status filtering and a
further validation step before retrieved evidence is passed to Gemini.

### 5.3 Evidence-based refusal

The model should not fill gaps with general knowledge. The application
uses an evidence-bound prompt and server-side response checks. The
annual factory electricity-consumption question is an example of a
question that the supplied documents cannot answer; the expected
behaviour is to abstain and provide no citations.

## 6. Improvement priorities

Revision-aware retrieval and page-level citations were prioritised ahead
of features such as OCR and advanced table extraction.

This ordering follows the project's central requirement: retrieving the
correct approved instruction is more important than adding more ways to
process documents. Additional features would have limited value if the
application could still use an outdated SOP or produce unsupported
answers.

The current implementation therefore focuses on active-revision
filtering, source metadata and a controlled fallback. OCR and better
table extraction remain possible future improvements.

------------------------------------------------------------------------

## 7. Architecture

The application has four main stages. Document processing and indexing
are performed separately from normal question answering.

### Application flow

``` text
Documents/
    active/
    archived/
    sample_questions/
          |
          v
(1) PDF Processing
    PyMuPDF
          |
          v
data/processed/
    active_chunks
    archived_chunks
    manifest
    sample_questions_extracted
          |
          v
(2) Embedding Generation
    Gemini Embeddings
          |
          v
vector_store/chroma_db
    ChromaDB
          |
          v
(3) Retrieval
    Query Embedding
    Top-k Search
    Revision Validation
          |
          v
backend/services/rag_service.py
          |
          v
(4) Answer Generation
    Evidence-bound Prompt
    Gemini JSON Response
          |
          v
POST /api/chat
          |
          v
frontend/js/app.js
```

### Main application commands

  ------------------------------------------------------------------------------------------------
  Stage                   Entry point                                      Output
  ----------------------- ------------------------------------------------ -----------------------
  Document processing     `python -m backend.services.document_pipeline`   JSON chunks and
                                                                           manifest

  Indexing                `python -m backend.services.ingestion_service`   ChromaDB collection

  Serving                 `uvicorn backend.main:app`                       API and dashboard

  Configuration           `backend/core/config.py`                         Central Settings object
  ------------------------------------------------------------------------------------------------

Document processing is kept separate from the serving application. The
API reads the existing vector index when answering questions; it does
not extract PDFs or generate embeddings during ordinary chat requests.

## 8. Technology choices

  ------------------------------------------------------------------------
  Layer                   Technology               Purpose
  ----------------------- ------------------------ -----------------------
  Backend                 FastAPI and Uvicorn      API and application
                                                   server

  AI generation           Google Gen AI SDK and    Generates answers from
                          Gemini 3.5 Flash Lite    retrieved evidence

  Embeddings              `gemini-embedding-001`   Converts document
                                                   passages and questions
                                                   into vectors

  Vector database         ChromaDB                 Persistent local vector
                                                   storage and similarity
                                                   search

  PDF processing          PyMuPDF                  Extracts text page by
                                                   page

  Configuration           Pydantic Settings        Validates and
                                                   centralises application
                                                   settings

  Frontend                HTML, CSS and vanilla    Browser interface
                          JavaScript               without a separate
                                                   build process

  Testing                 Python `unittest`        Automated tests using
                                                   the standard library
  ------------------------------------------------------------------------

The recorded implementation uses `google-genai` 2.34.0, ChromaDB 1.5.9
and PyMuPDF 2.1. The exact dependency versions should be checked against
`requirements.txt` when reproducing the environment.

The frontend is served from the same origin as the API. A separate
Node.js runtime or frontend build process is not required. The
implementation does not use React, Next.js, Flask, LangChain or
LlamaIndex.

## 9. PDF processing

Implementation: `backend/services/pdf_processor.py`

The PDF processing component extracts information from the supplied
documents.

Key behaviours include:

-   **Page-by-page extraction:** text is extracted separately from each
    page using `page.get_text("text")`, preserving the original page
    number.
-   **No invented text:** a page with no extractable text is recorded as
    a warning; the application does not create replacement content.
-   **Failure handling:** password-protected, empty or corrupted PDFs
    are handled individually so one failed document does not stop the
    entire processing run.
-   **Text normalisation:** line endings, trailing spaces and
    unnecessary blank lines are cleaned up.
-   **Document verification:** the first page is checked against the
    registered document code, revision and effective date.
-   **Document registry:** `document_registry.py` identifies approved
    documents rather than relying only on filenames.

Unregistered documents and documents placed in the wrong folder are
skipped rather than processed with an assumed identity.

The original PDFs inside `Documents/` are not modified. The pipeline
reads the source files and writes processed output to `data/processed/`.

## 10. Chunking strategy

Implementation: `backend/services/text_chunker.py`

Extracted text is divided into smaller sections called chunks.

Implemented settings:

-   Chunk size: 900 characters.
-   Chunk overlap: 150 characters.
-   Page-level separation: each chunk belongs to one page.

Page-scoped chunks support accurate page citations. The chunker attempts
to split at natural boundaries such as paragraph breaks, line breaks and
spaces, reducing the chance of cutting an instruction in the middle of a
sentence.

A small remaining section at the end of a page can be merged with the
previous chunk when appropriate. Each chunk receives a stable ID based
on the document, page and chunk index, allowing existing records to be
updated without creating unnecessary duplicates.

### Processing results

For the supplied document set:

-   Three active documents produced 15 active chunks.
-   The archived revision produced three archived chunks.
-   The sample-questions PDF was extracted but not indexed.
-   PDF extraction completed with zero warnings and zero errors.

Archived chunks are retained for reference but are not embedded into the
active collection.

## 11. Embedding generation

Implementation: `backend/services/embedding_service.py`

Embeddings convert text into numerical vectors that represent semantic
meaning. The application uses Google's `gemini-embedding-001` model.

Two task types are used:

-   `RETRIEVAL_DOCUMENT` for document content.
-   `RETRIEVAL_QUERY` for user questions.

Embedding requests are sent in batches of 24. The service checks that
returned vectors match the number of submitted inputs and rejects empty
text before making an API request.

Temporary errors such as rate limits and server errors are retried up to
three times with a delay between attempts.

The ingestion process is incremental. It uses a SHA-256 hash of each
chunk to identify whether its content has changed. Unchanged chunks do
not need to be embedded again, avoiding unnecessary API usage.

## 12. Vector database implementation

Implementation: `backend/services/vector_store.py`

ChromaDB is used as the persistent local vector database.

-   Database path: `vector_store/chroma_db`
-   Collection: `factoryassist_active_documents`
-   Similarity metric: cosine distance
-   Similarity conversion: `1 - distance`, clamped between 0 and 1
-   Metadata: document ID, revision, page number, filename and chunk
    index
-   Updates: `upsert` uses stable chunk IDs to update records rather
    than create duplicates
-   Active indexing: the indexer reads `active_chunks.json`; archived
    chunks are not embedded into the active collection

ChromaDB stores and searches the vectors generated by Gemini; it does
not generate the embeddings itself.

## 13. Retrieval approach

Implementation: `backend/services/rag_service.py`

When a user submits a question:

1.  The question is converted into an embedding using `RETRIEVAL_QUERY`.
2.  ChromaDB searches for the five most relevant chunks.
3.  The search filters for records with `document_status == "active"`.
4.  Results below the configured similarity threshold of `0.30` are
    discarded.
5.  Remaining results are checked against the document manifest.
6.  Valid evidence is passed to Gemini for answer generation.

If no relevant evidence remains, the application returns the fixed
fallback response without calling the generation model.

The manifest check provides an additional safeguard: a record cannot be
used unless it matches the active revision, even if an outdated record
remains in the vector database.

During the recorded test run, the best-match similarity scores for the
five answerable questions were approximately 0.69 to 0.79.

## 14. Prompt engineering and grounding

The application uses a strict system instruction to control how Gemini
generates answers.

The model is instructed to:

-   Use only the supplied document evidence.
-   Avoid outside knowledge.
-   Never invent measurements, procedures or document references.
-   Return the required fallback response when evidence is insufficient.
-   Report conflicting values when supplied documents contain
    conflicting information.
-   Respond in the language used by the user.

Retrieved evidence is sent to Gemini in numbered blocks. Each block
includes the document title, code, revision, page and filename.

Gemini returns a structured JSON response containing:

-   `answer`
-   `supported`
-   `used_source_indices`

The generation configuration uses JSON response formatting, a
temperature of 0.2 and a maximum output of 1,024 tokens.

The backend validates the response before displaying it. If Gemini marks
an answer as unsupported, returns an empty answer or uses the fallback
response, the server returns the standard fallback with no citations.

Citations are generated from the actual retrieved chunks rather than
allowing Gemini to write source references itself. This reduces the risk
of fabricated document references.

## 15. Gemini integration and compatibility fix

Implementation:

-   `backend/services/gemini_client.py`
-   `backend/services/rag_service.py`

The application uses a shared Gemini client factory. The client is
created when first required and reused.

During integration, a `400 INVALID_ARGUMENT` error occurred with
`gemini-3.5-flash-lite`. The request configuration was tested one
parameter at a time. Basic generation, temperature and token settings,
system instruction, JSON response format and response schema were
accepted. The error appeared when `thinking_budget=0` was added.

The investigation identified a mismatch between the thinking
configuration and the model family. Gemini 3 uses `thinking_level`
rather than the older thinking-budget configuration.

The implementation was updated so that:

-   Gemini 3 and newer use the configured `thinking_level`.
-   Gemini 2.x and unversioned model aliases do not receive a thinking
    hint.
-   If a model rejects the thinking configuration with a 400 error, the
    application retries once without that hint.

This makes the integration more compatible with different model
configurations instead of relying on one fixed parameter.

## 16. Error handling

The application classifies errors rather than displaying the same
message for every failure.

  -----------------------------------------------------------------------
  Failure                             Application behaviour
  ----------------------------------- -----------------------------------
  Missing API key                     Explains that the key is not
                                      configured

  400 `INVALID_ARGUMENT`              Identifies a request or model
                                      configuration problem

  401 / 403                           Indicates an authentication or
                                      permission problem

  404 `NOT_FOUND`                     Indicates that the configured model
                                      is unavailable

  429                                 Indicates rate limiting and
                                      suggests retrying

  5xx                                 Reports a temporary service issue

  Timeout                             Reports that the request took too
                                      long

  Embedding failure                   Explains that document search could
                                      not be completed

  Missing vector index                Indicates that ingestion needs to
                                      be run
  -----------------------------------------------------------------------

Error classification prevents a request-configuration problem from being
incorrectly reported as an API-key issue.

The `redact()` function removes the configured API key and sensitive key
parameters before errors are logged or returned. Error details are
limited to 300 characters, and stack traces are not exposed to the
frontend.

The application can return useful status information when the model, API
key or vector index is unavailable. Generation requests retry temporary
429 and 5xx errors once. Embedding requests have separate retry
handling.

Debug mode is disabled by default to avoid exposing unnecessary internal
information.

## 17. Document version management

The original document registry is maintained in `document_registry.py`.
It contains the verified identity of each supplied document, including
its code, title, revision and effective date. The manifest records the
active revision and relationships between revisions.

For QC-SOP-014:

-   Rev 04, effective 01-Jul-2026, is active.
-   Rev 03, effective 15-Mar-2023, is archived.

The application uses multiple checks to prevent archived content from
appearing in normal answers:

1.  Archived chunks are not embedded into the active vector collection.
2.  Retrieval filters for active documents.
3.  Every retrieved result is checked against the active revision in the
    manifest.

The document pipeline also checks whether a PDF is stored in the correct
folder. If an archived document is placed in the active folder, the
pipeline reports an error rather than silently treating it as active.

### Revisions added through the application

Revisions uploaded through the management interface are not added to
`document_registry.py`. That file is a hand-verified catalogue of the
original assignment corpus. Runtime uploads are stored in
`data/managed/documents.json`.

`knowledge_base.py` merges both sources so that views and the retrieval
guard use one authoritative answer to which revision is active. A
managed activation overrides the manifest entry for the same document
code, and a managed archive cannot make the older manifest revision
active again.

## 18. Testing and validation

The application was tested using automated tests and live Gemini
requests.

### Automated tests

There are 92 offline tests using Python's standard-library `unittest`
framework. The original 19 cover Gemini integration and the status
probe; the additional tests cover document lifecycle and access control.

Run them using:

``` bash
python -m unittest discover -s tests -t . -v
```

  -------------------------------------------------------------------------
  Test file                             Coverage
  ------------------------------------- -----------------------------------
  `tests/test_gemini_integration.py`    Model-family thinking
                                        configuration, retry behaviour,
                                        error classification, key redaction
                                        and JSON parsing

  `tests/test_status_availability.py`   Model availability, authentication
                                        failures, caching and status
                                        responses

  `tests/test_document_management.py`   Upload validation, processing,
  (37 tests)                            retries, revision
                                        activation/archival, retrieval
                                        exclusion by status and dashboard
                                        counters

  `tests/test_access_control.py` (36    Anonymous 401,
  tests)                                employee/manager/admin permissions,
                                        CSRF, cookies, expiry, revocation,
                                        login rate limiting, audit content
                                        and unchanged chat contract
  -------------------------------------------------------------------------

The following static check also completed successfully:

``` bash
python -m compileall backend tests
```

### Live Gemini validation

The application was tested using:

-   Generation model: `gemini-3.5-flash-lite`
-   Embedding model: `gemini-embedding-001`
-   Indexed active chunks: 15

  -----------------------------------------------------------------------
  Question                            Expected result
  ----------------------------------- -----------------------------------
  TX-200 coolant concentration        6--8%, MNT-MAN-CNC-02 Rev 02, page
                                      1

  AL-104 alarm                        Way lube oil level low; top up ISO
                                      VG 68 oil to MAX and press RESET,
                                      Rev 02, page 2

  LOTO lock removal                   Each authorised person removes only
                                      their own lock, SAF-SOP-003 Rev 05,
                                      page 1

  BH-220 OD tolerance                 ±0.050 mm at 90.000 mm nominal,
                                      QC-SOP-014 Rev 04, page 2

  Spindle runout                      Monthly, performed by a maintenance
                                      technician, MNT Rev 02, page 1

  Annual electricity consumption      Insufficient evidence; fallback
                                      response with no sources
  -----------------------------------------------------------------------

All six live questions returned HTTP 200 responses. In the recorded
validation run, response times were between 1.5 and 2.3 seconds; later
re-runs ranged from about 2 to 6 seconds depending on API latency.

QC-SOP-014 Rev 03 did not appear in any answer or source list during the
tests.

### Error-path validation

A second application instance was tested with the unavailable model name
`gemini-2.5-does-not-exist`. The status endpoint correctly reported the
model as unavailable. The chat endpoint returned a 404 diagnostic
without exposing API-key information.

### Frontend validation

The interface was checked in a browser for:

-   Normal answers with source citations.
-   Answers showing document code, revision and page.
-   Questions without sufficient evidence.
-   Service errors.
-   Gemini model availability on the System Info page.

The interface displayed the expected results for these scenarios.

## 19. Important engineering decisions

  ------------------------------------------------------------------------
  Decision                Implementation           Reason
  ----------------------- ------------------------ -----------------------
  Vector database         Local persistent         Simple local deployment
                          ChromaDB

  Chunk size              900 characters with 150  Keeps relevant
                          overlap                  instructions together

  Chunk boundaries        Page-scoped              Supports accurate
                                                   citations

  Embedding model         `gemini-embedding-001`   Uses the selected
                                                   embedding provider

  Retrieval               Top 5 with cosine        Suitable for the small
                          similarity               document collection

  Similarity threshold    0.30                     Filters weak matches

  Grounding               Evidence-only prompt and Reduces unsupported
                          server checks            answers

  Citations               Generated from retrieved Avoids fabricated
                          chunks                   references

  Revision management     Ingestion filtering,     Prevents outdated
                          query filtering and      instructions from being
                          manifest checks          used

  Gemini configuration    Model-family-aware       Avoids incompatible API
                          thinking settings        parameters

  Model status            Cached availability      Avoids repeated model
                          check                    checks on every refresh

  Frontend                HTML, CSS and vanilla    No separate frontend
                          JavaScript               build process

  Configuration           Pydantic Settings and    Keeps configuration in
                          `.env`                   one place

  Error handling          Classified errors and    Makes failures easier
                          safe fallback responses  to understand

  Debug mode              Disabled by default      Avoids exposing
                                                   internal details

  Tests                   Standard-library         Keeps the testing setup
                          `unittest`               lightweight
  ------------------------------------------------------------------------

The document registry also verifies document identity against the PDF
content instead of trusting the filename alone. This helps prevent an
incorrectly named or misplaced PDF from entering the active document
collection.

## 20. Limitations and future improvements

The application is functional and passed the recorded validation, but it
has limitations.

### Current limitations

-   There is no OCR support for scanned PDFs without an extractable text
    layer.
-   PDF tables are converted into plain text, so some table
    relationships may be lost.
-   Retrieval has been tested on a small collection of 15 active chunks.
-   The current `top_k=5` setting may need adjustment as more documents
    are added.
-   Model availability information can be up to 10 minutes old because
    the result is cached.
-   `thinking_level=low` was selected for response speed; other levels
    were not benchmarked.
-   Chat does not require sign-in; only document management and the
    audit trail are gated.
-   Each deployment uses one vector collection.
-   Uploaded revisions are processed synchronously, and revision
    activation relies on a single-process lock. The application
    therefore assumes one Uvicorn worker.
-   Answers are displayed after generation rather than streamed.

### Possible future improvements

1.  Add OCR support for scanned manufacturing documents.
2.  Improve PDF table extraction so measurements and tolerances retain
    their relationships.
3.  Build a larger evaluation dataset with known answers to measure
    retrieval quality.
4.  Add read-only audit logs for questions and cited documents, subject
    to an appropriate privacy and retention policy.
5.  Add streaming responses for longer answers.
6.  Move managed-document coordination to a transactional database or
    job queue before using multiple application workers.
7.  Benchmark retrieval settings and model configurations against a
    larger document collection.

Improvements should be prioritised based on actual user and deployment
needs rather than adding features only to increase complexity.

## 21. Final reflection

This project brought together several parts of an AI application that
are easy to treat separately: PDF processing, chunking, embeddings,
vector search, prompt design, answer generation, API integration and
frontend behaviour.

One of the main engineering lessons is that a RAG application is not
reliable just because it can retrieve text and generate a fluent answer.
The retrieved passage must belong to the correct document revision, the
source must be traceable, and the application must be able to refuse a
question when the evidence is missing.

The Gemini integration also showed why API configuration needs to be
tested rather than assumed. The thinking-configuration incompatibility
required isolating request parameters and handling model families
differently.

The validation work was important because it exposed issues that were
not obvious from reading the code alone. The address-wide login lockout,
CSS rule overriding the `hidden` attribute and Windows file-handle issue
were found during live testing and corrected.

If development continued, the next priorities would be a larger
retrieval evaluation set, OCR and better table extraction, followed by
deployment improvements for multi-worker operation.

## 22. Closing notes

FactoryAssist AI provides a natural-language interface for searching
manufacturing SOP and maintenance information.

The project focuses on traceable answers, correct document revisions and
refusal when the supplied evidence is insufficient.

The implemented application demonstrates:

-   PDF processing and document metadata management.
-   Text chunking and Gemini embedding generation.
-   Persistent vector storage using ChromaDB.
-   Revision-aware retrieval.
-   Evidence-grounded Gemini responses.
-   Page-level source citations.
-   Fallback handling for unsupported questions.
-   API and frontend integration.
-   Automated tests and live validation.
-   Document upload, review, activation and archival.
-   Authentication, role-based access control and audit logging.

------------------------------------------------------------------------

## 23. Document management, access control and governance

The original application operated on a read-only document corpus. A
manufacturing document collection also needs a way to manage procedures
as they are uploaded, reviewed, approved and retired.

The document-management stage adds that lifecycle. Managers can upload,
review, activate and archive revisions without replacing the existing
answer-generation pipeline.

### 23.1 Architecture

Three components were added, each with a defined responsibility:

``` text
Upload (ADMIN / SOP_MANAGER)
    |
    v
document_manager.py ---- validation, processing, activation, archival
    |                        |
    |                        +--> management_store.py  (data/managed/documents.json)
    |                        +--> auth_store.py        (data/managed/app.db)
    |
    +--> pdf_processor.extract_document     (existing)
    +--> text_chunker.chunk_document        (existing)
    +--> embedding_service.embed_documents  (existing)
    +--> vector_store.upsert                (existing collection)
                                   |
                                   v
                         ChromaDB: document_status metadata
                                   |
                                   v
                     rag_service query filter document_status = active
```

The upload path reuses the same processing functions as the baseline
pipeline. A managed document therefore produces chunks with the same
structure, metadata and citation behaviour as curated documents.

### 23.2 Why two storage mechanisms

Accounts, sessions and audit entries need transactions, uniqueness
constraints and constant-time lookups. They are stored in SQLite, which
is included with Python and does not require another service.

Document records are small, are written by governance actions and need
to be readable by the retrieval path without opening a database
connection. They are stored in one JSON file, written through a
temporary file and `os.replace`. This provides an atomic file
replacement for the document-record update.

The trade-off is that the JSON store assumes one application process. A
multi-worker deployment would need to move those records into the same
SQLite database or introduce a suitable coordination mechanism. This is
recorded as a limitation.

### 23.3 Status model and retrieval exclusion

``` text
processing -> pending_review -> active -> archived
                   |              |
                   +-> rejected   +-> archived by manager
                   +-> failed -> retry -> pending_review
```

Retrieval is protected at three levels:

1.  The embedding/index path stores `document_status` on every chunk.
2.  The ChromaDB query filters for `document_status = active`, so
    pending work is not a candidate.
3.  `RagService._keep_active` checks the chunk status and active
    revision map again, preventing a stale index from exposing a
    superseded revision.

Pending chunks share the active collection rather than using a second
collection. With a status field, activation is a metadata transition and
archival is a deletion; the guard map determines what is visible.

### 23.4 Making activation safe

The requirement is to avoid leaving a document code without an active
revision or with two active revisions. The implementation orders the
steps as follows:

1.  Verify that the new revision is `pending_review` and its indexed
    chunk count matches the record.
2.  Change the new chunks to `active` in ChromaDB. At this point the
    store still maps the code to the old revision, so retrieval
    continues to exclude the new chunks.
3.  Write both records --- new revision active, old revision archived,
    links set and approver recorded --- in one atomic JSON write. This
    is the commit point.
4.  Delete the superseded revision's chunks on a best-effort basis. If
    deletion fails, the status filter already hides them.

If step 2 fails, the records are unchanged. If step 3 fails, the chunk
status is rolled back and the old revision remains active. Step 4
affects storage hygiene rather than retrieval correctness. A
process-wide lock serialises concurrent activations within the supported
single-process deployment.

### 23.5 Authentication decisions

-   **Password hashing:** PBKDF2-HMAC-SHA256 with a per-password salt
    and 600,000 iterations, encoded as
    `pbkdf2_sha256$iterations$salt$hash`. The iteration count is stored
    so it can be increased later without invalidating existing accounts.
-   **Sessions:** the cookie holds a random 256-bit token. SQLite stores
    only its SHA-256 fingerprint and an expiry, so a database copy does
    not contain a replayable session token.
-   **Cookies:** HttpOnly, SameSite=Lax, `Path=/`, and Secure when the
    request is HTTPS or `SESSION_COOKIE_SECURE=true`. On the default
    plain-HTTP local deployment, Secure is omitted because a Secure
    cookie would not be sent over HTTP.
-   **CSRF:** each session has its own token, returned by `/api/auth/me`
    and required in `X-CSRF-Token` for POST/PATCH/PUT/DELETE. The Origin
    header is also compared with Host.
-   **Rate limiting:** failed sign-ins are counted per account and per
    client address. The limits are five failures per account and twenty
    failures per address within the configured window. This replaced a
    single username-plus-IP counter that, during live testing, could
    lock out every user behind a shared office IP after one person's
    mistakes. The audit table stores the events, so the limits survive a
    restart.
-   **Authorisation:** role checks live in FastAPI dependencies
    (`require_manager`, `require_admin`), not only in the browser. The
    UI hides controls that a user cannot access, but each API route
    enforces its own permission.

### 23.6 Upload validation decisions

A PDF upload is untrusted input that is passed to a parser and vector
store. Validation therefore happens in order of cost:

1.  Enforce the configurable size cap before further processing (25 MB
    by default).
2.  Check extension and MIME type; neither is treated as sufficient
    proof.
3.  Check for the `%PDF-` signature in the first kilobyte because the
    extension and MIME type are client-controlled.
4.  Save under a generated name derived from the document key and a
    random suffix. Keep the original filename only as a display label.
5.  Open with PyMuPDF. Encrypted, zero-page, unreadable and textless
    files are refused with specific messages.
6.  Check for duplicate code/revision, duplicate file content and
    revisions already present in the curated corpus.

Scanned PDFs are refused rather than silently indexed as empty
documents. OCR is outside the current scope.

### 23.7 Classification as a review aid

Keyword density over extracted text produces a simple
manufacturing-relevance score. A low score adds a warning to the record
and a `check` marker in the table. It does not block or approve a
document. The review decision remains with the manager because the score
is a basic heuristic.

### 23.8 Failure handling

-   Processing failures mark the record `failed` with a short, safe
    message, delete partial chunks and retain the stored file so a retry
    is possible.
-   Retrying reuses existing embeddings when the chunk set is unchanged,
    avoiding repeated embedding charges after a later-stage failure.
-   A server restart marks a record left in `processing` as `failed`
    with an interruption message instead of leaving it in a state that
    cannot finish.
-   API errors return short messages. Exception types and status codes
    are written to the server log rather than exposed to the browser.

### 23.9 Audit trail

Sign-in success and failure, rate-limit blocks, logout, uploads,
validation failures, processing results, retries, rejections,
activations, archival, metadata changes, account changes and
unauthorised management access are recorded.

Audit entries include timestamp, actor, action, document key, revision,
result and a short detail. Passwords, tokens and keys are not included
in audit records. Tests check that the API's audit payload does not
contain them.

### 23.10 What this stage deliberately does not do

-   Processing is synchronous inside the upload request. This keeps the
    result visible to the user for small documents, but a large manual
    could block the request. A job queue would be a future improvement.
-   Chat remains available without sign-in. Document management is
    gated, matching the requirement that unauthenticated users must not
    have management access while preserving the existing assistant.
-   Scanned documents still require an OCR step before they can be
    indexed.

### 23.11 Validation

The recorded offline suite contains 92 tests: the original 19 plus 73
covering upload validation, processing, retries, revision activation and
archival, retrieval exclusion for non-active statuses, roles, CSRF, rate
limiting per account and address, session expiry, audit content and the
unchanged chat contract.

Live validation on the running application supplemented the automated
tests. Real accounts were created through the API; the
anonymous/employee/manager/admin permission matrix was exercised over
HTTP; upload failure modes were attempted; workflows A--E were performed
end to end; the six original questions were asked against live Gemini;
and the management interface was checked in a browser across upload,
drag-and-drop, client validation, search, filters, details, activation,
archival, rejection, audit and a mobile viewport.

Three defects were found and fixed during this validation:

1.  An address-wide login lockout that could affect users sharing an
    office IP.
2.  A CSS rule that overrode the browser's `hidden` attribute.
3.  A Windows file handle that could leave rejected PDFs on disk.

After validation, the baseline corpus was restored to 15 active chunks,
three active documents and one archived revision. The detailed results
are recorded in `DOCUMENT_UPLOAD_TEST_REPORT.md`.
