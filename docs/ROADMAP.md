# Roadmap

Work runs in **two parallel tracks**. A phase is complete only when **all** of its exit criteria hold **and the owner has reviewed it**. Nothing is committed without the owner's approval. Steps marked **[WIN]** run only on the Windows laptop; the M1 uses mock mode and unit tests only.

## Track B: people, vocabulary, consent (starts now)

| Step | Deliverable | Gate |
|---|---|---|
| B0 | Roles confirmed (lead reviewer, annotators, Deaf co-design participants, community partner); compensation agreed | — |
| B1 | Vocabulary v1 validated: items, variants, `unit_type`, `mirroring_ok`, icons, distractor list | Needed by P4 |
| B2 | Consent package (Vietnamese text + VSL video), identity-register procedure, data-handling plan, legal applicability review | **No third-party recording before B2 is approved** |
| B3 | Pilot recording: 1–2 signers | After P4 tooling |
| B4 | Full collection: ≥12 signers × ≥5 repetitions, distractors, background, realistic subset | Needed by P5 |

## Track A: software

### P0: Discovery & architecture ✅ (approved 2026-10-18)
- **Deliverables:** 15 docs + README.
- **Exit criteria:** owner approval; decisions in §B of the plan answered.

### P1: Foundation (current)
- **Goal:** a reproducible workspace on both OSes, a health endpoint, mock mode, scripts, and CI.
- **Deliverables:**
  - uv workspace (root + `services/ai-backend`);
  - Vite React-TS app shell showing backend health;
  - `GET /api/v1/health`;
  - config with the mock-mode guard; `MockClassifier`;
  - security middleware (Origin allow-list, headers, body limit) and the error envelope;
  - scripts `bootstrap`, `run_backend`, `run_web`, `check`, `doctor`, `guard_no_media`;
  - CI (Ubuntu + Windows, gitleaks) plus a manual macOS workflow;
  - `.gitattributes`, `.editorconfig`, `.python-version`, `.nvmrc`, `.env.example`, `.gitignore` additions;
  - `model-artifacts/README.md`, `ml/datasets/README.md`.
- **Out of scope:** onnxruntime, torch, mediapipe, WebSocket, camera.
- **Likely files:** root config files, `scripts/*`, `services/ai-backend/**`, `apps/web/**`, `.github/**`.
- **Dependencies:** none.
- **Risks:** npm lockfile across OSes; Python wheel availability (resolved: Python 3.12, ADR-008).
- **Exit criteria:**
  1. `run_backend.py` and `run_web.py` each start **on their own**. There is no `dev.py`.
  2. Health returns a valid `HealthResponse`. Mock mode is the default, and it is refused when `VSL_ENV` is not `dev`.
  3. `scripts/check.py` passes on the Mac.
  4. CI is green on Ubuntu and Windows.
  5. The Windows smoke checklist passes on the real laptop **[WIN]**.
  6. Python wheel availability is recorded (done 2026-10-18; this led to the move to Python 3.12) for fastapi, numpy, onnxruntime, mediapipe, and faster-whisper on `macosx_arm64` and `win_amd64`. This means *checking PyPI*, not installing.
- **Test plan:** pytest (health, config, security, errors, mock classifier); Vitest (app shell, a11y); a contract test for the health example.

### P2: Frontend skeleton
- **Deliverables:**
  - permission flows: denied, unavailable, in use;
  - mirrored preview and camera selector;
  - manual text → transcript → **local vi-VN TTS**;
  - connection banner; Settings and Privacy views;
  - Playwright with a fake camera.
- **Exit criteria:**
  - vi-VN local voice availability recorded on macOS and Windows. Checking which voices the browser reports is not ML.
  - axe is clean.
  - E2E tests pass with the backend both up and down.
- **Risk:** no local Vietnamese voice on Windows. The fallback is text plus the large display; backend TTS stays out of the MVP.

### P3: Walking skeleton (the smallest end-to-end prototype)
- **Deliverables:**
  - `packages/vsl-features` (spec, normalise, buffer, segmenter, decoding);
  - WS endpoint with the `feature_spec` handshake; `ReplayLandmarkSource`;
  - `gen_contracts.py`;
  - MediaPipe L1/L2 in the browser **[WIN]**, plus a Web Worker spike;
  - minimal landmarks-only recorder;
  - `TemplateClassifier` trained on 3–5 of the developer's own signs **[WIN]**, kept local and **never committed or used for the real model**;
  - L3 spike: `ServerLandmarkExtractor`, binary JPEG frames, parity report **[WIN]**.
- **Exit criteria:**
  - Replay E2E passes in CI.
  - Measured on Windows at each ladder level: **≥15 fps** and **≤1.0 s p95** from rest to rendered.
  - Memory and VRAM recorded.
  - The ADR-002 level is decided per machine.
  - If no level reaches 15 fps, the machine is documented as manual-only and the owner decides whether to continue.

### P4: Data tooling (requires B1 + B2)
- **Deliverables:**
  - full recorder with consent ID, manifest, and condition tags;
  - manifest schema and validator;
  - review UI;
  - deletion script.
- **Exit criteria:**
  - B3 pilot quality report, including inter-annotator agreement.
  - No data inside the repo (guard test passes).

### P5: Dataset + first model (requires B4) **[WIN]**
- **Deliverables:**
  - signer-grouped splits;
  - template vs GRU vs TCN report;
  - calibration;
  - ONNX export with model card and sha256;
  - registry checks;
  - ML smoke job in CI (synthetic data).
- **Gate G5 (go/no-go):** the owner reviews macro-F1, per-signer minimum, and open-set FAR on held-out signers. The owner then approves the target operating point **or** a pivot: a smaller vocabulary, more data, different features, or stopping.

### P6: Stabilisation & UX
- **Deliverables:**
  - thresholds at the G5 operating point;
  - uncertain and rejected UI; candidate policy;
  - feedback API + delete;
  - SignGuideView and LargeDisplayView;
  - `ResourceManager` (lazy load, idle unload, RAM guard, swap rule unit-tested with fake engines).
  - Backend TTS is **not** included (deferred).
- **Exit criteria:** every failure-mode row is tested; UX sessions with Deaf users are scheduled.

### P7: STT subtitles (gated) **[WIN]**
- **Deliverables:**
  - push-to-talk capture; `/stt/transcriptions`;
  - faster-whisper (or PhoWhisper in CTranslate2 format) on **CPU int8**;
  - WER and latency measured for ≥2 model sizes on a consented test set;
  - RSS measured while recognition is active;
  - optional GPU experiment (`int8`/`int8_float32`) with VRAM measured alongside Chrome, and an OOM → CPU fallback test.
- **Gate G7:** the owner approves STT, or it is deferred. GPU stays off by default unless the measurements justify turning it on.

### P8: Evaluation, accessibility, privacy, Windows
- **Exit criteria:**
  - held-out signer report;
  - WCAG 2.2 AA audit plus Deaf user sessions;
  - privacy checklist ([SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md#4-privacy-review-checklist-run-before-p8-and-p9));
  - full Windows pass.

### P9: Packaging + controlled adult pilot
- **Deliverables:**
  - `static.py`, so the backend serves the built SPA from one origin, started with one command per OS;
  - pilot protocol with consent;
  - feedback analysis.
- **Exit criteria:** pilot completed under the protocol; findings documented.
