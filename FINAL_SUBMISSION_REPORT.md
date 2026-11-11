Final Submission Report — FactoryAssist AI
Report date: 11 November 2026
Repository: Iamgokul7/FactoryAssist-AI
Branch: master
Project status: Engineering implementation and documented validation completed; public repository and demo assets available.
Scope and evidence note: This report consolidates the Stage 6 engineering audit with the subsequent Stage 7 document-management implementation and validation. Historical Stage 6 results are identified as historical where relevant. The latest reported automated test result is 92 passing tests. The demo video and screenshots are recorded deliverables, but the video does not demonstrate document submission, activation, or archival. Repository status below reflects the last status supplied for this review: the initial repository and banner commits are pushed; the later documentation and demo-asset changes are still uncommitted. Recheck git status before treating that repository detail as current.

1. Executive Summary
FactoryAssist AI is a document-grounded manufacturing SOP copilot. It helps manufacturing personnel ask questions about controlled SOPs and maintenance manuals, retrieves relevant document passages, generates evidence-based answers, and provides source citations. When the indexed evidence is insufficient, it abstains rather than presenting an unsupported answer.

The application also includes document-management capabilities for controlled document uploads, revision review, activation and archival workflows, role-based access control, and audit records.

The project is implemented as a Python FastAPI application with a browser-based interface. Its retrieval pipeline uses Google Gemini embeddings and generation with ChromaDB as the persistent vector store. Document metadata and management records are maintained locally using SQLite and JSON.

Current validation summary
- Automated tests: 92 passed in the latest reported run.
- Code and dependency checks: compileall, pip check, and JavaScript syntax validation passed in the reported validation run.
- Functional validation: Chat, citations, abstention, document upload and governance, authentication, role restrictions, and audit workflows were exercised.
- Demo assets: A 4:37 MP4 recording, an approximately 17-second workflow GIF, and ten screenshots are available in the repository assets directory.
- Deployment: This report does not claim a production or cloud deployment.
2. Project Overview
2.1 Problem
Manufacturing teams rely on controlled procedures, maintenance manuals, and revision-sensitive technical documents. Finding the correct instruction can be difficult when information is spread across PDFs or when superseded revisions remain accessible.
2.2 Solution
FactoryAssist AI provides a conversational interface over an indexed document collection. It retrieves relevant passages from active documents, uses those passages as evidence for generation, and returns citations that identify the source document, revision, and page where available.

The system is designed to:
- Answer questions using indexed manufacturing documentation.
- Cite the evidence used to formulate an answer.
- Abstain when the available evidence does not support an answer.
- Exclude archived or superseded revisions from active retrieval.
- Provide controlled document-management workflows with role-based permissions.
2.3 Main interface areas
- Dashboard
- AI Assistant
- Knowledge Base
- System Info
- Document-management and administrative workflows
3. Technology Stack
Layer	Technology
Runtime	Python (project target: Python 3.12)
API framework	FastAPI
ASGI server	Uvicorn
LLM integration	Google Gen AI SDK
Generation model	gemini-3.5-flash-lite
Embedding model	gemini-embedding-001
Vector database	ChromaDB
PDF extraction	PyMuPDF
Configuration	Pydantic Settings
Management persistence	SQLite and JSON metadata
Frontend	HTML, CSS, vanilla JavaScript
Automated tests	Python unittest


The application does not use React, Next.js, Flask, LangChain, or LlamaIndex.
4. Core Application and RAG Implementation
4.1 Document ingestion
The ingestion pipeline extracts text from PDF documents, retains page-level context, creates chunks with document metadata, and indexes eligible content for retrieval.

The Stage 6 audit recorded the following baseline corpus:
Item	Recorded value
Documents processed	5
Active documents	3
Archived documents	1
Sample-questions document	1
Pages extracted	8
Active chunks	15
Archived chunks	3
Extraction warnings / errors	0 / 0


These figures describe the corpus at the time of that audit; they should not be interpreted as a live count if the local document collection has since changed.
4.2 Retrieval and answer generation
The RAG workflow:
1. Receives a user question.
2. Embeds the query using the configured embedding model.
3. Retrieves relevant chunks from the persistent ChromaDB collection.
4. Restricts retrieval to active document content.
5. Supplies retrieved evidence to the generation model.
6. Validates the structured model response.
7. Builds citations from retrieved source metadata.
8. Returns an answer or an insufficient-evidence response.
The Stage 6 audit recorded top-5 retrieval, a cosine-similarity floor of 0.30, and a second active-revision manifest check. The archived QC-SOP-014 Rev 03 did not appear in retrieval results, citations, or answers during that audit.
4.3 Grounding and abstention
The application is designed to avoid presenting unsupported answers as facts. When the available evidence is insufficient, the system returns its configured fallback response without source citations.

The historical validation included an annual factory electricity-consumption question for which the knowledge base had no supporting evidence. The system returned insufficient_evidence with no cited source.
5. Document Management
Stage 7 added document-management workflows alongside the original RAG assistant.

Reported capabilities include:
- Document registration and management views.
- PDF upload and validation.
- Safe handling of uploaded filenames.
- Document metadata and revision tracking.
- Review and activation workflow.
- Archiving and superseded-revision handling.
- Role-based access control.
- Audit-event recording.
- Protection of active retrieval from pending or archived content.
The management implementation uses SQLite for structured management records and JSON metadata for document information. The document-management report and test report contain the detailed implementation and validation records.

Demo coverage limitation: The published recording shows the document-management area and a populated upload form, but the form is not submitted during the recording. The video therefore does not demonstrate a completed upload, activation, or archive action. Those workflows were separately exercised during functional and browser validation.
6. Authentication and Security
Stage 7 introduced authentication and access controls for document-management operations.

The implementation report records:
- Role categories for ADMIN, SOP_MANAGER, and EMPLOYEE.
- Password hashing using PBKDF2-HMAC-SHA256 with 600,000 iterations.
- Opaque session tokens, with SHA-256 fingerprints stored server-side.
- HttpOnly and SameSite cookie settings.
- CSRF and Origin/Host validation.
- Login rate limiting.
- Security response headers.
- Role checks for protected management operations.
- Redacted and bounded error diagnostics.
The public chat interface is intentionally accessible without a management-role session. Protected document-management operations require the relevant authenticated role.
6.1 Repository hygiene
The reported repository audit found that .env, local databases, PDFs, logs, virtual environments, and ChromaDB data were excluded from version control. The configured API key was not found in the scanned working tree or Git history, and .env was not committed.

These are results of the documented repository scan, not a guarantee that no secret could exist in any future change. Continue to review staged files and diffs before every commit.
7. Automated and Functional Validation
7.1 Latest automated test result
The latest reported test run completed with:
Check	Reported result
Automated test suite	92 passed
Python compilation (compileall)	Passed
Dependency consistency (pip check)	Passed
JavaScript syntax (node --check)	Passed


The Stage 7 reports attribute the 92 tests to 73 document-management/access-control tests and 19 earlier application tests.
7.2 Live API validation
The document-management validation report records a live HTTP validation run of 86 passing checks, one failing check, and two informational results. The failure involved a sparse synthetic PDF whose retrieved evidence fell below the configured retrieval threshold. The case was repeated using a denser test fixture and passed.

This historical result is reported transparently; it is not represented as an entirely clean first run.
7.3 Functional coverage
The reported validation covered:
- Chat responses and source citations.
- Insufficient-evidence handling.
- Active versus archived revision retrieval.
- PDF upload validation.
- Pending, review, activation, rejection, and archive workflows.
- Authentication and role-based access restrictions.
- Audit records.
- Browser-level management workflows.
- Regression checks for the original chatbot.
7.4 Known validation gaps
The reports identify the following areas as not fully validated:
- OCR for scanned PDFs.
- Multi-worker deployment behaviour for the in-process activation lock.
- Load and large-file performance testing.
- Full long-duration session-expiry behaviour through an eight-hour browser session.
- Production-scale or multi-plant operation.
8. Example Knowledge-Base Validation
The documented QA examples include:
Question / topic	Expected grounded result
Coolant concentration	6–8%
AL-104 way-lubrication action	If low, use ISO VG 68 way lube to MAX, then RESET
LOTO lock removal	Each authorized person removes their own lock
BH-220 outside-diameter tolerance	±0.050 mm at 90.000 mm, measured using a digital caliper
Spindle runout	Monthly check by a maintenance technician
Annual factory electricity consumption	Abstain when no supporting evidence is available


The Stage 6 live test recorded HTTP 200 responses for these six questions, with the electricity question returning insufficient_evidence and no source citation.
9. Demo and Visual Assets
The following assets were reported as created:
Asset	Details
Demo video	assets/demo/factoryassist-demo.mp4
Video duration	Approximately 4 minutes 37 seconds
Video resolution	1920 × 1080
Video format	H.264 video with AAC audio
Video frame rate	12 fps
Workflow GIF	assets/demo/factoryassist-workflow.gif
GIF duration	Approximately 17 seconds
GIF dimensions	960 × 540
Screenshots	Ten files under assets/screenshots/


The demo narration uses a synthetic Windows SAPI voice. The recording shows the dashboard, knowledge base, system information, three grounded questions, an abstention example, sign-in and role-gating views, and the unsubmitted document-upload form.

The screenshots include desktop and mobile-sized captures. Their actual dimensions vary; they should not all be described as 1920 × 1080.
10. Fresh-Environment Installation Check
The fresh-install report records a successful installation in a new virtual environment using Python 3.14.6, with 102 packages installed. Compilation, dependency checks, imports, application endpoint checks, and the then-current 19-test suite passed.

The project target remains Python 3.12. The Python 3.14.6 installation check is additional compatibility evidence; it does not replace validation on the documented target runtime.

The fresh-install test run occurred before the Stage 7 test-suite expansion. It therefore reports 19 tests, not the later 92-test result.
11. Repository and Delivery Status
The public repository is:

https://github.com/Iamgokul7/FactoryAssist-AI

The initial repository commit and the banner commit were pushed. The later documentation updates and demo assets were reported as modified or untracked and had not yet been committed or pushed at the last recorded status check.

Before final delivery:
1. Run git status and inspect the exact changed-file list.
2. Review git diff --check and the full diff.
3. Confirm no secrets, personal information, local databases, PDFs, logs, or private test artifacts are staged.
4. Decide whether internal audit reports belong in the public repository.
5. Stage only the files intended for publication.
6. Commit and push only after reviewing the staged diff.
No production or cloud deployment is claimed in this report.
12. Known Limitations and Future Improvements
- Synchronous processing: Document processing is synchronous and may need background jobs for larger workloads.
- Single-process coordination: The activation lock is in-process; multi-worker deployment requires a shared coordination mechanism.
- No OCR: Scanned PDFs without extractable text are not covered by the current PDF text-extraction workflow.
- Local persistence: SQLite and JSON are suitable for the current local/single-plant scope, but a larger deployment may require a production database and storage architecture.
- Performance: Load testing and large-document performance testing remain future work.
- Session-duration testing: Full eight-hour browser-session expiry has not been validated end-to-end.
- Cloud deployment: A production deployment, monitoring, backup automation, and CI/CD pipeline are not claimed as completed.
13. Final Assessment
FactoryAssist AI has progressed beyond the original Stage 6 RAG prototype. The current implementation includes a grounded manufacturing SOP assistant, revision-aware retrieval, document-management workflows, role-based access controls, and audit functionality.

The latest reported automated suite has 92 passing tests, and the project has a public GitHub repository plus recorded demo and screenshot assets. The documented validation also identifies remaining limitations and test gaps rather than presenting the project as production-ready.

Submission recommendation: The engineering work and demo materials are available for review. Before calling the repository fully submission-ready, reconcile and publish the latest documentation/assets, verify the final Git status and staged diff, and confirm that the public repository contains only the intended submission materials.