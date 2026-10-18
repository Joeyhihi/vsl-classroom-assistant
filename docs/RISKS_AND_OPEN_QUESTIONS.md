# Risks & Open Questions

## 1. Highest-risk assumptions (ranked)

| # | Assumption | Impact if wrong | How and when it is tested |
|---|---|---|---|
| R1 | ≥12 signers × ≥5 repetitions gives usable signer-independent accuracy **and** open-set rejection | Unusable recognition | Learning curves and held-out signers at G5 |
| R2 | Signers accept returning to rest between messages | Segmentation fails in natural use | Deaf user sessions (P3 replay demo, P6) |
| R3 | Browser Holistic reaches ≥15 fps on the Windows laptop | Undersampled motion | P3 benchmark; ADR-002 ladder |
| R4 | A local vi-VN TTS voice exists on Windows and macOS | No speech output | P2 voice check; fallback is text plus the large display |
| R5 | Vietnamese STT quality fits CPU int8 | No subtitles | G7 |
| R6 | Confirming while signing is practical | Slow or awkward use | P6 UX sessions |
| R7 | Contributor data handling meets Vietnamese law | Legal or ethical exposure | B2 legal applicability review |
| R8 | Python 3.12 wheels exist for every dependency on macOS arm64 and win_amd64 | Setup breaks | **Checked on PyPI in P1:** all planned packages have them |
| R9 | The npm lockfile works across both OSes | Windows build fails | Windows CI job |
| R10 | The L3 server extractor gives landmarks close enough to the browser extractor | Model skew under L3 | P3 parity report |
| R11 | Python 3.11 stays viable | numpy has dropped 3.11 (2.5+ needs 3.12), and other scientific packages will follow, leaving the project on old pins | **Resolved 2026-10-18:** moved to Python 3.12 (ADR-008) |

## 2. Verification tasks (claims not yet verified)

| Claim | Source status | Task / phase |
|---|---|---|
| MediaPipe HolisticLandmarker available for Web | Verified in Google docs | — |
| Holistic fps on target hardware | **Unverified** | P3 [WIN] |
| MediaPipe Python wheels for 3.11 on mac arm64 / win_amd64 | **Checked on PyPI, 2026-10-18:** mediapipe 1.1.1 ships `py3-none` wheels for macOS arm64 and win_amd64, so it works on 3.11 | Done (P1) |
| Python 3.11 wheels for other planned deps | **Checked on PyPI, 2026-10-18:** fastapi 0.143 (pure Python), onnxruntime 1.31 (cp311), faster-whisper 1.2.1, ctranslate2 4.8.3 and av 19.0.1 all have cp311 wheels for macOS arm64 and win_amd64. **numpy 2.5.x requires Python ≥3.12**; 2.4.6 is the newest with cp311 wheels. | **Resolved:** moved to Python 3.12; cp312 wheels confirmed for numpy, onnxruntime, ctranslate2, av and torch (R11) |
| faster-whisper GPU needs CUDA 12 + cuDNN 9; on Windows the libraries come from a bundle | Verified in the faster-whisper README | P7 |
| GTX 16xx fp16 problems with CTranslate2 | Unverified (reported in other stacks) | P7 |
| ~1.5 GB VRAM used by Windows + Chrome | Unverified estimate | P3 [WIN] Task Manager |
| Piper vi_VN and VieNeu licences | Unverified | Post-MVP only |
| Local vi-VN voices on macOS and Windows | **macOS recorded (2026-10-18):** macOS 15.8 + Chrome 155 exposes one Vietnamese voice, "Linh" (`vi-VN`, `localService: true`), in headless and headed mode, with no network Vietnamese voices. **Windows: not yet checked.** | Windows: open Settings → Chẩn đoán in the app on the Acer laptop (P2 exit) |
| Worker spike: MediaPipe tasks-vision 1.0.1 in a module Web Worker (ES-module WASM loader, GPU delegate) | **Unverified**: code written, never executed (no MediaPipe on the Mac) | P3 Windows step 2 |
| Python `HolisticLandmarker` API and result shape in mediapipe 1.x (L3) | **Unverified; P3 closed without executing L3** (owner decision). The backend reports the extractor as available on Windows; the adapter is tested only with fakes. | Before relying on L3 (any machine where L2 is too slow) |
| Left/right-hand convention | **L2 checked on Windows (2026-10-18):** HandLandmarker's label names the signer's own hand on unmirrored frames (it was being swapped wrongly) and flickers under fast motion. Fixed by matching hands to the pose wrists. **L1 Holistic and L3: still to check** in the final run, including whether the pose's own left/right is anatomical. | P3 final Windows run, step 3 |
| Holistic model URL uses `/latest/`, not a fixed version | Mitigated by sha256 pinning on first fetch (trust on first use) | P3 Windows step 1 |
| Backend RSS in mock mode | **Measured on the M1 (2026-10-18): about 46 MB** for the Python process, plus about 24 MB for the `uv run` wrapper | Re-measure in P3 with the WS endpoint |
| Vietnamese data-protection applicability | Not reviewed | B2 |

## 3. Architecture review log

**Round 1 (rev2), 34 findings, all resolved in the docs.** Summary of the critical and high findings:

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | Critical | Phrases split by a per-sign segmenter | Message units + utterance segmenter + variable length (ADR-005) |
| 2 | Critical | No rejection of real out-of-vocabulary signs | Distractor collection + rejection classes + open-set FAR metric |
| 3 | Critical | Data track scheduled too late | Parallel Track B with gate B2 (ROADMAP) |
| 4 | High | Withdrawal impossible (no identity link) | Encrypted identity register (DATASET §3) |
| 5 | High | Too few signers for credible evaluation | ≥12 signers, ≥3 test signers, CIs |
| 6 | High | TS/Python feature-spec drift | Server-published `feature_spec` (ADR-009) |
| 7 | High | P3 needed a recorder that only arrived in P4 | Minimal recorder moved to P3 |
| 8 | High | Failure-mode table missing | ARCHITECTURE §9 |
| 9 | High | Always-on microphone VAD | Push-to-talk only |
| 10 | High | "Classroom" framing vs adults-only scope | Explicit adults-only statement |
| 11 | High | Vocabulary discoverability and literacy | Sign guide, icons |
| 12 | High | No go/no-go gates | G5 and G7 |

Medium and low findings: P1 overengineering trimmed; no CUDA torch; no symlinks; no-model degraded mode; latency measured from rest to rendered; worker, visibility, and hybrid-GPU handling; memory budget; fp16 caution; WS contract details; extractor versioning; VSL-fluent annotation; bystanders; candidate policy; teacher large display; npm lockfile risk; no free-text feedback; no pickle; synthetic fixtures; Windows `~` paths; mirroring per item.

**Round 2 (rev3, owner-directed):**

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 35 | High | Combined launcher; no low-RAM UI mode | Separate scripts, no `dev.py`, dev-only mock mode, replay source (ADR-016) |
| 36 | High | No server-side fallback if browser fps is low | Ladder L1/L2/L3 with confirmation (ADR-002) |
| 37 | High | Risk of exhausting GTX 1650 VRAM | CPU-only MVP inference, backend TTS deferred, ResourceManager swap rule (ADR-015, ADR-010) |

**Approval addendum (2026-10-18):** the M1 runs no models and no real inference. As a result, **research data lives on the Windows laptop**, which changes rev2's "data stays on the Mac" assumption, and every measurement step is tagged [WIN].

## 4. Open questions

| Question | Owner | Must be resolved by |
|---|---|---|
| How does a signer confirm with busy hands (button, space bar, pedal)? | Deaf co-design participants | P6 |
| Does every vocabulary item have a usable local voice pronunciation? | Developer + reviewers | P2 |
| Is BitLocker or Device Encryption available on the Windows laptop's edition? | Developer | B2 |
| Which consent wording and VSL video format does the community partner prefer? | Community partner | B2 |
| Is the Web Worker MediaPipe path stable in Chrome on Windows? | Developer | P3 |
| Target operating point (precision vs coverage) | Owner | G5 |

## 5. Phase 3 findings (2026-10-18)

- **uvicorn had no WebSocket implementation.** FastAPI's `TestClient` does not need one, so pytest passed while the real server answered the upgrade with 404. The full-stack Playwright test caught it. `websockets` is now an explicit dependency, with a regression test.
- **Segmenter pre-roll at low fps.** At 10 fps the first moving frames were cut off. Fixed by measuring the pre-roll from the candidate start, with tests at 10/15/30 fps.
- **L3 fps is the send rate**, not the server's processing rate. If the server falls behind, frames queue on the socket (sends are skipped above 512 KB buffered). Watch prediction latency during the Windows L3 benchmark.
- **"Unable to open zip archive" on Windows (first P3 run).** Vite's SPA fallback answered missing `/mediapipe/*` files with `index.html` (HTTP 200), and MediaPipe tried to open it as a `.task` zip. Fixed in four places:
  - a Vite plugin returns 404 for missing MediaPipe assets in dev and preview;
  - the browser checks the WASM files and the zip signature of each model before creating any task;
  - models are passed to MediaPipe as buffers (`modelAssetBuffer`), so the worker resolves no model paths;
  - the UI names the missing files and the command to run.

  `fetch_mediapipe_assets.py` also refuses to save a non-zip download. Upstream URLs were checked with HEAD requests on 2026-10-18 (holistic 13.7 MB, hand 7.8 MB, pose lite 5.8 MB).
- **`fetch_mediapipe_assets.py` failed on Windows with WinError 32** (second Windows run). There were two bugs:
  1. **Wrong zip check (mine).** Both the script and the browser required `.task` files to start with `PK`. MediaPipe's real files start with 2–4 zero bytes before the zip header; this was checked with HTTP Range requests on 2026-10-18 (first bytes `00000000504b0304` / `0000504b0304`, last 22 bytes `504b0506…`). Valid models were rejected. Both now detect the end-of-central-directory record (`zipfile.is_zipfile` in Python, an EOCD scan in the browser).
  2. **Deleting an open file.** The rejection path called `unlink()` inside the `with` block that still held the file open. macOS allows that; Windows refuses. Removing and renaming now happen only after every handle is closed, with a short retry (5 attempts, growing delay) for antivirus locks on new files.

  Regression tests simulate Windows' "cannot delete an open file" rule, and fail against the old script.
- **Windows run 1 (L2, mock, GTX 1650).**
  - Results: 20.7 fps; total latency p50 784 ms / p95 1376 ms; inference 1.4 ms; source `L2 main/GPU`, so **the Web Worker path fell back to the main thread**. The worker's error text is now logged to the console as "MediaPipe worker unavailable…"; capture it in the final run.
  - Handedness was flipped, and fast motion flickered. Fixed with pose-wrist matching (see the P3 decision note in ROADMAP).
  - Frames are now sent one by one, and the latency criterion changed to processing ≤ 500 ms p95.
- **Windows run 2 (L1 worker/GPU 17.0 fps; L2 main/GPU 25.5 fps; L3 unavailable).** Handedness is now correct, with no flicker. The latency numbers were **not trustworthy** because of two measurement bugs, now fixed:
  - **Separate source clock.** Camera sources used their own clock, started after model loading, so the start-up time was added to every sample. This is why L2's "processing" sat at a flat ~700 ms. All sources now use the session clock.
  - **"Still" closes.** These reported a 0 ms wait and kept the motionless frames in the unit. With a laptop webcam, hands resting on the desk sit above the rest line, so most signs end by "still" after 1.5 s. Units are now cut at the last moving frame, the wait is measured, and close reasons are counted.

  Also changed:
  - The L3 error now shows the server's reason, and the backend warns at startup when the `server-extraction` extra is missing. `uv run`/`uv sync` without `--extra` removes it.
  - The fallback window went from 5 s to 15 s: L1 was auto-switched to L2 after a short dip.

  **Known limitation:** L2 (Hand + Pose, two tasks) cannot run in the module Web Worker. tasks-vision 1.0.1 fails with "ModuleFactory not set" when creating the second task, so L2 uses the main thread. L1 (one Holistic task) runs in the worker. Not fixed: no way to test it on the Mac, and L2 still reached 25.5 fps on the main thread.
  **Open UX question for P4/P6:** should hands resting on a desk count as "rest"? This decides whether signs end after 0.6 s or 1.5 s. Signer sessions decide it, together with the pause tolerance.
- **Windows run 3 / Phase 3 closed.**
  - With measurement fixed, **L2 meets the criterion: 22.8 fps, processing p95 146 ms**. L1 fell to 12.4 fps.
  - **L3 was never executed** (owner accepted). The run labelled L3 showed `L1 worker/GPU`, because the level only applies after stopping and restarting.
  - **Segmentation is the next real risk:** 26/31 signs ended at the 4 s maximum. Even the synthetic HOLD takes show jitter (≈0.4 shoulder widths/s at ±0.002 noise) above the current 0.15 "still" threshold, so the threshold is unrealistic for tracker data.
  - Bug fixed alongside: wrist speed compared the hands without labels, so one hand vanishing while the other appeared counted as fast motion and could start a false unit.
  - Next: tune the thresholds from the owner's recordings (P4 first task).
