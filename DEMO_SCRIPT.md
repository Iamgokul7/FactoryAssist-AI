# Demo Video Script — FactoryAssist AI

## Recorded Demo

**Status: RECORDED**

The FactoryAssist AI demonstration is available at:

`assets/demo/factoryassist-demo.mp4`

| Property | Specification |
|---|---|
| Duration | 4 minutes 37 seconds |
| Resolution | 1920 × 1080 |
| Video format | H.264 |
| Audio format | AAC |
| Frame rate | 12 FPS |
| Narration | Synthetic Windows SAPI voice (Microsoft Zira) |

The recording follows the ten-scene sequence documented in `assets/demo/README.md`.

Supporting assets:

- Workflow GIF: `assets/demo/factoryassist-workflow.gif`
- Demo screenshots: `assets/screenshots/`
- Original application screenshots: `screenshots/`

The recording demonstrates the running application, actual AI responses, source citations, abstention behaviour, authentication, and the document registration interface.

**Recording disclosure:** The document upload form is filled with a draft revision, but the submission button is not pressed. No new document is uploaded or activated during the recording. The document register therefore remains empty.

---

## 1. Recorded Demo Sequence

### 00:03 – 00:40 · Dashboard Overview

**Narration:**

> A shop-floor supervisor needs reliable answers quickly. What coolant concentration should an operator use? What does a machine alarm mean? Which document revision contains the correct procedure?
>
> FactoryAssist AI is designed to make controlled manufacturing knowledge easier to access. It uses the plant's approved SOP documents to answer questions, provides source citations, and avoids inventing information when supporting evidence is unavailable.

**Screen:**

- Open the application dashboard.
- Show the status indicators and KPI tiles.
- Briefly introduce the application.

### 00:40 – 01:05 · Knowledge Base

**Narration:**

> The knowledge base contains three active manufacturing documents covering machine maintenance, lockout and tagout safety, and quality procedures.
>
> Document revisions are controlled so that archived versions do not become sources for new answers.

**Screen:**

- Open the Knowledge Base.
- Show the active document table.
- Point out the archived QC-SOP-014 Rev 03 entry.
- Explain that Rev 04 is the active revision.

### 01:05 – 01:27 · System Information

**Narration:**

> FactoryAssist AI uses a retrieval-augmented generation pipeline. Documents are processed, converted into searchable chunks, and retrieved as evidence when a user asks a question.
>
> The application uses Google Gemini for generation and embeddings, with ChromaDB as its local vector store.

**Screen:**

- Open System Info.
- Show the model availability status.
- Highlight the "How it answers" explanation and runtime configuration.

### 01:27 – 01:55 · Coolant Question

**Question:**

> What is the recommended coolant concentration for the TX-200 CNC turning centre?

**Expected response:**

> Maintain the coolant concentration between 6% and 8%.

**Source:**

`MNT-MAN-CNC-02 Rev 02`, page 1.

**Narration:**

> The assistant retrieves the coolant recommendation directly from the maintenance manual. The answer includes a source citation so the operator can verify the information.

**Screen:**

- Ask the question in AI Assistant.
- Show the answer and source card.

### 01:55 – 02:21 · AL-104 Alarm

**Question:**

> The machine is showing alarm AL-104. What does it mean and what should the operator do?

**Expected response:**

> The way-lubrication oil level is low. Top up with ISO VG 68 oil to the MAX mark and press RESET.

**Source:**

`MNT-MAN-CNC-02 Rev 02`, page 2.

**Narration:**

> Instead of providing a generic troubleshooting suggestion, the assistant retrieves the documented alarm procedure and presents the required operator action.

**Screen:**

- Ask the AL-104 question.
- Show the answer and source citation.

### 02:21 – 02:44 · Quality Tolerance

**Question:**

> What is the outer diameter tolerance for the BH-220 bearing housing?

**Expected response:**

> Plus or minus 0.050 millimetres at a nominal diameter of 90.000 millimetres, measured using a digital caliper.

**Source:**

`QC-SOP-014 Rev 04`, page 2.

**Narration:**

> The assistant retrieves the tolerance from the active quality SOP revision. The archived Rev 03 document is not used as the source.

**Screen:**

- Ask the BH-220 question.
- Show the answer and source citation.

### 02:44 – 03:12 · Evidence-Based Abstention

**Question:**

> What is the annual electricity consumption of the factory?

**Expected behaviour:**

The knowledge base does not contain the requested information. The assistant responds with its fixed fallback message and does not display a source card.

**Narration:**

> Not every question has an answer in the available documents. When supporting evidence is missing, FactoryAssist AI abstains instead of generating an unsupported answer. This is especially important in manufacturing environments where incorrect information can affect safety and quality.

**Screen:**

- Ask the electricity consumption question.
- Show the amber fallback response.
- Confirm that no source card is displayed.

### 03:12 – 03:47 · Authentication and Document Management

**Narration:**

> The application also includes controlled document management. Employees can use the assistant, while authorised administrative roles manage the document lifecycle.

**Screen:**

- Show the sign-in interface.
- Sign in using the demonstration manager account.
- Open Document Management.
- Show the document register and management interface.

### 03:47 – 04:15 · Document Registration

**Narration:**

> An authorised manager can register a document by providing its identity, revision information, and PDF file. The application validates the document before it can enter the controlled document lifecycle.
>
> In this recording, the registration form is demonstrated, but the draft is not submitted. No new revision is added to the knowledge base.

**Screen:**

- Open the upload form.
- Show the prepared draft document details.
- Do not submit the form.
- Keep the empty document register visible.

### 04:15 – 04:37 · Closing

**Narration:**

> FactoryAssist AI combines document-grounded question answering, source-level citations, revision awareness, role-based access, and evidence-based abstention.
>
> The next development opportunities include OCR for scanned SOPs, improved table extraction, and a dedicated evaluation framework for retrieval quality.
>
> Thank you.

**Screen:**

- Show the final application view.
- End the recording.

---

## 2. Technical Stack Reference

The application uses the following technologies:

| Component | Technology |
|---|---|
| Backend framework | FastAPI |
| Application server | Uvicorn |
| Programming language | Python 3.12 target |
| AI generation | Google Gemini |
| Embeddings | `gemini-embedding-001` |
| Vector database | ChromaDB |
| PDF processing | PyMuPDF |
| Frontend | HTML, CSS and vanilla JavaScript |
| Configuration | Pydantic Settings |
| Relational database | SQLite |

### RAG Pipeline

The application follows these main stages:

1. **Document processing:** Extract text from manufacturing SOP PDFs.
2. **Chunking:** Split extracted content into page-scoped chunks.
3. **Embedding:** Generate vector embeddings using Google's embedding model.
4. **Indexing:** Store searchable vectors in ChromaDB.
5. **Retrieval:** Retrieve relevant evidence for a user question.
6. **Filtering:** Apply the configured similarity threshold and verify document revision eligibility.
7. **Generation:** Provide retrieved evidence to Gemini for a grounded response.
8. **Citation construction:** Build source citations from retrieved document metadata rather than relying on model-generated citations.

---

## 3. Additional Validation Questions

The following question is part of the broader application validation but is not included in the recorded video.

**LOTO question:**

> Who is allowed to remove a lockout lock from a machine?

**Expected answer:**

Each authorised person removes only their own lock, subject to the documented procedure and its stated exceptions.

**Source:**

`SAF-SOP-003 Rev 05`, page 1.

This question can be included in a future extended recording.

---

## 4. Document Management Demonstration — Future Recording

The existing video demonstrates authentication and the document registration interface. It does not demonstrate a completed upload, pending revision processing, activation, archival, or audit workflow.

For a future extended recording, the following sequence can be used after preparing a genuine demonstration PDF.

### Step 1: Sign In

Show the authorised manager signing in and opening Document Management.

### Step 2: Upload a Revision

Select a prepared PDF and provide its document identity and revision details.

Show the validation and processing workflow.

### Step 3: Pending State

Demonstrate that a newly uploaded revision remains pending review and is not yet available for question answering.

### Step 4: Activation

Activate the revision through the authorised management interface.

Show that the previously active revision is archived as part of the revision lifecycle.

### Step 5: Audit Trail

Show the relevant document-management audit records.

**Important:** Only record these actions after performing them successfully in the application. Do not use staged or fabricated activation results.

---

## 5. Recording Preparation Checklist

- [ ] Application starts successfully.
- [ ] AI service is available.
- [ ] Expected knowledge base documents are indexed.
- [ ] System Info shows model availability.
- [ ] AI Assistant responds correctly to the validation questions.
- [ ] Browser zoom is set to 100%.
- [ ] Recording resolution is set to 1920 × 1080 or 1280 × 720.
- [ ] Browser bookmarks and unnecessary tabs are hidden.
- [ ] Windows notifications are disabled.
- [ ] No API keys, passwords, session tokens, or private configuration values are visible.
- [ ] The demonstration account is ready.
- [ ] Narration is checked before recording.
- [ ] The conversation is cleared before each new take.

---

## 6. If a Live Question Misbehaves

Do not fabricate an answer or alter footage to imply that an unsuccessful response worked correctly.

If a question takes longer than expected:

1. Allow the request to finish.
2. Check whether the application returns an answer or an error.
3. If an error occurs, record it accurately.
4. Investigate the issue before attempting another take.
5. Use a previously captured screenshot only as a clearly identified visual fallback.

The screenshots in `assets/screenshots/` provide supporting visuals for the recorded workflow.

---

## 7. Final Deliverables

```text
assets/
├── demo/
│   ├── factoryassist-demo.mp4
│   ├── factoryassist-workflow.gif
│   └── README.md
└── screenshots/
    ├── 01-dashboard.png
    ├── 02-knowledge-base.png
    ├── 03-system-info.png
    ├── 04-assistant-coolant.png
    ├── 05-assistant-al104.png
    ├── 06-assistant-bh220.png
    ├── 07-abstention.png
    ├── 08-role-permissions.png
    ├── 09-document-upload.png
    └── 10-mobile-view.png
```

**Final status:** The 4:37 demonstration video, workflow GIF, and ten supporting screenshots have been created. The script documents the actual recorded sequence and separately identifies functionality intended for a future extended demonstration.