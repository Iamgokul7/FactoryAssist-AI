# FactoryAssist AI

**AI-powered Manufacturing SOP Copilot**

FactoryAssist AI helps manufacturing supervisors ask questions in natural
language about safety procedures, machine maintenance manuals and quality
inspection documents. Answers are grounded in the plant's own SOP PDFs rather
than in general knowledge.

---

## Current Development Stage

**Stage 2 - PDF Processing & Document Preparation (complete).**

Delivered so far:

- **Stage 1:** FastAPI skeleton with root and health endpoints, centralised
  `.env` configuration, pinned dependencies, project structure, Git repository.
- **Stage 2:** revision-aware PDF text extraction, chunking and structured JSON
  output for the SOP corpus. See
  [Document Processing Pipeline](#document-processing-pipeline-stage-2).

**Not implemented yet:** embedding generation, ChromaDB ingestion, semantic
search, Gemini answers, chat and upload endpoints, and the frontend
application. These arrive in Stages 3-6. The root endpoint still reports
`stage: 1`, as defined in Stage 1.

Because Gemini integration belongs to a later stage, the application starts
and serves both endpoints without a Gemini API key configured.

---

## Technology Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| AI generation | Google Gemini API (`google-genai`) |
| Embeddings | Gemini Embedding API |
| Vector database | ChromaDB (persistent local store) |
| PDF processing | PyMuPDF |
| Configuration | python-dotenv, Pydantic Settings |
| Version control | Git / GitHub |
| Deployment | Local network access over Wi-Fi |

No additional frameworks are used: there is no React, Node.js, Next.js, Flask,
LangChain or LlamaIndex in this project.

---

## Project Directory Structure

```
S:\BiztelAI Technologies. Assesment
│
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, root + health endpoints
│   ├── api/                    # API routers (later stages)
│   │   └── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py           # Centralised Pydantic Settings
│   ├── services/
│   │   ├── __init__.py
│   │   ├── document_models.py      # Document, page and chunk dataclasses
│   │   ├── document_registry.py    # Verified document metadata + revisions
│   │   ├── document_pipeline.py    # Stage 2 pipeline entry point
│   │   ├── pdf_processor.py        # PyMuPDF page-by-page extraction
│   │   └── text_chunker.py         # Page-scoped overlapping chunking
│   └── utils/                  # Shared helpers (later stages)
│       └── __init__.py
│
├── frontend/
│   ├── index.html              # Placeholder page (UI built in later stages)
│   ├── css/
│   └── js/
│
├── documents/
│   ├── active/                 # SOPs currently in the knowledge base
│   ├── archived/               # Superseded SOP versions
│   └── sample_questions/       # Example supervisor questions
│
├── data/
│   └── processed/              # Generated Stage 2 JSON (git-ignored)
├── vector_store/               # ChromaDB persistence (created at runtime)
├── screenshots/                # Evidence for the assignment write-up
│
├── README.md
├── THINKING.md
├── requirements.txt
├── .env                        # Local secrets (git-ignored)
├── .env.example                # Template, safe to commit
├── .gitignore
└── .venv/                      # Virtual environment (git-ignored)
```

Relative paths in `.env` (`CHROMA_PERSIST_DIRECTORY`, document directories) are
resolved against the project root by `backend/core/config.py`, so the
application can be started from any working directory.

---

## Python Environment Setup

The project uses an existing Python 3.12 installation (Python 3.14 is also
present on this machine, but ChromaDB's native dependency chain is most
reliably supported on 3.12). The system Python is left untouched; all
dependencies live in the project virtual environment.

Create the virtual environment (skip if `.venv` already exists):

```bat
cd "S:\BiztelAI Technologies. Assesment"
py -3.12 -m venv .venv
```

Activate it:

```bat
.venv\Scripts\activate
```

---

## Dependency Installation

With the virtual environment active:

```bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Pinned versions are listed in `requirements.txt`. To confirm the environment:

```bat
pip list
```

---

## Configuration

Configuration is read from the root `.env` file. Copy the template and adjust
it if you need a fresh file:

```bat
copy .env.example .env
```

| Variable | Purpose |
| --- | --- |
| `APP_NAME` | Application name used by FastAPI |
| `APP_VERSION` | Application version |
| `DEBUG` | Debug mode |
| `GEMINI_API_KEY` | Gemini API key (empty until the AI stage) |
| `GEMINI_MODEL` | Gemini generation model |
| `GEMINI_EMBEDDING_MODEL` | Gemini embedding model |
| `CHROMA_PERSIST_DIRECTORY` | ChromaDB persistence directory |
| `ACTIVE_DOCUMENTS_DIRECTORY` | Active SOP documents |
| `ARCHIVED_DOCUMENTS_DIRECTORY` | Archived SOP documents |
| `SAMPLE_QUESTIONS_DIRECTORY` | Sample questions sheet (kept out of the corpus) |
| `PROCESSED_DATA_DIRECTORY` | Generated Stage 2 JSON output |
| `CHUNK_SIZE` | Target chunk size in characters (default 900) |
| `CHUNK_OVERLAP` | Chunk overlap in characters (default 150) |
| `SERVER_HOST` | Bind address (`0.0.0.0` exposes the app on the local network) |
| `SERVER_PORT` | Server port |

`.env` is git-ignored. Never commit API keys, and never expose them to the
frontend JavaScript.

---

## Running the Application

From the project root, with the virtual environment active:

```bat
uvicorn backend.main:app --reload
```

Alternatively:

```bat
python -m backend.main
```

Then open <http://127.0.0.1:8000>.

| Endpoint | Response |
| --- | --- |
| `GET /` | `{"application": "FactoryAssist AI", "status": "running", "stage": 1}` |
| `GET /health` | `{"status": "healthy"}` |
| `GET /docs` | Interactive FastAPI documentation |

To reach the application from another device on the same Wi-Fi network, start
it with `SERVER_HOST=0.0.0.0` (the default) and open
`http://<this-computer-ip>:8000`. Windows Firewall may prompt for permission on
first run.

---

## Document Processing Pipeline (Stage 2)

PDFs are organized by role before processing:

| Folder | Documents | Status used for retrieval |
| --- | --- | --- |
| `documents/active/` | QC-SOP-014 Rev 04, SAF-SOP-003 Rev 05, MNT-MAN-CNC-02 Rev 02 | `active` |
| `documents/archived/` | QC-SOP-014 Rev 03 (superseded) | `archived` |
| `documents/sample_questions/` | Sample_Questions.pdf | `sample_questions` |

The original PDFs are also kept untouched in the parent `documents/` folder;
the pipeline only reads the three sub-folders, so no document is processed
twice.

Run the pipeline once from the project root:

```bat
python -m backend.services.document_pipeline
```

It extracts each page with PyMuPDF, verifies the document number, revision and
effective date against `document_registry.py`, chunks the text and writes:

| File | Contents |
| --- | --- |
| `data/processed/active_chunks.json` | Chunks from active revisions only |
| `data/processed/archived_chunks.json` | Chunks from superseded revisions |
| `data/processed/document_manifest.json` | Document metadata, active revision map, warnings |
| `data/processed/sample_questions_extracted.json` | Sample questions sheet, extracted but never chunked |

Processing rules:

- **Revision isolation.** QC-SOP-014 Rev 04 supersedes Rev 03. Rev 03 is
  processed into the archived set only, and the manifest records
  `superseded_by_document_id`, so it can be kept out of retrieval later.
- **Page traceability.** Chunks never cross a page boundary, so every chunk
  carries its exact page number, document code, revision and status.
- **No invented content.** Pages without extractable text are recorded as
  extraction warnings and left empty; no OCR is performed at this stage.
- **Chunking.** Target 900 characters with 150 characters of overlap on word,
  line and paragraph boundaries (`CHUNK_SIZE` / `CHUNK_OVERLAP`).

The generated JSON is a local build artifact and is git-ignored.

---

## Project Status

Stages 1 and 2 are complete. Stage 1 was verified with a single manual smoke
test (server start, `GET /` and `GET /health`); Stage 2 was verified with one
pipeline run. Later stages add embeddings, retrieval, grounded Gemini answers
and the chat frontend.
