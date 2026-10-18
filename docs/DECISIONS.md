# Architecture Decision Records

Status values: **Accepted**, **Provisional** (needs measurement or validation), **Superseded**. Each record gives the context, the options considered, the decision, the trade-offs, and when to revisit it.

---

## ADR-001: Modular monolith — Accepted
- **Context:** a solo developer, a single laptop, a small MVP.
- **Options:**
  - microservices;
  - a modular monolith: one backend process plus a SPA.
- **Decision:** a modular monolith with strict module boundaries (`api`, `schemas`, `recognition`, `inference`, `speech`) and a shared `vsl_features` library.
- **Trade-offs:** simple to run and debug. Modules can't be scaled independently, which this project doesn't need.
- **Revisit when:** multi-device or multi-user deployment.

## ADR-002: Landmark extraction ladder — Provisional (P3 benchmark on Windows)
- **Context:**
  - Video should stay in the browser.
  - The same extractor should be used for data collection and inference.
  - Browser WASM/WebGL performance is unverified on the target hardware.
  - Low fps undersamples movement.
- **Options:**
  - browser only;
  - server only;
  - a browser default with a defined server fallback.
- **Decision:** a three-level ladder, using measured fps:
  - **L1:** browser MediaPipe Holistic with GPU delegate, in a Web Worker if the spike passes.
  - **L2:** browser reduced: 480p input, Hand + Pose landmarkers, no face.
  - **L3:** server-side Python MediaPipe. The browser sends JPEG frames (≤640×480, ≤20 fps) as binary WS messages to `127.0.0.1`. Frames are processed in memory and never stored.

  **Rules:**
  - L1 → L2 happens automatically when L1's p50 stays below 15 fps for 5 s after a 3 s warm-up.
  - L3 is **offered** and requires the user to confirm.
  - Switches happen only at session boundaries.
  - The chosen level is remembered per machine.
  - Python MediaPipe is an **optional extra** (`[server-extraction]`).
- **Trade-offs:**
  - L3 adds JPEG encode and decode cost and runs on the same CPU, so it is not guaranteed to be faster.
  - It reintroduces a native dependency, which is kept optional.
  - It may produce slightly different landmarks than the browser extractor. A parity test is required, and `extractor_backend` is recorded.
  - Motion blur is a camera-exposure problem that no level fixes.
- **Revisit when:** P3 measurements are in. If L3 fails too, the machine is manual-only.
- **P3 implementation:** `ladder.ts` (decision logic), `extractor.ts` (worker first, main-thread fallback), `sources.ts` (Replay / Camera / Server), `server_extractor.py` (L3, optional extra, lazy import). L3 frames use a 16-byte little-endian header (`t_ms` u64, width u16, height u16, 4 reserved) followed by the JPEG. Pending Windows measurements.

## ADR-003: REST + one WebSocket — Accepted
- **Decision:**
  - REST for discrete operations: health, vocabulary, models, feedback, STT.
  - One WS for the recognition stream, with JSON messages (binary for L3 frames), `protocol_version`, and snake_case on the wire and in TypeScript.
- **Trade-offs:** JSON is larger than binary, which is negligible on localhost and easy to debug.
- **Revisit when:** measured CPU or bandwidth problems call for binary landmark frames.

## ADR-004: Landmark-based recognition, not pixels — Accepted
- **Reasoning:** privacy, small data, CPU inference, and robustness to background.
- **Trade-offs:** fine appearance cues are lost, and results depend on the quality of the landmark tracker.
- **Revisit when:** there are thousands of samples per class and suitable GPU resources.

## ADR-005: Message-unit utterance classification — Provisional (G5)
- **Decision:**
  - Each vocabulary item is a single sign or a fixed phrase of up to 3 s, classified as a whole.
  - An utterance segmenter detects rest → signing → rest and tolerates pauses of about 600 ms.
  - Input is variable length with masking.
  - Models: a template/DTW sanity baseline, then a GRU (baseline) compared with a 1D-TCN on leave-signer-out validation.
  - Rejection: background and distractor classes plus a calibrated threshold and margin.
- **Trade-offs:** the signer has to return to rest between messages, so this does not handle continuous signing.
- **Revisit when:** users reject the return-to-rest interaction, or continuous signing is required (CTC or transformer models).

## ADR-006: Local-first on loopback — Accepted
- **Decision:**
  - Bind to `127.0.0.1`, with no cloud.
  - CSP allows connections only to the app's own origin and loopback WS.
  - MediaPipe assets are self-hosted.
- **Revisit when:** LAN mode is needed, which requires HTTPS plus a pairing token.

## ADR-007: Data and artifacts outside git — Accepted
- **Decision:**
  - `DATA_ROOT` lives outside the repo, by default on the Windows laptop.
  - An encrypted identity register is stored separately.
  - Artifacts carry sha256 model cards. ONNX or `.npz` only, no pickle.
  - Public release of a model requires the consent scope from every contributor in its training data.
  - The public repo holds synthetic fixtures only.
- **Revisit when:** a team forms, at which point DVC or object storage could be considered.

## ADR-008: Toolchain — Accepted (revised 2026-10-18: Python 3.12)
- **Decision:**
  - A uv workspace with a universal `uv.lock` and **Python 3.12** (`requires-python = ">=3.12,<3.13"`).
  - CPU torch on both OSes (P5). There is no CUDA torch.
  - npm with `package-lock.json` and Node 24 LTS.
  - CI on Ubuntu and Windows, with a manual-only macOS workflow.
- **Trade-offs:** uv is newer than pip or Poetry, but its universal lockfile is exactly what a mixed Mac/Windows setup needs.
- **Revisit when:** a required package lacks Python 3.12 wheels for either OS, or the ecosystem drops 3.12.
- **P1 wheel check (2026-10-18):** all planned packages have wheels usable on 3.11 for macOS arm64 and win_amd64, **except numpy ≥2.5, which requires Python 3.12**. The original reason for 3.11 (old MediaPipe wheel limits) no longer applies, because mediapipe 1.x ships `py3-none` wheels. 
- **Revision (2026-10-18, owner decision):** the workspace moves to **Python 3.12**. PyPI check: numpy 2.5.4, onnxruntime 1.31, ctranslate2 4.8.3, av 19.0.1 and torch 2.14.1 all have cp312 wheels for macOS arm64 and win_amd64; faster-whisper and mediapipe 1.x are Python-version-independent. numpy is not a dependency until P3, so no pin is needed now; P3 adds it unpinned (current 2.5.x supports 3.12). This resolves RISKS R11.

## ADR-009: Single preprocessing source — Accepted
- **Decision:**
  - `packages/vsl-features` (NumPy only) is used by both the backend and `ml/`.
  - The server sends the `feature_spec` to the client in `session.started`, so the browser packer never hard-codes landmark indices.
- **Trade-offs:** adds one workspace package.
- **P3:** the recorder, which has no WS session, gets the same spec from `GET /api/v1/feature-spec`.

## ADR-010: TTS uses local browser voices only in the MVP — Accepted
- **Decision:**
  - `speechSynthesis` with `vi-VN` voices where `localService === true`. Network voices are excluded by default.
  - **Backend TTS (Piper, VieNeu) is deferred out of the MVP.**
  - If a machine has no local voice, the fallback is text plus the large display.
- **Revisit when:** after the MVP, if the P2 check shows no usable local voice on target machines. Then: verify the licence, and bring in backend TTS under ADR-015's swap rule.

## ADR-011: STT is push-to-talk, CPU int8 — Provisional (G7)
- **Decision:**
  - faster-whisper (or PhoWhisper converted to CTranslate2) on CPU at int8, loaded only when first needed.
  - Push-to-talk only.
  - Chrome Web Speech recognition is rejected because it sends audio to a remote server.
- **Revisit when:** the measured Vietnamese WER or latency is unacceptable. Then defer, or try GPU on Windows after G7.

## ADR-012: No database, no authentication — Accepted
- **Decision:** settings in `localStorage`; feedback as JSONL; an Origin allow-list for HTTP **and** WS, which protects against cross-site WebSocket hijacking.
- **Revisit when:** LAN mode or persistence across users is needed.

## ADR-013: Chromium only — Accepted
- **Revisit when:** pilot users need Safari or Firefox.

## ADR-014: Intentional message mode and confirm before speech — Accepted (pending Deaf user validation)
- **Decision:**
  - Recognition runs only after the student starts it.
  - Every candidate must be confirmed before it reaches the transcript or speech.
  - Auto-speak is off.
- **Revisit when:** UX sessions show that confirmation is impractical. Explore other input methods; never auto-speak by default.

## ADR-015: CPU-only Python inference and a resource manager — Accepted (revisit after P7)
- **Context:** the M1 has 8 GB of unified memory. The GTX 1650 has 4 GB of VRAM, and Windows plus Chrome use an estimated (unmeasured) ~1.5 GB.
- **Decision:**
  - All Python inference runs on CPU in the MVP: the sign model on ORT CPU, STT on CTranslate2 int8 CPU. There is no backend TTS model.
  - The GPU is left to Chrome and MediaPipe.
  - A `ResourceManager` enforces:
    - lazy loading;
    - idle unload after `VSL_HEAVY_MODEL_IDLE_UNLOAD_S` (default 300 s);
    - a RAM guard (`VSL_MIN_FREE_RAM_MB`, default 1500) that refuses loads with `RESOURCE_EXHAUSTED`;
    - a **swap rule**: at most one heavy model is resident, and loading one unloads the other.
  - Post-G7 GPU STT is a Windows opt-in. It loads only if `nvidia-smi` reports free VRAM ≥ `VSL_MIN_FREE_VRAM_MB`, uses `int8`/`int8_float32`, and falls back to CPU on a CUDA out-of-memory error.
- **Trade-offs:** CPU STT is slower, which is acceptable for push-to-talk segments.
- **Revisit when:** P7 measurements show CPU latency is unacceptable and VRAM headroom is proven.

## ADR-016: Separate start scripts and dev-only mock model mode — Accepted
- **Context:** the M1 cannot comfortably run the browser, MediaPipe, the IDE, the Vite dev server, and models together. The owner requires separate start scripts. A combined launcher uses the same memory, but it prevents running only one side.
- **Decision:**
  - `scripts/run_backend.py` and `scripts/run_web.py` are the only launchers. **There is no `dev.py`.**
  - `VSL_MODEL_MODE=mock` loads **no** ML libraries and sends scripted predictions (`cycle` or `timer`). It is refused unless `VSL_ENV=dev`. The UI shows a permanent MOCK badge, and **speech is disabled**.
  - The frontend `VITE_LANDMARK_SOURCE=replay` skips the camera and MediaPipe.
  - The M1 runs only mock and replay modes, plus unit tests.
  - **Clarification (P2):** "speech disabled in mock mode" applies to **sign-recognition output**, so scripted predictions can never be spoken. Text the user types themselves can always be spoken, because it is not generated by the model.
- **Trade-offs:** two terminals instead of one, and a mock path that has to be maintained, kept small and covered by tests.
- **Revisit when:** never for the M1 rule. Mock mode stays for CI and UI development.
