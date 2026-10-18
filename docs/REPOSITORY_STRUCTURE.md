# Repository Structure

This is the target layout. A directory or file is created **only in the phase where it becomes necessary**, so there are no empty placeholders. The existing layout (`apps/web`, `services/ai-backend`, `ml`, `docs`, `model-artifacts/`) is kept. `packages/vsl-features` was added and approved in Phase 0.

Dependency direction:

```
apps/web  ──(HTTP/WS contract)──▶  vsl_backend  ──▶  vsl_features
                                                   ▲
ml (vsl_ml) ───────────────────────────────────────┘
```

`vsl_backend` and `vsl_features` must never import torch.

## Tree

```
vsl-classroom-assistant/
├── README.md
├── .gitignore  .gitattributes  .editorconfig
├── .python-version  .nvmrc  .env.example
├── pyproject.toml  uv.lock
├── .github/
│   ├── workflows/ci.yml
│   ├── workflows/macos-manual.yml
│   └── pull_request_template.md
├── scripts/
│   ├── bootstrap.py  run_backend.py  run_web.py
│   ├── check.py  doctor.py  guard_no_media.py
│   ├── gen_contracts.py            (P3)
│   └── fetch_mediapipe_assets.py   (P3; Windows/with-models only)
├── apps/web/
│   ├── package.json  package-lock.json  vite.config.ts  tsconfig*.json  eslint.config.js  index.html
│   ├── playwright.config.ts  e2e/                       (P2)
│   ├── public/mediapipe/                                (P3, gitignored)
│   └── src/
│       ├── main.tsx  App.tsx
│       ├── views/  components/  features/  api/  i18n/  styles/  test/
├── services/ai-backend/
│   ├── pyproject.toml
│   ├── src/vsl_backend/
│   │   ├── main.py  config.py  logging_config.py  errors.py  security.py
│   │   ├── api/v1/  schemas/  recognition/
│   │   ├── extraction/  inference/  speech/              (P3+)
│   │   ├── feedback_store.py (P6)  static.py (P9)
│   └── tests/
├── packages/vsl-features/                              (P3)
├── ml/                                                 (P4–P5)
├── model-artifacts/README.md
└── docs/
```

## Entry-by-entry

### Root

| Path | Responsibility | Depended on by | Phase |
|---|---|---|---|
| `README.md` | Summary, status, quickstart, links to docs | everyone | P0 |
| `.gitignore` | Keeps venvs, node_modules, secrets, media, models, and data out of git | CI guard | existing, extended in P1 |
| `.gitattributes` | Line-ending normalisation (LF; CRLF for `*.ps1`) | Windows checkout | P1 |
| `.editorconfig` | Consistent indentation and charset across editors | developers | P1 |
| `.python-version` | `3.12`, read by uv | uv | P1 |
| `.nvmrc` | `24`, the Node LTS version | nvm/fnm, CI | P1 |
| `.env.example` | Every environment variable, documented, with no secrets | `config.py`, Vite | P1 |
| `pyproject.toml` | uv workspace root, ruff/mypy/pytest configuration, dev dependencies | all Python members | P1 |
| `uv.lock` | Universal lockfile for macOS and Windows | uv, CI | P1 |

### `.github/`

| Path | Responsibility | Phase |
|---|---|---|
| `workflows/ci.yml` | Lint, typecheck, tests, build, `guard_no_media`, gitleaks, on Ubuntu and Windows | P1 |
| `workflows/macos-manual.yml` | Same checks on macOS, triggered manually only (`workflow_dispatch`) | P1 |
| `pull_request_template.md` | Quality and privacy checklist | P1 |

### `scripts/` (cross-platform Python, run with `uv run python scripts/<name>.py`)

| Script | Responsibility | Phase |
|---|---|---|
| `bootstrap.py` | `uv sync`, `npm ci`, tool and version checks, creates `.env` from the example. Never downloads models unless given `--with-models` (P3+, Windows only). | P1 |
| `run_backend.py` | Starts **only** the backend (uvicorn on 127.0.0.1). `--mock` forces mock mode. | P1 |
| `run_web.py` | Starts **only** the frontend (Vite dev server). `--preview` serves the built app instead. | P1 |
| `check.py` | Runs every local quality gate in order and reports a summary | P1 |
| `doctor.py` | Prints OS, Python, Node, npm, uv, memory, and optional GPU details | P1 |
| `guard_no_media.py` | Fails if tracked files include media, model, or dataset files, or anything over the size limit | P1 |
| `gen_contracts.py` | Pydantic → JSON Schema → TypeScript (single pipeline) | P3 |
| `_common.py` | Shared stdlib helpers for the scripts (tool lookup, subprocess) | P1 |
| `fetch_mediapipe_assets.py` | Downloads pinned MediaPipe WASM and model files with sha256 checks. **Not run on the M1.** | P3 |

There is deliberately no combined launcher. The frontend and backend always run in separate terminals (ADR-016).

### `apps/web/`

| Path | Responsibility | Phase |
|---|---|---|
| `src/main.tsx`, `App.tsx` | Entry point; view state (communicate, settings, privacy, guide, record) with no router | P1 shell, P2 |
| `src/views/` | `CommunicationView`, `SettingsView`, `PrivacyView` (P2); `RecorderView` (P3 minimal, P4 full); `SignGuideView`, `LargeDisplayView` (P6) | P2+ |
| `src/components/` | `camera/`, `recognition/`, `transcript/`, `compose/`, `speech/`, `system/` (banners, live region), `ui/` (Button, Dialog, Toggle, Badge) | P2+ |
| `src/features/` | Hooks and logic: `health/` (P1, backend status polling), `camera/`, `landmarks/`, `recognition/`, `transcript/`, `tts/`, `settings/`, `recorder/` (P3), `stt/` (P7) | P2+ |
| `src/api/` | `http.ts` (P1), `ws.ts` (P3), `types.ts` (hand-written P1 health type), `generated/contracts.d.ts` (P3) | P1+ |
| `src/i18n/vi.ts` | All UI strings and error-code messages, in Vietnamese | P1 |
| `src/styles/` | `tokens.css` (colours, sizes, focus ring), `global.css` | P1 |
| `src/test/` | Vitest setup and synthetic fixtures | P1 |
| `e2e/` | Playwright: permission denied, manual text, replay recognition, no-egress | P2–P3 |
| `public/mediapipe/` | Self-hosted MediaPipe assets (gitignored) | P3 |

### `services/ai-backend/`

| Path | Responsibility | Phase |
|---|---|---|
| `src/vsl_backend/main.py` | `create_app()`, lifespan, routers, middleware | P1 |
| `config.py` | `Settings` (pydantic-settings); mock-mode guard; `DATA_ROOT` resolution | P1 |
| `logging_config.py` | Structured logging; redaction policy | P1 |
| `errors.py` | `AppError` hierarchy, error-envelope handlers, request IDs | P1 |
| `security.py` | Origin allow-list middleware, security headers (CSP), body-size limit | P1 |
| `api/v1/health.py` | `GET /api/v1/health` | P1 |
| `api/v1/{vocabulary,models,recognition_ws}.py` | Vocabulary, model info, the WS endpoint | P3 |
| `api/v1/feedback.py`, `api/v1/stt.py` | Feedback (P6), STT (P7) | P6–P7 |
| `schemas/` | Pydantic models, the single source of the contract | P1+ |
| `recognition/classifiers.py` | `Classifier` protocol; `MockClassifier` (P1); `TemplateClassifier` (P3); `OnnxClassifier` (P5) | P1+ |
| `recognition/session.py`, `pipeline.py` | Per-connection session and orchestration | P3 |
| `extraction/server_extractor.py` | L3 server-side MediaPipe (optional extra) | P3 spike |
| `inference/model_registry.py`, `resource_manager.py` | Artifact checks; heavy-model policy | P3 / P6–P7 |
| `speech/stt_engine.py`, `audio_validation.py` | faster-whisper wrapper, WAV validation | P7 |
| `feedback_store.py` | Append and delete local JSONL | P6 |
| `static.py` | Serves the built SPA on the same origin | P9 |
| `tests/` | API, security, config, classifier, WS, registry tests; `contract_examples/` holds JSON examples validated by **both** Pydantic and the frontend type guards | P1+ |

There is no backend TTS module in the MVP (ADR-010).

### `packages/vsl-features/` (P3)

| Module | Responsibility |
|---|---|
| `spec.py` | `FeatureSpec` (version, landmark subsets, exact shapes, face indices), served to the client |
| `frames.py` | Frame validation, presence masks |
| `normalize.py` | Shoulder-centred, shoulder-width scaling, aspect-ratio correction, wrist-relative hands, mirroring |
| `features.py` | Velocities, distances, masking |
| `buffer.py` | Bounded ring buffer |
| `segmentation.py` | Utterance segmenter state machine |
| `decoding.py` | Temperature scaling, threshold, margin, cooldown |
| `vocabulary.py` | Loading and validating the vocabulary YAML |

### `ml/` (P4–P5)

| Path | Responsibility |
|---|---|
| `vocabulary/vocabulary.v1.yaml` | The validated vocabulary. Uses reviewer **role IDs**, never names. |
| `metadata/manifest.schema.json`, `manifest.example.jsonl` | Manifest schema plus a **synthetic** example |
| `configs/` | Model and training configuration (`template`, `gru`, `tcn`) |
| `datasets/README.md` | Points to `DATA_ROOT`. Real data never lives in the repo. |
| `src/vsl_ml/` | `data/`, `models/`, `train.py`, `calibrate.py`, `evaluate.py`, `export.py`, `parity.py`, `synth.py`, `reports/` |
| `tests/` | Signer and distractor leakage, schema, synthetic train smoke test, export parity |

### `model-artifacts/`

`model-artifacts/sign/<model_id>/{model.onnx | templates.npz, model_card.json, labels.json, calibration.json}`. Everything except `README.md` is gitignored. See [DATASET_AND_ANNOTATION.md](DATASET_AND_ANNOTATION.md#model-artifact-policy).

### `docs/`

Fifteen planning documents. They are updated in the same PR as the code they describe.
