# Demo recording checklist

A short, practical checklist for recording the 2–3 minute demo described in
`DEMO_SCRIPT.md`. Tick each line before you press record.

**Status of demo assets:** eight screenshots exist in `screenshots/` and were
captured from the running application. No video file has been recorded — the
video is still to be made by you.

---

## 1. Pre-flight (5 minutes)

- [ ] Virtual environment active: `.venv\Scripts\activate`
- [ ] Server running: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
- [ ] `http://127.0.0.1:8000/` opens, and the top-right badges read
      **AI service ready** and **15 chunks indexed**
- [ ] System Info shows **Model availability: Available**
- [ ] AI Assistant answers one throwaway question ("What does alarm AL-104
      mean?") so the model is warmed up
- [ ] Click **Clear conversation** so the recording starts on the empty state
- [ ] API key is configured and working (the badge proves it; do not open `.env`)

## 2. Screen hygiene

- [ ] `.env` closed in every editor and terminal that can appear on screen
- [ ] Terminal cleared (no `env`, `set`, `pip config` or key output in scrollback)
- [ ] Browser bookmarks bar hidden; zoom at 100 %
- [ ] Window at least 1280 × 800 (screenshots were captured at 1280 × 900)
- [ ] Notifications off (Windows Focus Assist or equivalent)
- [ ] Mail, chat, other browser tabs and file explorer closed
- [ ] No customer/company documents open other than the SOP PDFs you intend to show

## 3. Recording order (matches `DEMO_SCRIPT.md`)

| Time | Shot | On screen |
| --- | --- | --- |
| 0:00 | Problem | Dashboard — badges, KPI tiles |
| 0:18 | Stack | Scroll to active-document table |
| 0:40 | Ingestion | Knowledge Base — active table, then archived Rev 03 row |
| 1:00 | Pipeline | System Info — "How it answers" and runtime configuration |
| 1:20 | Q&A ×4 | AI Assistant — coolant, AL-104, LOTO, BH-220 (one at a time) |
| 2:05 | Abstention | AI Assistant — electricity question, amber "No matching evidence" |
| 2:25 | Close | Dashboard again, then stop |

- [ ] Each answer stays on screen ~3 seconds so the source card is readable
- [ ] Total runtime under 3 minutes (drop AL-104 or LOTO first if long)
- [ ] One continuous take preferred; if you restart, clear the conversation first

## 4. Audio

- [ ] Microphone tested; no fan or keyboard noise
- [ ] Narration read from `DEMO_SCRIPT.md`, or recorded afterwards over the
      silent capture
- [ ] No reading of the API key, file paths containing your username, or
      internal URLs on screen

## 5. Expected output to verify while recording

| Question | Expected answer | Expected source |
| --- | --- | --- |
| Coolant concentration | 6 – 8 % | MNT-MAN-CNC-02 Rev 02, page 1 |
| AL-104 | Way lube oil low → ISO VG 68 to MAX, RESET | MNT-MAN-CNC-02 Rev 02, page 2 |
| LOTO | Each person removes only their own lock | SAF-SOP-003 Rev 05, page 1 |
| BH-220 OD | ±0.050 mm at 90.000 mm, digital caliper | QC-SOP-014 **Rev 04**, page 2 |
| Electricity | Fallback sentence, **no** source card | — |

If an answer differs, do not edit the footage to hide it: say what happened and
continue. A refusal or an error bubble is part of the honest behaviour the
project demonstrates.

## 6. After recording

- [ ] Play back the file start to finish and confirm no key or personal data is
      visible in any frame
- [ ] Name the file clearly (for example `factoryassist-demo.mp4`)
- [ ] Confirm the file exists on disk before reporting a video as delivered
