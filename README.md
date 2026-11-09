# FactoryAssist AI — Manufacturing SOP Copilot

An AI copilot for manufacturing shop-floor supervisors. Supervisors ask a
practical question in natural language and get an answer grounded strictly in
the plant's own controlled documents — safety procedures, maintenance manuals
and quality SOPs — with the document code, revision and page number attached.

The application refuses to answer when the documents do not contain the
information, and it never retrieves superseded revisions.

---

## Problem

Supervisors on the shop floor need answers in seconds: what coolant
concentration to run, what an alarm code means, who may remove a lockout lock,
what tolerance applies to a bearing housing. That knowledge lives in PDF SOPs
that are hard to search under time pressure, and old revisions stay in
circulation. A wrong answer on a safety or quality question is expensive.

Generic chatbots make this worse: they answer confidently from general
knowledge and cannot show where an instruction came from.

## Target users

- Manufacturing supervisors and shift leads on the shop floor.
- Maintenance technicians and quality inspectors checking a procedure.
- Anyone who needs to verify which revision of a document is current.

## Key features

- **Grounded answers only** — retrieval-augmented generation restricted to the
  indexed, active documents.
- **Page-level citations** — document title, code, revision, page and filename
  for every answer.
- **Revision-aware corpus** — QC-SOP-014 Rev 04 is active; Rev 03 is archived
  and excluded from retrieval, never merged with Rev 04.
- **Explicit refusal** — a clear fallback message when the evidence is
  insufficient, with no invented values, procedures or citations.
- **Live operational dashboard** — corpus, index and configuration status,
  knowledge-base view, and a chat interface with source cards.
- **Mobile-friendly** — usable from a phone on the same Wi-Fi network.

---

## Technology stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Configuration | python-dotenv, Pydantic Settings |
| AI generation | Google Gemini API (`google-genai` 2.34.0) |
| Embeddings | Gemini Embedding API (`gemini-embedding-001`) |
| Vector database | ChromaDB 1.5.9 (local, persistent) |
| PDF processing | PyMuPDF 2.1 |
| Frontend | HTML5, CSS3, vanilla JavaScript (no framework) |

No React, Node.js, Next.js, Flask, LangChain or LlamaIndex is used.

## Architecture

```
PDFs → PyMuPDF extraction → page-scoped chunking → JSON (Stage 2)
                                                      │
                                     Gemini embeddings│
                                                      ▼
                                             ChromaDB (active only)
                                                      │
question → Gemini query embedding → cosine search ───┘
                                                      │
                            evidence + strict prompt ▼
                                             Gemini generation
                                                      │
                                 answer + cited sources (API/UI)
```

Four rules hold the design together:

1. Chunks never cross a page boundary, so every citation is exact.
2. Only active revisions are embedded into the vector store.
3. The generation prompt forbids outside knowledge and invented citations.
4. Sources are built from the chunks that were actually retrieved and used —
   never from model text.

---

## Project structure

```
S:\BiztelAI Technologies. Assesment
├── backend/
│   ├── main.py                     # FastAPI app, dashboard + API
│   ├── api/
│   │   ├── chat.py                 # POST /api/chat
│   │   └── health.py               # GET /health, GET /api/status
│   ├── core/config.py              # Centralised Pydantic Settings
│   └── services/
│       ├── document_pipeline.py    # Stage 2: extract + chunk + write JSON
│       ├── document_registry.py    # Verified document metadata/revisions
│       ├── pdf_processor.py        # PyMuPDF page extraction
│       ├── text_chunker.py         # Page-scoped overlapping chunks
│       ├── embedding_service.py    # Gemini embeddings (batched, retried)
│       ├── vector_store.py         # ChromaDB collection wrapper
│       ├── ingestion_service.py    # Embed + index active chunks
│       ├── knowledge_base.py       # Reads the document manifest
│       ├── rag_service.py          # Retrieval, grounding, citations
│       └── gemini_client.py        # Shared client, error descriptions
├── frontend/
│   ├── index.html                  # Dashboard shell
│   ├── css/styles.css
│   └── js/app.js
├── Documents/
│   ├── active/                     # 3 current SOPs/manuals
│   ├── archived/                   # QC-SOP-014 Rev 03
│   └── sample_questions/           # Assignment sample questions
├── data/processed/                 # Generated JSON (git-ignored)
├── vector_store/chroma_db/         # ChromaDB persistence (git-ignored)
├── requirements.txt
├── .env / .env.example
└── README.md, THINKING.md
```

The original PDFs also remain untouched in `Documents/`; the pipeline reads only
the three sub-folders.

---

## Prerequisites

- Windows with Python 3.12 installed (`py -3.12 --version`).
- Internet access for the Gemini API (document processing works offline).
- A Google Gemini API key for embeddings and answers.

## Installation

```bat
cd "S:\BiztelAI Technologies. Assesment"
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Configure the Gemini API key

The application starts and serves the dashboard without a key, but chat and
ingestion stay disabled until one is present.

1. Open `.env` in the project root (copy `.env.example` if it is missing).
2. Set the key:

```ini
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
```

3. Restart the server. No source change is needed — the key is read at startup
   and never sent to the browser.

`.env` is git-ignored. Do not commit it.

## Document processing (Stage 2)

Only needed when the PDFs change:

```bat
python -m backend.services.document_pipeline
```

Writes `data/processed/active_chunks.json`, `archived_chunks.json`,
`document_manifest.json` and `sample_questions_extracted.json`.

## Indexing (Stage 3)

```bat
python -m backend.services.ingestion_service
```

Embeds the active chunks and writes them to the ChromaDB collection
`factoryassist_active_documents`. Re-running is safe: unchanged chunks are
skipped, changed chunks are updated, and removed chunks are deleted — no
duplicates. Requires `GEMINI_API_KEY`.

## Run the application

```bat
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open <http://127.0.0.1:8000>. The dashboard and API are served from the same
origin; there is no separate frontend server.

## Access from a phone on the same Wi-Fi

1. Find the laptop's IPv4 address:

```bat
ipconfig
```

2. Open `http://<LAPTOP-IP>:8000` on the phone (for example
   `http://192.168.1.24:8000`).
3. Both devices must be on the same Wi-Fi network.
4. If Windows Firewall prompts, allow Python on **private** networks. If it was
   dismissed earlier, allow `python.exe` through Windows Defender Firewall for
   Private networks.

The server binds to `0.0.0.0`, so it is reachable on the local network, but it
is not exposed to the public internet and there is no cloud deployment.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Dashboard in a browser; application info JSON for API clients |
| `GET` | `/health` | Health check — `{"status": "healthy"}` |
| `GET` | `/api/status` | Service availability, corpus, revisions, retrieval settings |
| `POST` | `/api/chat` | Grounded answer with sources |
| `GET` | `/docs` | Interactive OpenAPI documentation |

### `POST /api/chat`

```json
{ "question": "What does alarm AL-104 mean?" }
```

```json
{
  "status": "answered",
  "answer": "...",
  "sources": [
    {
      "document_id": "mnt-man-cnc-02-rev02",
      "document_title": "Preventive Maintenance Manual - TX-200 CNC Turning Centre",
      "document_code": "MNT-MAN-CNC-02",
      "revision": "02",
      "page_number": 2,
      "source_filename": "MNT-MAN-CNC-02_TX-200_Preventive_Maintenance.pdf",
      "similarity": 0.71
    }
  ],
  "grounded": true,
  "detail": null
}
```

`status` is one of `answered`, `insufficient_evidence`, `not_configured`,
`error`, `invalid_question`. Business outcomes return HTTP 200 with an explicit
status; empty questions return 400 and malformed bodies 422.

## Sample questions

The five assignment questions, also offered as chips in the UI:

1. What is the recommended coolant concentration for the TX-200 CNC?
2. What does alarm AL-104 mean?
3. Who can remove a LOTO lock?
4. What is the tolerance for bearing housing BH-220?
5. How often should spindle runout be checked?

### Expected answers and citations

Taken from the source PDFs; the application generates these itself at runtime —
nothing is hardcoded.

| # | Expected answer | Source |
| --- | --- | --- |
| 1 | Coolant concentration 6 – 8 %, checked with a refractometer reading × 1.0 factor | MNT-MAN-CNC-02 Rev 02, page 1, §3 |
| 2 | AL-104 = way lube oil level low. Top up with ISO VG 68 oil to the MAX mark, then press RESET; the machine can continue after reset | MNT-MAN-CNC-02 Rev 02, page 2, §6 |
| 3 | Each authorised person removes only their own lock; nobody may remove another person's lock | SAF-SOP-003 Rev 05, page 1, §5 |
| 4 | Outer diameter 90.000 mm with ±0.050 mm tolerance, checked with a digital caliper, class Major | QC-SOP-014 Rev 04, page 2, §6 |
| 5 | Monthly, by a maintenance technician (spindle runout limit 0.005 mm at the chuck face) | MNT-MAN-CNC-02 Rev 02, page 1, §3–4 |

### Unanswerable question

> "What is the annual electricity consumption of the factory?"

Expected: `status: "insufficient_evidence"`, the fixed fallback sentence, and
**no sources**. The value appears nowhere in the documents, so nothing is
invented.

## How answers are produced

1. The question is embedded with the configured embedding model.
2. The top 5 chunks by cosine similarity are retrieved from the active
   collection only, then filtered by `RETRIEVAL_MIN_SIMILARITY` (default 0.30).
3. Each chunk is re-checked against the manifest: its revision must be the
   active revision for its document code.
4. Gemini receives the numbered evidence blocks and a system prompt that
   permits only facts from that evidence, forbids invented values, steps and
   citations, and requires the exact fallback sentence when unsupported.
5. The model returns JSON (`answer`, `supported`, `used_source_indices`);
   sources are assembled from the chunks it used. If it reports `supported:
   false`, the server returns the fallback with no sources.

### Active versus archived revisions

| Document | Active | Archived |
| --- | --- | --- |
| QC-SOP-014 Incoming Material Inspection | Rev 04 (01-Jul-2026) | Rev 03 (15-Mar-2023) |
| SAF-SOP-003 Lockout/Tagout | Rev 05 (12-Feb-2026) | — |
| MNT-MAN-CNC-02 TX-200 Maintenance | Rev 02 (20-Jan-2026) | — |

Rev 03 stays in `data/processed/archived_chunks.json` for reference and in the
Knowledge Base view, but it is never embedded into the active collection, never
retrieved, and never cited.

## Security notes

- `GEMINI_API_KEY` lives only in `.env` (git-ignored) and on the server; the
  browser never receives it.
- No credentials, stack traces or key material are returned by the API.
- `.venv/`, `data/processed/`, `vector_store/chroma_db/`, caches and logs are
  git-ignored.
- The app has **no authentication** and binds to the local network. Do not port
  forward it or expose it to the internet.
- Answers should support, not replace, the controlled SOP and the responsible
  supervisor.

## Known limitations

- Requires a paid/free-tier Gemini API key; without it the UI runs but chat and
  ingestion are disabled with a clear message.
- No OCR: scanned pages without a text layer are reported as extraction
  warnings and left empty.
- Tables are extracted as plain text, so very wide tables read awkwardly in
  chunks.
- The similarity floor (0.30) and `RETRIEVAL_TOP_K` (5) are sensible defaults,
  but have not been tuned on a large corpus.
- Single-plant, single-collection deployment; no user accounts, no audit trail,
  no document upload UI.

## Project status

Stages 1–6 are implemented: foundation, PDF processing, embeddings/ChromaDB,
RAG, FastAPI + dashboard, and documentation.

**Live AI validation is pending** — no `GEMINI_API_KEY` was configured during
the build, so ingestion, retrieval quality and answer generation have not been
executed against the Gemini API. Document extraction, chunking, the API, the
error paths and the dashboard were verified.
