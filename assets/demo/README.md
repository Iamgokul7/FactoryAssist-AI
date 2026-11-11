# Demo Assets

Two files here, both produced from the running application --- no
slides, mock-ups, or edited screenshots.

  ------------------------------------------------------------------------------
  File                           What it is              Specs
  ------------------------------ ----------------------- -----------------------
  `factoryassist-demo.mp4`       Full walkthrough,       1920 × 1080, 12 fps,
                                 dashboard to governance H.264 + AAC 44.1 kHz,
                                                         4:37, 7.2 MB

  `factoryassist-workflow.gif`   Dashboard → question →  960 × 540, 7 fps, 17 s,
                                 answer → citation       164 KB
  ------------------------------------------------------------------------------

The ten matching stills are in [`../screenshots/`](../screenshots/).

## How It Was Recorded

-   Chrome (headless, 1920 × 1080, device scale factor 1) drove the real
    application at `http://127.0.0.1:8000` and answered questions
    through the live `/api/chat` endpoint. The answers and citations in
    the video are those returned by the server, including similarity
    scores and page numbers.
-   Screen frames were captured at roughly five per second and encoded
    to H.264 with FFmpeg. The recording was made in two takes
    (00:00--03:05 and 03:06--04:37), joined at a stable screen.
-   Narration is **synthetic speech** (Windows SAPI "Microsoft Zira")
    reading the accompanying script. It is machine-generated, not a
    human voice-over.
-   The sign-in during the governance scene uses a validation
    `SOP_MANAGER` account. The password field is masked in every frame.
    No credential, cookie, CSRF token, or API key appears in the video,
    GIF, or screenshots.

## Scenes and Narration

Times are approximate positions in the final file.

  -----------------------------------------------------------------------
  Time                    On screen               Narration
  ----------------------- ----------------------- -----------------------
  00:03                   Dashboard, badge, KPI   FactoryAssist AI is an
                          tiles, corpus table     assistant for
                                                  shop-floor supervisors.
                                                  The knowledge a
                                                  supervisor needs is
                                                  already written down,
                                                  in maintenance manuals,
                                                  safety procedures and
                                                  quality SOPs. The
                                                  problem is that it sits
                                                  in long PDFs that are
                                                  slow to search, while
                                                  older revisions are
                                                  often still in
                                                  circulation. This
                                                  application answers
                                                  from those controlled
                                                  documents and nothing
                                                  else. The dashboard
                                                  shows what it is
                                                  working with: three
                                                  active documents,
                                                  fifteen indexed chunks,
                                                  and one archived
                                                  revision kept for
                                                  reference.

  00:40                   Knowledge Base, active  The Knowledge Base view
                          corpus, archived Rev 03 lists the corpus with
                                                  each document's code,
                                                  revision, page count
                                                  and chunk count. Below
                                                  it sits QC-SOP-014
                                                  Revision 03. That
                                                  revision stays in the
                                                  plant record for
                                                  reference, but it is
                                                  not embedded into the
                                                  search index, so it can
                                                  never appear in an
                                                  answer. Only Revision
                                                  04 is active.

  01:05                   System Info, model      System Info exposes the
                          availability, retrieval settings an operator
                          settings                needs to check before
                                                  trusting an answer: the
                                                  Gemini model in use,
                                                  whether that model is
                                                  actually available for
                                                  the key on this
                                                  machine, the collection
                                                  being searched, the
                                                  similarity floor of
                                                  0.30, and the
                                                  five-chunk retrieval
                                                  window.

  01:27                   Coolant question,       Now a real question.
                          answer, source card     What is the recommended
                                                  coolant concentration
                                                  for the TX-200 CNC
                                                  turning centre? The
                                                  question is embedded,
                                                  the closest chunks are
                                                  retrieved, anything
                                                  below the similarity
                                                  floor is discarded, and
                                                  the model may only use
                                                  the retrieved evidence.
                                                  The answer is six to
                                                  eight percent, and the
                                                  source card names the
                                                  document code, the
                                                  revision, the page and
                                                  the file it came from.

  01:55                   Alarm AL-104 question   Next, an alarm code.
                          and answer              The machine is showing
                                                  alarm AL-104. What does
                                                  it mean, and what
                                                  should the operator do?
                                                  The manual says the way
                                                  lube oil level is low:
                                                  top up with ISO VG 68
                                                  to the MAX mark, then
                                                  press RESET. The
                                                  citation again points
                                                  to page two of the
                                                  maintenance manual,
                                                  Revision 02.

  02:21                   BH-220 tolerance        A tolerance question
                          answered from Rev 04    has to come from the
                                                  current revision. The
                                                  outer diameter
                                                  tolerance for the
                                                  BH-220 bearing housing
                                                  is plus or minus 0.050
                                                  millimetres on a 90
                                                  millimetre nominal, and
                                                  the citation names
                                                  QC-SOP-014 Revision 04,
                                                  the active revision,
                                                  never Revision 03.

  02:44                   Electricity question,   Not every question can
                          "No matching evidence"  be answered. What is
                                                  the annual electricity
                                                  consumption of the
                                                  factory? The documents
                                                  do not contain that
                                                  figure, so the system
                                                  returns its fallback
                                                  message and no sources
                                                  at all. It would rather
                                                  refuse than invent a
                                                  number, which matters
                                                  most on a safety or
                                                  quality question.

  03:12                   Sign-in, Document       Chat access in this
                          Management, register    demo does not require
                                                  sign-in. Changing the
                                                  controlled corpus does.
                                                  Signing in as a
                                                  supervisor-level
                                                  manager unlocks
                                                  Document Management,
                                                  where the corpus is
                                                  governed: a searchable
                                                  register of uploaded
                                                  revisions and their
                                                  status, a detail panel
                                                  with metadata and
                                                  revision history, and,
                                                  for administrators, an
                                                  audit trail of
                                                  governance actions. The
                                                  register is empty in
                                                  this deployment because
                                                  the baseline documents
                                                  were ingested by the
                                                  pipeline rather than
                                                  uploaded here.

  03:47                   Upload form filled with The upload form takes a
                          a draft revision        PDF together with its
                                                  document identity,
                                                  revision, department
                                                  and category. On
                                                  submission the file is
                                                  validated, extracted
                                                  and chunked, then held
                                                  as pending review, and
                                                  nothing pending is used
                                                  in answers until a
                                                  manager activates it. I
                                                  have filled the form
                                                  but will not submit it:
                                                  an upload would change
                                                  the corpus, and this is
                                                  the validated set the
                                                  earlier answers came
                                                  from.

  04:15                   Register, then closing  To sum up: answers
                          on the document panels  grounded in the plant's
                                                  own documents with
                                                  page-level citations,
                                                  revision isolation so
                                                  superseded documents
                                                  are never used, an
                                                  explicit refusal when
                                                  the evidence is
                                                  missing, and role-based
                                                  governance over the
                                                  corpus. The natural
                                                  next steps would be OCR
                                                  for scanned procedures
                                                  and a retrieval
                                                  evaluation harness.
                                                  Thank you.
  -----------------------------------------------------------------------

## What the Demo Deliberately Does Not Show

-   **No document was submitted.** The upload form is filled with a 0.18
    MB draft (`DEMO-SOP-101`, revision 01), but the button is never
    pressed. A real upload would change the validated corpus the answers
    come from. The register is therefore empty: no revision has been
    uploaded through this screen in this deployment.
-   **No admin-only screens.** The audit trail and account management
    require an `ADMIN` session. Those capabilities are covered in
    `DOCUMENT_UPLOAD_TEST_REPORT.md`, not in this recording.
-   **No performance claims.** The recording does not measure latency or
    establish overall retrieval accuracy. It demonstrates three answered
    questions and one abstention. Broader validation results are
    documented separately.

## Re-recording

Start the server, then follow [`../DEMO_SCRIPT.md`](../DEMO_SCRIPT.md).
If you want a human voice-over, record it separately and replace the
audio track:

``` bash
ffmpeg -i factoryassist-demo.mp4 -i your-voice.wav -map 0:v -map 1:a -c:v copy -shortest factoryassist-demo-voiced.mp4
```
