# AI/ML Strategy

> **Execution rule.** Nothing in this document runs on the M1 development Mac. Training, model downloads, real inference, and benchmarks run **only on the Windows laptop**. The Mac runs unit tests on synthetic data and mock mode.

## 1. Problem framing

- **Task:** classify one **message unit** at a time, out of a closed vocabulary of 20–50 items, plus rejection. A message unit is either a single lexical sign or a short fixed phrase of up to 3 s, recorded and classified as a whole. Experts tag each item `unit_type: sign | phrase`. The MVP prefers single signs.
- **Interaction:** *intentional message mode*. The signer starts recognition, signs one unit, and returns their hands to rest. The system does **not** interpret continuous signing.
- **Not in scope:** continuous sign language recognition, translation, grammar, fingerspelling.

## 2. Pipeline and limitations

| # | Step | Approach | Limitations |
|---|---|---|---|
| 1 | Frame acquisition | Browser `requestVideoFrameCallback`, target ≥15 fps | Low fps undersamples fast handshape changes. Motion blur comes from exposure and lighting, not from processing speed. |
| 2 | Landmarks | MediaPipe Holistic: pose 33×4, hands 2×21×3, face subset of about 40×3, using unmirrored coordinates and presence masks. Fallback ladder L1/L2/L3 (ARCHITECTURE §5). | Occlusion, crossed hands, handedness swaps, low light, a wrong person tracked |
| 3 | Buffering | Ring buffer of about 5 s per session | Bounded memory; long phrases get truncated at 4 s |
| 4 | Normalisation | Centre on the shoulder midpoint, scale by shoulder width, correct for aspect ratio (`image_width/height`), wrist-relative hand coordinates plus global hand position, velocities, masked missing values | Fails if the shoulders aren't visible. Mirroring is allowed only for items experts approve (`mirroring_ok`). |
| 5 | **Utterance segmentation** | State machine. Start when a hand enters the signing space and motion stays above a threshold for N frames. Tolerate pauses of about 600 ms inside a unit. End when hands return to rest or motion stays low for M frames. Minimum and maximum duration (max 4 s). Manual capture mode is the fallback. | Signers may not return to a clear rest pose. This needs UX validation with Deaf users. |
| 6 | Classification | Variable-length sequence with masking (no fixed T=32) | Small data, signer variation |
| 7 | Calibration | Temperature scaling fitted on validation signers | Can drift when new signers or conditions appear |
| 8 | Stabilisation | **One decision per utterance**, never per frame | — |
| 9 | Duplicate suppression | The same gloss within a cooldown of about 1.5 s (tuned) is merged | Can suppress a genuine repeat |
| 10 | **Unknown rejection** | `__background__` class (non-sign motion) + `__distractor__` class (real out-of-vocabulary VSL signs) + calibrated threshold + top-1/top-2 margin | Open-set recognition is never perfect, so confirmation stays mandatory |
| 11 | Phrase mapping | 1:1 lookup `gloss_id → text_vi + icon` from the vocabulary YAML | No sentence generation |
| 12 | Confirmation | Required before the transcript and before speech | Adds a step for the signer |
| 13 | TTS | Browser local `vi-VN` voice (ADR-010) | Voice availability depends on the OS |

## 3. Candidate approaches

| Approach | Pros | Cons | Role |
|---|---|---|---|
| **Template / kNN with DTW** on normalised landmarks | Works with a handful of samples, no training, easy to interpret | Slow as the number of templates grows; weak across signers | P3 walking skeleton (developer's own signs, Windows only); sanity baseline in P5 |
| **GRU** (2 × 128, bidirectional, masked) | Robust with small data, small size, exports to ONNX easily | Sequential, so inference is a bit slower | **Recommended baseline** |
| **1D-TCN** (dilated, masked pooling) | Parallel, fast, strong on short sequences | Receptive field needs tuning | Compared with the GRU at G5 |
| Transformer encoder on landmarks | Strong in landmark-based isolated sign recognition benchmarks | Needs more data | Later phase |
| Video CNN (I3D, Video-Swin) | Uses appearance detail | Needs lots of data and a GPU, and keeps raw video | Rejected (ADR-004) |

All MVP models are expected to be a few MB or less and to run on CPU through onnxruntime. This is **unverified** until P5. The template model is stored as `templates.npz` (`allow_pickle=False`) plus `labels.json`. Pickle is never used.

## 4. Evaluation protocol

- **Splits:** grouped by `signer_id`. A fixed **held-out test set of ≥3 signers** is used once per release. Model selection uses signer-grouped k-fold or leave-one-signer-out on the remaining signers. Distractor sign *identities* are also split, so test distractors are unseen. CI tests for leakage.
- **Realistic subset:** test recordings made in classroom-like conditions, with people in the background, uneven light, and different distances.
- **Metrics:**
  - per-class precision, recall, and F1; macro-F1; top-3 accuracy; confusion matrix;
  - **open-set:** false-accept rate (FAR) on unseen distractors and non-sign motion, and false-reject rate on known signs;
  - **calibration:** expected calibration error (ECE) and reliability diagrams;
  - **per-signer** and **per-condition** breakdowns (lighting, background, camera, handedness, region where consented), with bootstrap 95% confidence intervals;
  - **system:** browser fps (p50/p95), latency from *hands at rest* to *prediction rendered* (p50/p95, split into hysteresis, transport, and inference), and process RSS.
- **Operating point:** thresholds are chosen on validation data to favour **precision and low FAR**, because a wrong word spoken aloud costs more than "please sign again".
- **No accuracy is promised.** At gate **G5** the owner sees the baseline numbers and either approves targets or picks a pivot: a smaller vocabulary, more data, different features, or stopping.

## 5. Benchmark method (Windows laptop)

1. Use the production build of the web app, not the Vite dev server. Chrome is set to "High performance" GPU, and the in-app diagnostics show the WebGL renderer string to confirm which GPU is in use.
2. Run a 5-minute scripted session at each ladder level (L1, L2, L3). Log fps per second and latency per prediction.
3. Record backend RSS (`doctor.py`) and Task Manager GPU memory.
4. Save a Markdown report to `DATA_ROOT/reports/benchmarks/` (outside the repo). A summary table with no personal data goes into the PR.

**P3 thresholds (approved):** ≥15 fps; ≤1.0 s p95 from rest to rendered.

## 6. Hardware policy

| Workload | M1 Mac (8 GB) | Windows (GTX 1650 4 GB, 16 GB RAM) |
|---|---|---|
| Unit tests, mock mode, replay UI | ✅ | ✅ |
| MediaPipe in the browser | ❌ (not on the dev Mac, by rule) | ✅ |
| Sign model inference | ❌ | ✅ CPU onnxruntime |
| Training | ❌ | ✅ CPU torch, small models; never while the demo runs |
| STT (P7) | ❌ | ✅ CPU int8 by default. GPU is a post-G7 opt-in: `int8` / `int8_float32` first, fp16 experimental (GTX 16xx fp16 problems are reported in some stacks; unverified for CTranslate2). |
| Backend TTS | Not in the MVP | Not in the MVP |

## 7. Extractor versioning

- `@mediapipe/tasks-vision` is pinned to an exact version, and the model files are pinned by sha256.
- Every sample records `extractor_version` and `extractor_backend` (`browser-l1`, `browser-l2`, `server-l3`).
- An extractor upgrade requires a parity check against stored landmarks. Re-extraction is possible only for samples whose contributors consented to encrypted raw-video retention.
- **L3 parity (P3):** run both JS and Python extractors on the developer's own clips (on Windows, never committed) and compare per-landmark error against defined tolerances. If parity fails, L3 stays "experimental" until training data includes L3-extracted samples.

## 8. Artifacts

`model-artifacts/sign/<model_id>/`:
- `model.onnx` or `templates.npz`
- `labels.json`
- `calibration.json` (temperature, τ, margin, floor)
- `model_card.json`, containing:
  - `model_id`, `created_at`, `feature_spec_version`, `extractor_version`, `vocabulary_version`;
  - `dataset_version` and manifest sha256;
  - the metrics summary and the operating point;
  - the **distribution scope** (public or private, see the dataset doc);
  - the sha256 of every file.

The backend verifies all of these before loading. Models are selected with `VSL_SIGN_MODEL_ID`; there are no symlinks.
