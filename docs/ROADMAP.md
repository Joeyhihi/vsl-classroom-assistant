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

### P1: Foundation ✅ (merged; Windows smoke test passed 2026-10-18)
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

### P2: Frontend skeleton ✅ (merged; Windows voice check and CI passed 2026-10-18)
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

### P3: Walking skeleton ✅ (closed 2026-10-18, owner decision)
- **Deliverables:**
  - `packages/vsl-features` (spec, normalise, buffer, segmenter, decoding);
  - WS endpoint with the `feature_spec` handshake; `ReplayLandmarkSource`;
  - `gen_contracts.py`;
  - MediaPipe L1/L2 in the browser **[WIN]**, plus a Web Worker spike;
  - minimal landmarks-only recorder;
  - `TemplateClassifier` trained on 3–5 of the developer's own signs **[WIN]**, kept local and **never committed or used for the real model**;
  - L3 spike: `ServerLandmarkExtractor`, binary JPEG frames, parity report **[WIN]**.
- **Status (2026-10-18):** everything that can run without a camera or model is built and tested on the Mac: vsl-features, WS + handshake, segmenter, template classifier (tested on synthetic data), contracts generation, replay e2e (full stack, mock backend), recorder, metrics, ladder logic, L3 server extractor (tested with fakes). The MediaPipe extractors (L1/L2, worker spike) and the real L3 extractor are written but **have never executed**; that is the Windows step in [CROSS_PLATFORM_SETUP.md §11](CROSS_PLATFORM_SETUP.md#phase-3-windows-test-procedure).
- **Exit criteria:**
  - Replay E2E passes in CI.
  - Measured on Windows at each ladder level: **≥15 fps** and **processing latency ≤ 500 ms p95**. Processing = total − the segmenter's deliberate wait; see the decision note below. Total and wait are recorded too.
  - Memory and VRAM recorded.
  - The ADR-002 level is decided per machine.
  - If no level reaches 15 fps, the machine is documented as manual-only and the owner decides whether to continue.

- **Decision (2026-10-18, owner):** the P3 latency criterion changed from "≤ 1.0 s p95 hands-at-rest → rendered" to **processing ≤ 500 ms p95**.
  - Why: the first Windows run (L2, mock) gave total p95 1376 ms / p50 784 ms with 1.4 ms inference. About 600 ms of every total is the pause tolerance, which is a deliberate UX parameter, not hardware cost.
  - The pause tolerance will be tuned with Deaf signers in the P4 pilot and P6.
- **Windows run 1 findings (fixed):** handedness was flipped at L2, and a fast right hand flickered to "left". Hands are now matched to the pose wrists. Frames were batched (up to ~100 ms added); they are now sent one by one.

- **Final results (Windows, GTX 1650, `--preview`, mock model, run 3):**

  | Level | fps | Processing p50 / p95 | Wait p50 / p95 | Total p50 / p95 | Signs ended by (lowered · still · too long) | Source | JS heap |
  |---|---|---|---|---|---|---|---|
  | L1 | 12.4 ❌ | 77 / 84 ms ✅ | 0 / 653 ms | 77 / 737 ms | 1 · 0 · 7 | L1 worker/GPU | 34 MB |
  | **L2** | **22.8 ✅** | **141 / 146 ms ✅** | 0 / 601 ms | 146 / 668 ms | 1 · 0 · 6 | L2 main/GPU | 49 MB |
  | L3 | not executed | | | | | (run showed `L1 worker/GPU`) | |

- **Exit decision:** the criterion is met by **L2**, which is the working level for the GTX 1650 laptop. L1 met it in run 2 (17.0 fps) but not in run 3, and L2 has no face landmarks.
  - **L3** is recorded as **set up correctly but never executed**: the backend reports the extractor as available, but the benchmark session ran at L1. This is option (b), the owner's decision.
- **Carried into P4 (first task):**
  - 26 of 31 signs ended by **max duration (4 s)**, so the segmenter rarely detected the real end of a sign on webcam data.
  - Likely causes: resting hands sit above the rest line, and tracker jitter exceeds the 0.15 "still" threshold.
  - A separate bug was fixed: hands were compared without labels, so one hand vanishing while the other appeared looked like fast motion.
  - Tuning uses `scripts/analyze_segmentation.py` on the owner's own recorder takes.

### P4: Data tooling (requires B1 + B2) — tools merged 2026-10-18 (PR #10); Windows live checks pending

- **Owner decision (2026-10-18):** the tools are built *before* B1/B2, and only the developer records themselves. Recording anyone else still requires B1 + B2.
- **Tasks and status:**

  | # | Task | Status |
  |---|---|---|
  | 4.0 | Segmentation tuning: live Windows check | Implemented (PR #9); **live check pending** |
  | 4.1 | Storage + append-only manifest + schema + consent rule + dev vocabulary | Done |
  | 4.2 | Recorder ingest API → `DATA_ROOT` | Done |
  | 4.3 | Recorder v2 (session, vocabulary prompts, 3/6 s takes) | Done |
  | 4.4 | Review view (replay, accept/reject/relabel) | Done |
  | 4.5 | Deletion script (dry run, tombstones) | Done |
  | 4.6 | Quality report | Done |
  | 4.7 | Templates from accepted manifest samples, plus a live test on own signs | Code done; **Windows live test pending** |

- **Decisions taken autonomously (2026-10-18; the owner was away, review and change if needed):**
  1. The backend writes recordings into `DATA_ROOT`; there are no browser downloads.
  2. Consent `SELF` for `DEV-..` signer IDs only; every other ID is refused in code until B2.
  3. The dev vocabulary is a placeholder (`DEV_01`–`03` "Ký hiệu thử N"). Rename `text_vi` in `ml/vocabulary/vocabulary.dev.json`.
  4. The recorder's label lock was replaced by sessions and item selection. Each take is labelled at upload, so mislabelling is no longer possible.
- **Exit (self-recording version):** one full session recorded, reviewed, reported, templates built from it and run live on Windows; deletion verified; third-party recording blocked in code (tests); no data in the repo (guard plus a `DATA_ROOT` check).
- **First task: segmentation tuning — implemented 2026-10-18, live check pending.**
  - Data (1 take per label, L2): resting hands visible at y ≈ 0.6 shoulder widths below the shoulders (inside the frame, above the old 1.2 line); raised hold at 0.37–0.40; signing at ≤ 0.18. Active-wrist jitter p95 ≤ 0.34; signing p95 ≥ 1.75.
  - New defaults: rest line 0.45, start 1.0, still 0.7 (smoothed, 150 ms), per-hand speed.
  - Recorder: the label is locked while takes exist, and 3 s or 6 s takes can be chosen.
  - The synthetic signer was moved to laptop framing to match.
  - Original task description: Record REST_DESK / REST_LAP / REST_DOWN / HOLD / 3 own signs (5 takes each, L2), run `scripts/analyze_segmentation.py`, and set the segmenter thresholds (plus smoothing, if the data supports it) from the results. Exit: no false starts on rest takes, every sign take starts, and "too long" is no longer the dominant close reason on a rerun.
- **Deliverables:**
  - full recorder with consent ID, manifest, and condition tags;
  - manifest schema and validator;
  - review UI;
  - deletion script.
- **Exit criteria:**
  - B3 pilot quality report, including inter-annotator agreement.
  - No data inside the repo (guard test passes).

### P5: Dataset + first model (requires B4) **[WIN]** — current: pipeline built 2026-10-18 (prototype mode, PR pending review)

- **Owner decision (2026-10-18): fast prototype.** The pipeline is built and run on the developer's own recordings now. B4 data is still needed for G5. Details: [AI_ML_STRATEGY.md §2b](AI_ML_STRATEGY.md#2b-phase-5-implementation-as-built-prototype-mode).
- **Status:**

  | Deliverable | Status |
  |---|---|
  | Signer-grouped splits + leakage check | Done (falls back to session / sample for one signer, labelled) |
  | Template vs GRU vs TCN report | Done (`train_sign_model.py`, report in `DATA_ROOT/reports/models/`) |
  | Calibration | Done (temperature + operating point on validation) |
  | ONNX export, model card, sha256 | Done (parity check + backend reload) |
  | Registry checks, `VSL_MODEL_MODE=onnx` | Done |
  | ML smoke job in CI (synthetic) | Done (`ml-smoke`); **first run pending** (needs a push) |
  | First model on own data + live test | **Pending on Windows** |
  | G5 on ≥3 held-out signers | Blocked on B4 |

- **Deliverables:**
  - signer-grouped splits;
  - template vs GRU vs TCN report;
  - calibration;
  - ONNX export with model card and sha256;
  - registry checks;
  - ML smoke job in CI (synthetic data).
- **Gate G5 (go/no-go):** the owner reviews macro-F1, per-signer minimum, and open-set FAR on held-out signers. The owner then approves the target operating point **or** a pivot: a smaller vocabulary, more data, different features, or stopping.

### P6: Stabilisation & UX — current: code built 2026-10-18 (mock-tested, PR pending review)

- **Status:**

  | Deliverable | Status |
  |---|---|
  | Thresholds at the G5 operating point | Done in P5 (`calibration.json` from the operating point); real values wait for G5 |
  | Uncertain and rejected UI, candidate policy | Done (P3), now with icons |
  | Feedback API + delete | Done: `POST`/`DELETE /api/v1/feedback`, ✓/✗/? on confirmed signs (hidden in mock mode), deleted by "Xoá dữ liệu cục bộ" |
  | SignGuideView, LargeDisplayView | Done ("Danh sách ký hiệu", "Màn hình lớn" with full-screen) |
  | `ResourceManager` | Done (fake-engine tests); first heavy engine is STT in P7 |
  | Every failure-mode row tested | Partly; review against ARCHITECTURE §9 |
  | UX sessions with Deaf users scheduled | **Owner task** |

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
