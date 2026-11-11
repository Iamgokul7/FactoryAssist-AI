# Demo Recording Checklist

This document records the demo setup, recording details, verification points, and optional re-recording instructions for FactoryAssist AI.

## Demo Asset Status

**Status: RECORDED**

The FactoryAssist AI walkthrough has been recorded and saved in the repository.

| Asset | Location | Specifications |
|---|---|---|
| Demo video | `assets/demo/factoryassist-demo.mp4` | 4:37, 1920 × 1080, H.264 + AAC, 12 FPS, approximately 7.2 MB |
| Workflow GIF | `assets/demo/factoryassist-workflow.gif` | Approximately 17 seconds, 960 × 540, 7 FPS, 120 frames |
| Demo screenshots | `assets/screenshots/` | 10 screenshots |
| Original screenshots | `screenshots/` | 8 earlier screenshots |

### Screenshot Resolution Details

The ten new screenshots were captured at different viewport sizes:

- Screenshots 01–06 and 08–09: 1920 × 1080.
- Screenshot 07: 1280 × 900.
- Screenshot 10: 390 × 844 mobile viewport, saved as a 780 × 1688 image.

The eight original screenshots in `screenshots/` remain unchanged and were captured at 1280 × 900.

The existing recording uses synthetic Windows SAPI narration (Microsoft Zira). A human voice-over can optionally replace it in a future recording.

---

## 1. Pre-flight Checklist

Use this section when reproducing or re-recording the demonstration.

- [ ] Activate the project virtual environment.
- [ ] Start the FastAPI application using the documented startup command.
- [ ] Open `http://127.0.0.1:8000/`.
- [ ] Confirm that the application dashboard loads successfully.
- [ ] Confirm that the AI service is available.
- [ ] Verify that the knowledge base displays the expected indexed corpus.
- [ ] Open System Info and verify model availability.
- [ ] Test one question in the AI Assistant.
- [ ] Clear the conversation before starting a new recording.
- [ ] Confirm that the local API configuration is working without exposing `.env` contents.

---

## 2. Screen Hygiene

Before recording, verify the following:

- [ ] `.env` is closed in every editor and terminal that may appear on screen.
- [ ] No API keys, passwords, session tokens, or other secrets are visible.
- [ ] Terminal output does not expose environment variables or credentials.
- [ ] Browser bookmarks bar is hidden if unnecessary.
- [ ] Browser zoom is set to 100%.
- [ ] Recording resolution is appropriate for the intended output.
- [ ] Windows notifications and other distracting alerts are disabled.
- [ ] Personal email, chat applications, and unrelated browser tabs are closed.
- [ ] No personal files or unrelated documents are visible.
- [ ] Only intended demonstration SOP documents are displayed.

---

## 3. Recorded Demo Sequence

The following table reflects the sequence in the existing 4:37 recording.

| Approximate Time | Scene | Demonstration |
|---|---|---|
| 00:03 | Dashboard | Dashboard overview, status indicators and KPI tiles |
| 00:40 | Knowledge Base | Active knowledge base documents and archived revision |
| 01:05 | System Info | Model availability and system configuration |
| 01:27 | Coolant question | AI Assistant answers the coolant concentration question |
| 01:55 | AL-104 question | AI Assistant explains the way-lubrication alarm |
| 02:21 | BH-220 question | AI Assistant retrieves the dimensional tolerance from Rev 04 |
| 02:44 | Abstention | AI Assistant declines to invent an answer about factory electricity consumption |
| 03:12 | Authentication | Sign-in and role-based access demonstration |
| 03:47 | Document upload | Document registration and upload form demonstration |
| 04:15 | Closing | Final application view and closing narration |

### Important Recording Disclosures

The existing video demonstrates the document upload form but does not submit the draft document.

Consequently:

- The document register remains empty in the recording.
- No new revision is activated.
- No archive operation is performed during the video.
- The video should not be described as demonstrating a completed document upload or activation workflow.

The video also uses synthetic narration and contains two recording segments joined at a stable screen.

---

## 4. Expected AI Assistant Responses

Use these reference answers when verifying the application before a new recording.

| Question | Expected Answer | Expected Source |
|---|---|---|
| Coolant concentration | Maintain coolant concentration between 6% and 8%. | MNT-MAN-CNC-02 Rev 02, page 1 |
| AL-104 | Way-lubrication oil level is low. Use ISO VG 68 oil and top up to MAX, then press RESET. | MNT-MAN-CNC-02 Rev 02, page 2 |
| BH-220 OD tolerance | ±0.050 mm at 90.000 mm, measured using a digital caliper. | QC-SOP-014 Rev 04, page 2 |
| Factory electricity consumption | The assistant should abstain because the knowledge base does not contain supporting evidence. | No source card expected |

**Important:** The LOTO question is part of the broader application validation, but it is not included in the existing recorded demo sequence.

If an answer differs during a future recording, investigate the response rather than editing footage to conceal an error. The demonstration should accurately represent the application's behaviour.

---

## 5. Audio and Narration

The existing video uses synthetic Windows SAPI narration.

For an optional re-recording:

- [ ] Test the microphone before recording.
- [ ] Minimize background noise, fan noise, and keyboard sounds.
- [ ] Use `DEMO_SCRIPT.md` as the narration reference.
- [ ] Speak clearly and maintain a consistent pace.
- [ ] Avoid reading API keys, passwords, personal file paths, or private URLs.
- [ ] Review narration timing against the actual screen transitions.

A human voice-over is optional. The current synthetic narration should be disclosed accurately when presenting the existing video.

---

## 6. Post-Recording Verification

Before publishing a replacement recording:

- [ ] Play the complete video from beginning to end.
- [ ] Confirm that the application remains readable throughout.
- [ ] Check that no credentials, personal information, or private configuration values are visible.
- [ ] Verify that displayed AI responses and source citations are accurate.
- [ ] Confirm that the narration matches the actions shown.
- [ ] Verify that the video and GIF play correctly.
- [ ] Confirm that all referenced screenshot files exist.
- [ ] Check the final file size and video resolution.
- [ ] Update `assets/demo/README.md` if recording specifications or scene timings change.
- [ ] Update the main README if the demo assets or links change.

---

## 7. Final Deliverables

The current demo deliverables are:

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

**Final status:** The demo video, workflow GIF, and ten supporting screenshots have been created. A future re-recording is optional.