# THINKING.md

Working notes for the FactoryAssist AI assignment.

**How to read this file.** Technical sections describe what was actually built
and why, based on the implementation in this repository. Sections that require
the author's own independent thinking — the initial journey, the AI critique,
and the personal reflection — are marked `[USER INPUT REQUIRED]` and have not
been filled in. Nothing in those sections has been invented on the author's
behalf.

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

## 7. Product and technical decisions (factual)

| Decision | Choice | Reason |
| --- | --- | --- |
| Vector store | ChromaDB, local, persistent | Required by the brief; runs offline on a plant laptop |
| Chunk size | 900 chars, 150 overlap, page-scoped | Fits SOP paragraphs; keeps citations exact |
| Embedding model | `gemini-embedding-001` | Same provider as generation, no extra dependency |
| Retrieval | Top 5, cosine, `>= 0.30` similarity | Small corpus; threshold filters weak evidence |
| Grounding | Evidence-only system prompt + server-side check | Model output alone is not trusted |
| Citations | Built from retrieved chunks, not model text | Prevents fabricated references |
| Frontend | Vanilla HTML/CSS/JS served by FastAPI | No build step, no framework, same origin |
| Config | Pydantic Settings from `.env` | One place for models, paths, limits |
| Failure handling | Degraded-but-running | Missing key or index produces clear messages, not crashes |

The registry (`document_registry.py`) intentionally stores document identity read
from the PDFs themselves, rather than parsing filenames, and the pipeline
cross-checks code/revision/effective date against page 1 so a misfiled or
replaced PDF raises a warning instead of poisoning the corpus.

---

## 8. Limitations and future improvements (factual)

**Limitations**

- No OCR; scanned pages without a text layer are flagged, not read.
- Tables are flattened to text during extraction.
- Retrieval quality and the 0.30 similarity floor have not been tuned on a
  large corpus (see the note below on live validation).
- No authentication; the app is intended for a trusted local network only.
- Single collection per deployment; no document upload UI.

**Future improvements**

- OCR fallback (e.g. Tesseract) for scanned SOPs, with the same page metadata.
- Table-aware extraction, retaining row/column structure for tolerance tables.
- Evaluation harness over a question set with known answers, to tune retrieval
  and thresholds.
- Read-only audit log of questions and cited documents for quality reviews.
- Optional authentication and per-role access before any wider deployment.

---

## 9. Validation status

Document extraction, chunking, revision isolation, the API contract, error
paths, and the dashboard were verified during the build.

Live AI validation — ingestion, retrieval quality against the five sample
questions, and generated answers — **could not be run** because no
`GEMINI_API_KEY` was available in `.env`. The prompt, retrieval and citation
code paths were exercised with stand-in components to prove the plumbing, but
the semantic quality of Gemini's answers is unverified. Once a key is added,
run ingestion and the five sample questions and record the results.

---

## 10. Final reflection

`[USER INPUT REQUIRED: Write the honest retrospective in your own words: what
worked, what was harder than expected, what you would do differently, and what
you would tell the next person building this. Do not describe the AI's answers
as your own reasoning.]`
