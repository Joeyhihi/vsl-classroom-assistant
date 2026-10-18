# Requirements

This document separates **confirmed requirements** (stated by the project owner) from **derived requirements** (needed to meet the confirmed ones). Phase numbers refer to [ROADMAP.md](ROADMAP.md).

## 1. Confirmed constraints

- C1. Primary direction: VSL → Vietnamese text → Vietnamese speech. Secondary direction: spoken Vietnamese → subtitles.
- C2. The MVP vocabulary is about 20–50 classroom message units, validated by VSL experts and Deaf signers.
- C3. Deployment is a **single laptop**: browser and backend both run on `localhost`. No LAN or cloud.
- C4. Browsers: **Chrome and Edge only** for the MVP.
- C5. Development happens on a MacBook Air M1 with 8 GB RAM, using **mock mode and unit tests only**. The real pipeline is tested on a Windows laptop (GTX 1650, 4 GB VRAM).
- C6. Pilots involve **adults only**. K-12 use is a future phase.
- C7. The **repository is public**. Fixtures are synthetic only, and no personal data goes into git.
- C8. Video must not be uploaded or permanently saved by default.

## 2. Functional requirements

| ID | Requirement | Phase | Acceptance criteria |
|---|---|---|---|
| FR-1 | Webcam access and permission handling | P2 | Permission is requested only after a user action. The *denied*, *no camera*, and *camera in use* states each show a Vietnamese explanation and a recovery step. |
| FR-2 | Camera preview and recognition status | P2–P3 | The preview is mirrored. The status shows text, an icon, and colour for: waiting for hands, ready, signing, processing, paused. |
| FR-3 | Near-real-time recognition of supported message units | P3–P5 | Measured on Windows: ≥15 fps landmarks, and ≤1.0 s p95 from *hands at rest* to *prediction rendered*. |
| FR-4 | Vietnamese text output | P3 | Each prediction shows `text_vi` at ≥32 px together with an icon or category. |
| FR-5 | Optional Vietnamese TTS | P2 | Uses only local `vi-VN` browser voices (`localService === true`). If no such voice exists, the Speak button is disabled and an install guide is shown. |
| FR-6 | Confirmation before speech | P3/P6 | Nothing is spoken and nothing is added to the transcript unless the user explicitly confirms. Auto-speak is off by default. |
| FR-7 | Uncertainty state | P6 | An `uncertain` prediction shows its top 3 alternatives. A `rejected` one shows "Không nhận ra — hãy ký lại" (not recognised, please sign again) and no text. |
| FR-8 | Conversation transcript | P2 | The transcript lists entries with source (sign, manual, speech), speaker, and time. It is kept in memory only and exported only when the user chooses. |
| FR-9 | Manual text input fallback | P2 | Works with no camera, no backend, and no model. |
| FR-10 | Spoken Vietnamese transcription (push-to-talk) | P7 (gated at G7) | Whole-segment subtitles. Ships only if the measured Vietnamese word error rate (WER) and latency are approved. |
| FR-11 | Start/stop recognition controls | P3 | There is a button and a keyboard equivalent. When the browser tab is hidden, recognition pauses automatically. |
| FR-12 | Loading, error, permission-denied, and disconnected states | P2–P3 | Every row of the failure-mode table in [ARCHITECTURE.md](ARCHITECTURE.md#failure-modes) is implemented and tested. |
| FR-13 | Basic evaluation and feedback | P6 | The user can mark a verdict (correct, incorrect, unsure, plus the expected sign) for each prediction. Feedback is stored in a local file, deletable in one action. An offline evaluation report exists (P5). |
| FR-14 | Privacy-conscious default | P1+ | No video leaves the browser in the default mode. No video, audio, or landmarks are written to disk outside data-collection mode. |
| FR-15 | Supported-signs guide (derived) | P6 | Lists every supported message unit with its icon and a consented reference clip or illustration. |
| FR-16 | Large display for the teacher (derived) | P6 | Shows the last confirmed message full-screen in large type. |
| FR-17 | Mock model mode for development (derived) | P1 | `VSL_MODEL_MODE=mock` loads no ML libraries and sends scripted predictions. It is refused unless `VSL_ENV=dev`. The UI shows a MOCK badge and speech is disabled. |
| FR-18 | Data-collection recorder (derived) | P3 (minimal), P4 (full) | Records landmarks only. Requires a consent ID (from P4) and shows a visible recording banner. |

## 3. Non-functional requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Privacy | The backend binds to `127.0.0.1` only. HTTP and WebSocket connections are checked against an Origin allow-list. A Content Security Policy (CSP) allows connections only to the app's own origin. |
| NFR-2 | Offline | Everything works without internet once installed. Model assets are self-hosted, with no CDN at runtime. |
| NFR-3 | Accessibility | Target WCAG 2.2 AA. Status is never conveyed by sound alone. Full keyboard operation. |
| NFR-4 | Performance | The P3 thresholds above, measured on Windows. On the M1, memory comes first: mock or replay mode is the default. |
| NFR-5 | Resource safety | Python inference runs on CPU only in the MVP. Large models are lazy-loaded, unloaded after a period idle, and blocked by a RAM guard (ADR-015). |
| NFR-6 | Portability | The same setup commands work on macOS and Windows. Lockfiles are committed. |
| NFR-7 | Maintainability | API contracts have a single source (Pydantic, generating TypeScript from P3). The modular monolith has clear module boundaries. |
| NFR-8 | Logging safety | Logs never contain landmarks, audio, transcript text, or free text. |
| NFR-9 | Honesty | The UI states the system's limits (closed vocabulary, not translation). Development models carry a visible badge. |

## 4. Explicit exclusions (MVP)

Unrestricted or continuous VSL translation; sentence generation; fingerspelling; a mobile app; LAN or multi-device use; cloud inference; user accounts and authentication; databases; Docker or Kubernetes; backend TTS models; GPU inference in Python; Safari and Firefox; use with minors or in schools.

## 5. User stories

1. *As a Deaf student*, I want to sign "please repeat" and have the laptop say it after I confirm, so the teacher hears my request.
   - **Given** recognition is active and a model is loaded,
   - **when** I sign a supported unit and return my hands to rest,
   - **then** within 1 s (p95) I see the text and icon,
   - **and** pressing Confirm speaks it and adds it to the transcript.
2. *As a Deaf student*, if the system is unsure, I want to choose from alternatives or dismiss them, so wrong words are never spoken.
   - **Given** an `uncertain` prediction, I see 3 alternatives that I can pick with keys 1–3 or dismiss with Esc. Nothing is spoken automatically.
3. *As a student*, I want to type a message when recognition fails.
   - Manual text works with the backend stopped.
4. *As a teacher*, I want to read the student's message from across the room.
   - The large display shows the last confirmed message at ≥96 px.
5. *As a teacher* (P7, gated), I want to hold a button and speak so the student reads my words.
   - Push-to-talk produces a subtitle segment. The microphone is active only while the control is held, and a "Đang nghe" (listening) indicator is visible.
6. *As a developer on the M1*, I want to work on the UI without loading models.
   - `run_backend.py --mock` plus replay mode runs with no ML libraries imported.
7. *As a contributor*, I want my data deleted if I withdraw.
   - The withdrawal procedure in [DATASET_AND_ANNOTATION.md](DATASET_AND_ANNOTATION.md) removes my samples and excludes them from the next model release.

## 6. Definition of Done (applies to every change)

- Code, tests, and documentation are updated together. `uv run python scripts/check.py` passes locally.
- CI is green on Ubuntu and Windows, including gitleaks and `guard_no_media`.
- No new dependency without a justification in the PR, and an ADR if it is architectural.
- The accessibility checks pass for any changed UI. Vietnamese strings live in `apps/web/src/i18n/vi.ts`.
- No personal data, media, or models are committed.
- The owner reviews before merge. Commits happen only after the owner approves.

## 7. Traceability (requirement → component)

| Requirement | Component(s) |
|---|---|
| FR-1, FR-2 | `apps/web/src/features/camera`, `components/camera` |
| FR-3 | browser `features/landmarks`, backend `recognition/*`, `packages/vsl-features` |
| FR-4, FR-7 | `components/recognition`, backend `vsl_features.decoding` |
| FR-5 | `features/tts/speechSynthesis.ts` |
| FR-6 | `features/recognition/recognitionMachine.ts` (candidate policy) |
| FR-8 | `features/transcript` |
| FR-9 | `components/compose` |
| FR-10 | `features/stt`, backend `speech/stt_engine.py`, `inference/resource_manager.py` |
| FR-11 | `components/recognition/StartStopButton`, visibility handling in `useRecognitionSession` |
| FR-12 | `components/system`, `errors.py`, failure-mode table |
| FR-13 | backend `feedback_store.py`, `ml/src/vsl_ml/evaluate.py` |
| FR-14, NFR-1 | `security.py`, CSP, `guard_no_media.py` |
| FR-17 | `config.py` (`model_mode`), `recognition/classifiers.py` (`MockClassifier`) |
| FR-18 | `features/recorder`, `views/RecorderView` |
| NFR-5 | `inference/resource_manager.py` |
