# FactoryAssist AI – Document Management Guide

A practical guide for authorised managers to upload, review, activate, reject, and archive controlled manufacturing PDFs in FactoryAssist AI.

**Audience:** Plant Administrators and SOP Managers
**Account setup:** See `ADMIN_SETUP_GUIDE.md`.

---

## 1. What This Feature Does

FactoryAssist AI provides a controlled workflow for managing manufacturing documents:

- Controlled PDFs are uploaded through the application rather than copied into storage folders manually.
- Every upload is validated, processed, indexed, and placed in **Pending Review**.
- Only an **Active** revision can be retrieved and cited by the assistant.
- Activating a new revision automatically archives the revision it replaces.
- Each management action is recorded in the audit trail with the responsible user and timestamp.

This workflow helps ensure that employees receive answers based on approved, current documentation.

## 2. Before You Start

Make sure you have the following:

- An account with the `SOP_MANAGER` or `ADMIN` role.
- A PDF containing an extractable text layer. Scanned or image-only PDFs are rejected because OCR is not supported in this build.
- A document code, such as `QC-SOP-014`.
- A revision number, such as `05`.
- A department and category.
- An effective date.
- A PDF file no larger than **25 MB** by default. The limit is configurable through `MAX_UPLOAD_SIZE_MB`.

## 3. Signing In

1. Open FactoryAssist AI.
2. Click **Sign in** in the top navigation bar.
3. Enter your username and password.
4. Once authenticated, open **Document Management** from the sidebar.

The Document Management navigation item is displayed only to users with an authorised role. Employees cannot access the management interface or its protected API endpoints, even if they attempt to call those endpoints directly.

**Session behaviour:**

- Sessions expire after the configured `SESSION_TTL_HOURS` period (8 hours by default).
- Signing out ends the current session immediately.
- Changing a password or disabling an account invalidates that account's existing sessions.

## 4. Understanding the Dashboard Counters

The dashboard displays the current state of the document register.

| Counter | Meaning |
|---|---|
| Total Documents | All uploaded document revisions recorded in the system |
| Active | Approved revisions currently available to the assistant |
| Pending Review | Successfully processed uploads awaiting approval |
| Archived | Superseded or retired revisions |
| Failed Uploads | Uploads whose processing did not complete successfully |

The counters represent the entire document register, not just the rows currently visible through a search or status filter.

## 5. Uploading a Document Revision

Follow these steps to upload a new revision.

1. Open **Document Management**.
2. Click **Show form**.
3. Drag a PDF into the upload area, or click the area to select a file.
4. Confirm that the selected filename and file size are displayed.
5. Complete the document metadata fields.

| Field | Description | Example |
|---|---|---|
| Document ID | Stable identifier shared by all revisions of the document | `QC-SOP-014` |
| Revision | Numeric revision identifier | `05` |
| Document Title | Title printed on the document | Quality Control Procedure |
| Department | Department responsible for the document | Quality |
| Category | Document classification | Manufacturing SOP |
| Effective Date | Date the revision takes effect | 2026-11-01 |
| Description | Optional note for reviewers | Updated inspection procedure |

Supported categories:

- Manufacturing SOP
- Quality Manual
- Safety Manual
- Maintenance Manual
- Work Instruction

6. Click **Upload and process**.

The progress indicator tracks the upload. The server then processes the document through text extraction, chunking, and embedding.

After processing, the document appears in the register with one of the following statuses:

- **Pending Review:** Processing completed successfully. The document is indexed but is not available to the assistant until activated.
- **Failed:** Processing did not complete. The register displays an error summary and a **Retry** action where applicable.

### 5.1 Server-Side Validation

The application performs several checks before accepting a document.

| Validation | Purpose |
|---|---|
| PDF signature (`%PDF-`) | Checks the file content rather than trusting the supplied extension or MIME type |
| File size | Enforces the configured upload limit |
| PDF readability | Rejects unreadable or encrypted documents |
| Extractable text | Rejects empty or image-only documents |
| Document code and revision format | Maintains consistent document identity |
| Duplicate code and revision | Prevents duplicate revision records |
| Identical file content | Detects accidental re-uploads of the same PDF |
| Curated-corpus duplicate | Prevents re-uploading a revision already present in the original assignment corpus |

Rejected files are not stored as document records. The rejected attempt is recorded in the audit trail.

## 6. Reviewing a Revision

Locate the document in the register and click **View**.

The document details provide information such as:

- Document status, department, category, and effective date.
- Page and chunk counts.
- Uploader and processing information.
- Approval or archive details, where applicable.
- Access to the stored PDF through the **PDF** action.
- Revision history for the same document code.
- Document warnings, including the manufacturing-relevance indicator.

### Understanding the Manufacturing-Relevance Warning

A check marker displayed next to a document title indicates that the keyword-based classifier did not identify expected manufacturing terminology.

This is a review warning, not an automatic rejection.

The document may still be a valid manufacturing procedure with unusual wording. Alternatively, it may be an incorrect or unrelated file.

**Always review the document itself before activating it.**

## 7. Activating a Revision

Activation makes an approved revision available to the assistant.

1. Find the document with **Pending Review** status.
2. Click **Activate**.
3. Review the confirmation prompt.
4. Confirm the activation.

### What Happens During Activation?

The application performs the following operations:

1. Verifies that the revision is pending review.
2. Checks that the indexed chunks match the document record.
3. Marks the new revision's chunks as active.
4. Updates the document records so the new revision becomes active, including the approver and approval timestamp.
5. Archives the revision it replaces.
6. Removes the replaced revision's chunks from the active retrieval index.

The document-management workflow is designed to prevent two revisions of the same document code from remaining active simultaneously.

If an activation operation fails, the application is designed to preserve the previous active revision rather than leave the document without an approved version.

Once activation succeeds, the assistant can retrieve and cite the new revision. The superseded revision is no longer available for retrieval.

## 8. Rejecting a Revision

Use **Reject** when a document:

- Is the wrong file.
- Contains an incorrect revision.
- Is unrelated to the intended document.
- Has not been approved for operational use.

To reject a revision:

1. Locate the pending document in the register.
2. Click **Reject**.
3. Enter an optional rejection reason.
4. Confirm the action.

The rejection reason, when supplied, is recorded in the audit trail.

A rejected revision cannot subsequently be activated. Upload a corrected document instead.

**Important:** The system prevents duplicate document-code and revision combinations. Check the existing register before attempting to upload a corrected file using the same revision number.

## 9. Archiving a Revision

Archiving retires an active revision without replacing it with a newer revision.

To protect employees from accidentally losing access to an approved procedure, the application restricts archiving the last active revision.

The application displays the following message when an ordinary manager attempts this operation:

```text
Only an administrator can archive the last active revision.
```

An administrator can perform this operation when necessary.

**Recommended approach:** Upload the replacement revision, review it, and activate it. The activation workflow automatically archives the previous revision.

## 10. Retrying a Failed Upload

A failed upload can be reprocessed through the **Retry** action in the document register.

1. Find the failed document.
2. Review the displayed error.
3. Click **Retry**.
4. Wait for processing to complete.

Depending on the failure:

- If the required chunks have already been embedded, the retry can reuse those embeddings instead of generating them again.
- If the failure was caused by a temporary Gemini or vector-store outage, retry after the service becomes available.
- If the source PDF is missing or damaged, upload a valid copy again.

If repeated retries fail, review the application logs and the document's stored-file status before attempting another upload.

## 11. Finding Documents

The document register provides search and status filtering.

**Search**

Search matches document information such as:

- Document code
- Document title
- Revision
- Department
- Description

**Status filters**

Use the status chips to narrow the register to:

- Active
- Pending Review
- Archived
- Failed
- Rejected

Dashboard counters continue to represent the full register, regardless of the selected filter.

## 12. Roles and Permissions

The following table describes the permissions available in the document-management interface.

| Action | ADMIN | SOP_MANAGER | EMPLOYEE |
|---|---:|---:|---:|
| View document register | Yes | Yes | No |
| Upload a revision | Yes | Yes | No |
| Activate a revision | Yes | Yes | No |
| Reject a revision | Yes | Yes | No |
| Archive a revision | Yes | Yes | No |
| Retry a failed upload | Yes | Yes | No |
| Edit document metadata | Yes | No | No |
| Manage user accounts | Yes | No | No |
| Read the audit trail | Yes | No | No |

Permissions are enforced on the server, not only through the visibility of interface controls.

## 13. Common Messages and Troubleshooting

| Message | Meaning | Recommended Action |
|---|---|---|
| `Only PDF files can be uploaded.` | The selected file does not have a `.pdf` extension. | Export or save the document as a PDF. |
| `The file does not look like a valid PDF` | The file signature is missing or invalid. | Check that the selected file is a genuine PDF. |
| `The PDF contains no extractable text` | The PDF is scanned or image-only. | Add a searchable text layer before uploading. |
| `The PDF contains no pages` | The document is empty or invalid. | Check the original file and export it again. |
| `Revision 05 of QC-SOP-014 already exists` | The document code and revision combination is already registered. | Check the existing document record. |
| `This exact PDF has already been uploaded` | The same file content is already stored. | Locate and review the existing record. |
| `Only documents pending review can be activated` | The document is not in the required status. | Check the current document status. |
| `This is the only active revision` | The operation would archive the last active revision. | Activate a replacement or ask an administrator to perform the operation. |
| `The request could not be verified` | The CSRF token is missing, invalid, or expired. | Refresh the page and sign in again. |
| `Too many failed sign-in attempts` | The configured login rate limit has been reached. | Wait for the rate-limit window to expire before retrying. |

The login rate limit allows up to five failed attempts for one account or twenty attempts from one address within the configured window.

## 14. Storage and Backups

FactoryAssist AI stores document-management data locally.

| Data | Storage Location | Committed to Git? |
|---|---|---|
| Uploaded PDFs | `Documents/uploads/` | No |
| Document records | `data/managed/documents.json` | No |
| Accounts, sessions, and audit records | `data/managed/app.db` | No |
| Vector index | `vector_store/chroma_db/` | No |

### Backup Recommendations

Back up the following directories together:

- `data/managed/`
- `Documents/uploads/`

The document records reference the stored PDF files, so backing them up separately can result in inconsistent records.

The vector index can be rebuilt by reprocessing the stored documents. However, document records and audit history cannot simply be reconstructed from the vector index.

Keep backups in a secure location and restrict access to authorised administrators.

## 15. Current Limitations

The following limitations apply to this build:

- **Synchronous processing:** Document processing happens within the upload request. Large manuals can take longer to process, and the browser must wait for the request to finish.
- **No OCR:** Scanned or image-only PDFs are not supported. Documents must contain extractable text.
- **Heuristic relevance detection:** The manufacturing-relevance indicator uses keyword-based classification. It is a review aid, not a semantic approval system.
- **Single-process assumption:** The application is designed around a single server process. Multi-worker deployment requires additional coordination for document activation and index updates.
- **Local storage:** SQLite, JSON metadata, uploaded PDFs, and the local vector index are intended for a controlled, single-plant deployment rather than a large distributed enterprise environment.
- **Authentication scope:** The chat interface does not require sign-in in this build. Document management and its protected operations require an authorised account.

---

**Operational reminder:** Always review a pending revision before activation. Only activate documents that have been verified and approved for use in the plant.