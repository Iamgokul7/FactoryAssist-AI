# Demo video script — FactoryAssist AI (2–3 minutes)

Target length **2:45**. Everything below is recorded from the running
application; no slides are required, but the screenshots in `screenshots/` can
be used as a fallback if a live question is slow.

**Setup before recording**

```bat
.venv\Scripts\activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open <http://127.0.0.1:8000>. Confirm the two badges read **AI service ready**
and **15 chunks indexed** before you start recording.

---

## 0:00 – 0:18 · Problem

> A shop-floor supervisor needs an answer in seconds: what coolant
> concentration to run, what alarm AL-104 means, who may remove a lockout lock.
> That knowledge exists — in controlled SOP PDFs — but it is slow to search and
> old revisions are still in circulation. A generic chatbot makes this worse: it
> answers confidently from general knowledge and never shows its source.
> FactoryAssist AI answers only from the plant's own active documents, cites the
> exact page, and refuses when the documents do not contain the answer.

**Screen:** Dashboard, top badges and the four KPI tiles visible.

## 0:18 – 0:40 · Architecture and stack

> The stack is FastAPI and Uvicorn on Python 3.12, Google Gemini for both
> generation and embeddings, ChromaDB as the local vector store, PyMuPDF for PDF
> text, and a dependency-free HTML/CSS/JavaScript frontend served from the same
> origin. Four stages: document processing, indexing, retrieval and grounded
> generation.

**Screen:** scroll the dashboard to the active-document table.

## 0:40 – 1:00 · Document ingestion

> Three active documents — the TX-200 maintenance manual, the LOTO safety
> procedure and the quality SOP — are extracted page by page, checked against a
> registry of verified document identities, and split into page-scoped chunks of
> 900 characters with 150 characters of overlap. Those 15 chunks are embedded
> with `gemini-embedding-001` and written to ChromaDB.
>
> QC-SOP-014 Rev 03 is archived. It is never embedded, never retrieved and never
> cited — only Rev 04 is active.

**Screen:** Knowledge Base view — point at the active table, then the archived
revision row ("never retrieved by the assistant").

## 1:00 – 1:20 · RAG pipeline

> A question is embedded, the five closest chunks are retrieved from the active
> collection, anything below a 0.30 similarity floor is discarded, and every
> surviving chunk is re-checked against the manifest so a superseded revision
> cannot slip through. The model receives numbered evidence blocks and a system
> prompt that allows only facts from that evidence. It returns JSON with the
> answer, a supported flag, and the evidence numbers it used — and the server
> builds the citations from those chunks, never from model text.

**Screen:** System Info — "How it answers" steps and the runtime configuration.

## 1:20 – 2:05 · Live question answering with citations

**Ask 1 (coolant):**

> What is the recommended coolant concentration for the TX-200 CNC turning
> centre?

> Answer in about two seconds: 6 to 8 percent, from MNT-MAN-CNC-02 Revision 02,
> page 1 — with the document title, code, revision and page in the source card.

**Ask 2 (AL-104):**

> The machine is showing alarm AL-104. What does it mean and what should the
> operator do?

> Way lube oil level low, top up with ISO VG 68 to the MAX mark and press RESET,
> from page 2 of the same manual.

**Ask 3 (LOTO):**

> Who is allowed to remove a lockout lock from a machine?

> Each authorised person removes only their own lock, from SAF-SOP-003 Rev 05,
> page 1 — and note the answer keeps the exception about an absent owner rather
> than inventing procedure.

**Ask 4 (tolerance):**

> What is the outer diameter tolerance for the BH-220 bearing housing?

> Plus or minus 0.050 mm at 90.000 mm nominal, checked with a digital caliper,
> from QC-SOP-014 **Rev 04** — the active revision, never Rev 03.

**Screen:** AI Assistant. Let each source card stay on screen for a beat.

## 2:05 – 2:25 · Abstention

> What is the annual electricity consumption of the factory?

> The corpus does not contain that number, so the system returns "No matching
> evidence", the fixed fallback sentence, and **no sources**. It would rather
> refuse than guess — which is the behaviour that matters on a safety or quality
> question.

**Screen:** the amber fallback bubble with no source card.

## 2:25 – 2:45 · Closing

> FactoryAssist AI is a working, document-grounded copilot: 15 chunks indexed,
> six validation questions passing, page-level citations, revision isolation and
> honest refusal. The next steps would be OCR for scanned SOPs, table-aware
> extraction, and an evaluation harness to tune retrieval as the corpus grows.
> Thank you.

**Screen:** back to the dashboard, then stop.

---

## Recording checklist

- [ ] Server running on <http://127.0.0.1:8000>, both badges green.
- [ ] `.env` is not open in any editor, terminal or window that will be recorded.
- [ ] Terminal window cleared of any command output containing a key; no
      `env`, `set`, `pip config` or `.env` content on screen.
- [ ] Browser zoom 100 %, window at least 1280 × 800, bookmarks bar hidden.
- [ ] Other browser tabs, mail, chat and notification pop-ups closed.
- [ ] Start with a clean chat ("Clear conversation") for each take.
- [ ] Record at 1080p or 720p; voice-over can be recorded afterwards from this
      script if you prefer.
- [ ] Keep each answer on screen for ~3 seconds before moving on.
- [ ] Total runtime under 3 minutes; trim the AL-104 or LOTO question first if
      you run long.

## If a live question misbehaves

Do not re-record a fake answer. Wait for the request (2–4 s), and if the service
returns an error bubble, say what it says and move on — the error path is part of
the product. Screenshots `02`–`05` and `08` in `screenshots/` show the expected
output if you need to cut around a slow network.
