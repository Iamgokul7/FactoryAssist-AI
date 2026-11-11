# Document management guide

How an authorised manager uploads, reviews, activates and archives controlled
manufacturing PDFs in FactoryAssist AI.

Audience: plant administrators and SOP managers. For account setup, see
`ADMIN_SETUP_GUIDE.md`.

---

## 1. What the feature does

- Controlled PDFs are uploaded through the application, not copied into folders
  by hand.
- Every upload is validated, processed, indexed and held for **review**.
- Only an **active** revision can be retrieved by the assistant.
- Activating a revision automatically archives the revision it replaces, so a
  document code always has exactly one current revision.
- Every management action is recorded in the audit trail with the user and time.

## 2. Before you start

- You need an account with the `SOP_MANAGER` or `ADMIN` role.
- The PDF must contain a real text layer. Scanned, image-only PDFs are rejected
  because OCR is not part of this build.
- The document must be identified by a code (for example `QC-SOP-014`), a
  revision number (for example `05`), a department, a category and an effective
  date.
- The file must be 25 MB or smaller (configurable with `MAX_UPLOAD_SIZE_MB`).

## 3. Signing in

1. Open the application and click **Sign in** in the top bar.
2. Enter your username and password.
3. The **Document Management** item appears in the sidebar only if your role
   allows it. Employees never see it, and the server refuses their requests even
   if they call the API directly.

Sessions expire after `SESSION_TTL_HOURS` (8 by default). Signing out ends the
session immediately; changing a password or disabling an account ends all of that
account's sessions.

## 4. The dashboard counters

| Counter | Meaning |
| --- | --- |
| Total documents | Every uploaded revision on record |
| Active | Approved revisions the assistant may use |
| Pending review | Processed uploads waiting for a decision |
| Archived | Superseded or retired revisions |
| Failed uploads | Processing did not complete; see the row and retry |

## 5. Uploading a revision

1. Open **Document Management** and click **Show form**.
2. Drag the PDF onto the drop zone, or click it and choose the file. The drop
   zone shows the filename and size once selected.
3. Fill in:
   - **Document ID** — same code for every revision (`QC-SOP-014`).
   - **Revision** — digits only, next revision number (`05`).
   - **Document title** — as printed on the document.
   - **Department** — for example Quality, Maintenance, Safety.
   - **Category** — Manufacturing SOP, Quality Manual, Safety Manual,
     Maintenance Manual or Work Instruction.
   - **Effective date** — the date the revision takes effect.
   - **Description** — optional short note for reviewers.
4. Click **Upload and process**.

The progress bar tracks the upload; processing then runs on the server
(extraction, chunking, embedding). The result appears immediately:

- **Pending review** — processed successfully; not searchable yet.
- **Failed** — the row shows a short reason and a **Retry** button.

### What the server checks

| Check | Why |
| --- | --- |
| PDF signature (`%PDF-`) | The extension and MIME type are client-supplied |
| File size | Protects memory and storage |
| Readable, unencrypted PDF | A broken or locked file would poison the index |
| At least one page with text | Empty/scanned PDFs would produce meaningless chunks |
| Code and revision format | Keeps chunk identity and citations consistent |
| Duplicate code + revision | Prevents two records claiming the same identity |
| Identical file content | Catches accidental re-uploads under a new revision |
| Curated-corpus duplicate | The original assignment documents already hold that revision |

Rejected files are not stored against a document record; the attempt is written
to the audit trail.

## 6. Reviewing a revision

Open a row with **View** to see:

- Status, department, category, effective date, pages and chunks.
- Who uploaded it, when it was processed, and who approved or archived it.
- The stored PDF (the **PDF** action downloads it).
- Revision history for the same document code.
- Warnings, including the automatic manufacturing-relevance flag.

A `check` marker next to a title means the keyword classifier did not find
manufacturing language in the document. It is a prompt to read the document, not
a decision: the file may still be a legitimate SOP with unusual wording, or it
may be the wrong file entirely.

## 7. Activating a revision

1. In the register, find the pending row.
2. Click **Activate** and confirm.

What happens, in order:

1. The server verifies the revision is pending and its indexed chunks match its
   record.
2. The revision's chunks are marked active.
3. The document records are committed in one write: the new revision becomes
   active with your name and the approval time, and the revision it replaces
   becomes archived.
4. The replaced revision's chunks are removed from the index.

If any step before the commit fails, nothing changes and the previous revision
stays active. You cannot end up with two active revisions or none.

The assistant may cite the new revision immediately after activation. The old
revision can never be cited again.

## 8. Rejecting a revision

Use **Reject** when the upload is the wrong file, the wrong revision or not
approved for use. An optional reason is stored in the audit trail.

A rejected revision cannot be activated later. Upload a corrected revision
instead (with the same revision number only after the rejected record is no
longer needed — the system prevents duplicate code + revision pairs).

## 9. Archiving a revision

**Archive** retires the active revision without a replacement. To protect
employees from losing a procedure accidentally, the application refuses to
archive the only active revision unless an administrator forces it:

```text
Only an administrator can archive the last active revision.
```

The normal path is: upload the replacement, activate it, and let activation
archive the old revision for you.

## 10. Retrying a failed upload

A failed row keeps the stored PDF. Click **Retry** to reprocess it.

- If the chunks were already embedded, the retry reuses those embeddings instead
  of paying for them again.
- If the failure was a Gemini or vector-store outage, retry once the service is
  available.
- If the failure was a missing source file, upload the PDF again.

## 11. Finding documents

- **Search** matches document code, title, revision, department and description.
- **Status chips** filter to active, pending review, archived, failed or rejected.
- Counters always reflect the whole register, not the current filter.

## 12. Roles in this screen

| Action | ADMIN | SOP_MANAGER | EMPLOYEE |
| --- | --- | --- | --- |
| View the register | Yes | Yes | No |
| Upload a revision | Yes | Yes | No |
| Activate / reject / archive | Yes | Yes | No |
| Retry a failed upload | Yes | Yes | No |
| Edit metadata | Yes | No | No |
| Manage accounts, read audit trail | Yes | No | No |

## 13. Common messages

| Message | Meaning | What to do |
| --- | --- | --- |
| `Only PDF files can be uploaded.` | Extension is not `.pdf` | Export/save as PDF first |
| `The file does not look like a valid PDF` | Signature missing | The file is not really a PDF |
| `The PDF contains no extractable text` | Scanned or image-only | Add a text layer (OCR) before upload |
| `The PDF contains no pages` | Empty document | Check the export |
| `Revision 05 of QC-SOP-014 already exists` | Duplicate identity | Use the next revision number |
| `This exact PDF has already been uploaded` | Same bytes already stored | Check the existing record |
| `Only documents pending review can be activated` | Wrong status | Re-read the row status |
| `This is the only active revision` | Archiving the last one | Activate a replacement, or ask an administrator |
| `The request could not be verified` | CSRF token missing/expired | Refresh the page and sign in again |
| `Too many failed sign-in attempts` | Rate limit: five failures on one account, or twenty from one address, in the window | Wait for the window, then retry, or sign in as another account |

## 14. Storage and backups

| What | Where | Committed? |
| --- | --- | --- |
| Uploaded PDFs | `Documents/uploads/` | No |
| Document records | `data/managed/documents.json` | No |
| Accounts, sessions, audit | `data/managed/app.db` | No |
| Vector index | `vector_store/chroma_db/` | No |

Back up `data/managed/` and `Documents/uploads/` together; the records reference
the stored files. The vector index can be rebuilt by reprocessing uploads, but
the records and audit log cannot.

## 15. Limits worth knowing

- Processing happens inside the upload request, so a very large manual will take
  a while and the browser waits.
- The relevance classifier is a keyword heuristic.
- The application assumes a single server process.
- The chat itself does not require sign-in; only document management does.
