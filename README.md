# FactoryAssist AI

**AI-powered Manufacturing SOP Copilot**

FactoryAssist AI helps manufacturing supervisors ask questions in natural
language about safety procedures, machine maintenance manuals and quality
inspection documents. Answers are grounded in the plant's own SOP PDFs rather
than in general knowledge.

---

## Current Development Stage

**Stage 1 - Project Foundation & Environment Setup (complete).**

Stage 1 delivers the project skeleton only:

- FastAPI application with a root and a health-check endpoint.
- Centralised, `.env`-driven configuration via Pydantic Settings.
- Virtual environment and pinned dependencies.
- Project directory structure prepared for later stages.
- Git repository initialised.

**Not implemented yet:** the AI chat interface, PDF upload, text extraction,
embedding generation, ChromaDB retrieval, Gemini calls and the frontend
application. These arrive in Stages 2-6. The root endpoint reports `stage: 1`
to make this explicit.

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
│   ├── services/               # PDF, embedding, retrieval, chat (later stages)
│   │   └── __init__.py
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

## Project Status

Stage 1 is complete and verified with a single manual smoke test (server start,
`GET /` and `GET /health`). Later stages add document ingestion, retrieval,
grounded Gemini answers and the chat frontend.
