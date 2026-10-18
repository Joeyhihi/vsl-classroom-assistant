# Cross-Platform Setup (macOS ↔ Windows)

| Machine | Role | Allowed |
|---|---|---|
| MacBook Air M1, 8 GB | Primary development | Code, build, **unit tests, mock mode, replay mode only**. No model downloads, no real inference. |
| Windows laptop (i5-11400H, 16 GB, GTX 1650 4 GB) | Testing and the real AI pipeline | Everything, including model assets, benchmarks, training, and data collection |

Nothing that depends on the machine is committed. Virtual environments, `node_modules`, and model files are rebuilt on each machine.

## 1. One-time installs

| Tool | macOS | Windows |
|---|---|---|
| Git | Xcode CLT or Homebrew (`brew install git`) | [Git for Windows](https://git-scm.com/download/win), or **GitHub Desktop** (includes Git) |
| uv | `brew install uv` or the official installer | PowerShell: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| Node 24 LTS | `nvm install 24` (reads `.nvmrc`) | Official Node 24 LTS installer from nodejs.org, or `fnm` |
| Chrome or Edge | ✅ | ✅. Set Chrome to the **"High performance" GPU** in *Settings → System → Display → Graphics*, so MediaPipe uses the GTX 1650 rather than the Intel UHD graphics. |

uv installs Python 3.12 automatically, based on `.python-version`. You don't need to install Python yourself.

## 2. Everyday commands (identical on both OSes)

```bash
uv run python scripts/bootstrap.py     # first time and after pulling dependency changes
uv run python scripts/run_backend.py   # terminal 1 — backend only (127.0.0.1:8000)
uv run python scripts/run_web.py       # terminal 2 — frontend only (http://localhost:5173)
uv run python scripts/check.py         # all quality gates before a PR
uv run python scripts/doctor.py        # environment diagnostics
```

- **There is no combined launcher (ADR-016).** Always use two terminals, so each side can run on its own and memory use is visible.
- `run_backend.py --mock` forces mock mode, with no ML libraries imported.
- `run_web.py --preview` serves the built app, which uses less RAM than the Vite dev server.
- On Windows, use **PowerShell** or **Windows Terminal**. Every script is Python, so no bash and no execution-policy changes are needed.

### M1 working modes (lowest RAM first)

1. `VITE_LANDMARK_SOURCE=replay` with a **mock** backend: UI work with no camera and no MediaPipe. **This is the default on the Mac.**
2. Mock backend with no frontend: API and WS work via tests.

Camera + MediaPipe and any real model run **only on Windows**. Close unused IDE windows; never train on the Mac.

### Windows-only (from P3)

```powershell
uv run python scripts/bootstrap.py --with-models      # fetch pinned MediaPipe assets (sha256-checked)
uv sync --extra server-extraction                     # optional L3 server-side MediaPipe
```

## 3. Git and GitHub workflow

1. On the Mac, create a feature branch (e.g. `phase-1-foundation`).
2. Run `scripts/check.py`.
3. Push and open a PR.
4. CI runs on **Ubuntu and Windows** (a macOS workflow is available on demand).
5. On Windows, use **GitHub Desktop**: *Fetch origin → switch to the branch → Pull*. Then run `bootstrap.py` and the [smoke checklist](#windows-smoke-checklist).
6. The owner reviews, and the branch is merged into `main`. Nothing is committed without the owner's approval.

## 4. Dependency management

| Area | Tool | Lockfile | Notes |
|---|---|---|---|
| Python | **uv workspace** (root `pyproject.toml`) | `uv.lock` (universal: one lock for macOS and Windows) | Python 3.12 (ADR-008). P1 member: `services/ai-backend`. `packages/vsl-features` joins in P3 and `ml` in P5. |
| JS | **npm** | `apps/web/package-lock.json` | `npm ci` in CI and bootstrap |
| ML | CPU torch only (P5, Windows) | in `uv.lock` | No CUDA torch. Models are small. |
| Runtime inference | `onnxruntime` CPU (P3/P5) | in `uv.lock` | No GPU packages in the MVP (ADR-015) |
| STT (P7) | `faster-whisper`, CPU int8 | in `uv.lock` | GPU is a post-G7 opt-in: needs CUDA 12 + cuDNN 9 libraries on PATH (the faster-whisper README points to a prebuilt bundle for Windows) |
| L3 extractor | `mediapipe` (optional extra) | in `uv.lock` | `py3-none` wheels for macOS arm64 and win_amd64 (checked in P1) |

**Known risk:** npm has a history of lockfiles created on one OS missing optional native packages for another (for example Rollup's platform binaries). The Windows CI job runs `npm ci && npm run build` on every PR to catch this. If it happens, regenerate the lockfile with the current npm and verify again on both OSes.

## 5. Environment variables

`.env.example` (copied to `.env` by bootstrap) documents every variable:

| Variable | Default | Purpose |
|---|---|---|
| `VSL_ENV` | `dev` | `dev` or `prod`. Mock mode requires `dev`. |
| `VSL_HOST` / `VSL_PORT` | `127.0.0.1` / `8000` | Backend bind address (loopback only) |
| `VSL_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | HTTP and WS Origin allow-list |
| `VSL_MODEL_MODE` | `mock` | `mock`, `template`, or `onnx` |
| `VSL_MOCK_SCRIPT` | `cycle` | `cycle` or `timer` |
| `VSL_SIGN_MODEL_ID` | (empty) | Resolves to `model-artifacts/sign/<id>/` (no symlinks) |
| `VSL_DATA_ROOT` | (empty → platform user-data dir) | Research data, feedback, reports. Always outside the repo. |
| `VSL_SERVER_EXTRACTION_ENABLED` | `false` | Allows L3 |
| `VSL_STT_ENABLED` | `false` | P7 |
| `VSL_STT_MODEL` / `VSL_STT_DEVICE` / `VSL_STT_COMPUTE_TYPE` | `small` / `cpu` / `int8` | P7 |
| `VSL_HEAVY_MODEL_IDLE_UNLOAD_S` | `300` | ResourceManager |
| `VSL_MIN_FREE_RAM_MB` / `VSL_MIN_FREE_VRAM_MB` | `1500` / `1500` | Guards (to re-tune after P3 and P7) |
| `VSL_MAX_SESSION_S` | `7200` | WS session cap |
| `VSL_HOLISTIC_MODEL_PATH` | `apps/web/public/mediapipe/holistic_landmarker.task` | Model for L3 server extraction |
| `VSL_COOLDOWN_MS` | `1500` | Duplicate-prediction suppression window |
| `VSL_LOG_LEVEL` | `INFO` | Logging |
| `VITE_API_BASE` | `/api/v1` | Proxied to the backend by Vite in dev |
| `VITE_LANDMARK_SOURCE` | `replay` | `camera` or `replay`. Must be `camera` on Windows for real tests. |
| `VITE_MIN_FPS` | `15` | Ladder threshold |
| `VITE_ENABLE_RECORDER` | `false` | Data-collection view |

## 6. GPU and memory policy (ADR-015)

- **M1:** no GPU or ML workloads at all, by rule.
- **GTX 1650 (4 GB):** in the MVP it is used **only by Chrome** (MediaPipe WebGL). All Python inference runs on CPU, and there is no backend TTS model. The figure of about 1.5 GB VRAM used by Windows and Chrome is an estimate, to be measured in P3 with Task Manager → GPU → Dedicated memory.
- **Post-G7 GPU STT (opt-in):** loads only if `nvidia-smi` reports free VRAM ≥ `VSL_MIN_FREE_VRAM_MB`. Any CUDA out-of-memory error makes it fall back to CPU int8. The ResourceManager swap rule keeps at most one heavy model resident.

## 7. Files never committed

The existing `.gitignore` plus the P1 additions exclude:
- environments and dependencies: `.venv`, `node_modules`, `dist`;
- secrets: `.env*` (except `.env.example`);
- models and media: `*.onnx *.pt *.ckpt *.npz *.task *.tflite *.mp4 *.mov *.webm *.wav`;
- data and artifacts: `model-artifacts/*`, `ml/datasets/*`, `apps/web/public/mediapipe/`;
- caches and reports: `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `coverage`, `playwright-report`, `test-results`, `*.log`;
- editor and OS files: `.idea`, `.vscode`, `.DS_Store`, `Thumbs.db`.

`scripts/guard_no_media.py` enforces this in CI.

## 8. Windows smoke checklist {#windows-smoke-checklist}

- [ ] `uv run python scripts/bootstrap.py` completes
- [ ] `uv run python scripts/check.py` passes
- [ ] `run_backend.py` starts; http://127.0.0.1:8000/api/v1/health returns `status: ok` (mock)
- [ ] `run_web.py` starts; http://localhost:5173 shows the app and the backend status as connected
- [ ] Stopping the backend shows the "Mất kết nối máy chủ" (lost connection to server) state in the UI
- [ ] Ctrl+C stops each process cleanly
- [ ] (P2+) In the app, open **Cài đặt → Chẩn đoán** and record the "Giọng tiếng Việt: N cục bộ, M trực tuyến" line and the voice names. If there are 0 local voices, install one (Settings → Time & language → Speech → Add voices → Vietnamese) and check again.
- [ ] (P2+) `npm run e2e` in `apps/web` passes (uses the installed Chrome)
- [ ] (P3+) fps and latency benchmark recorded

## 8a. Segmentation recordings (P4 first task) {#segmentation-recordings}

1. In `.env`, set `VITE_ENABLE_RECORDER=true` and `VITE_LANDMARK_SOURCE=camera`. Restart `run_web.py --preview`, set Settings → level to **L2**, and turn on the camera in Giao tiếp (communication).
2. In **Ghi mẫu** (record), record 5 takes each of: `REST_DESK`, `REST_LAP`, `REST_DOWN`, `HOLD` (hands raised and still), and three of your own signs (`DEV_01`–`DEV_03`, each rest → sign → rest).
3. **After each label, download, then click "Xoá các lượt" (clear takes) before typing the next ID.** All takes in a file get the ID typed at download time.
4. Files land in the browser's Downloads folder as `recording-<ID>.json`. They contain landmarks only, never video. Keep them outside the repo; on the Mac, put them in `~/vsl-data/recordings/p3-segmentation/`.
5. Analyse with `uv run python scripts/analyze_segmentation.py ~/vsl-data/recordings/p3-segmentation/`. The report covers wrist speed and height per take, what the segmenter does, and suggested thresholds. It prints no raw landmark values.

## 9. End-to-end tests (Playwright)

- `npm run e2e` in `apps/web`, also run by `scripts/check.py` (use `--skip-e2e` to skip).
- **Locally** it drives the installed **Google Chrome** (`channel: "chrome"`), so the 8 GB Mac needs no extra browser download. **CI** installs Playwright's Chromium. Override with `PW_CHANNEL`, e.g. `PW_CHANNEL=msedge` or `PW_CHANNEL=chromium` (the latter needs `npx playwright install chromium`).
- Tests use Chrome's synthetic fake camera (a test pattern, no real person), a mocked `/api/v1/health` (no backend needed) and a stubbed `speechSynthesis`, so they run without a webcam, microphone, backend or model.

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `uv` not found | Reopen the terminal after installing; run `uv --version` |
| Port 8000 or 5173 in use | Set `VSL_PORT` or run `run_web.py --port 5174` (and add that origin to `VSL_ALLOWED_ORIGINS`) |
| Vite fails on Windows with a missing `@rollup/rollup-win32-*` | See the npm risk above: delete `node_modules`, run `npm ci`, and regenerate the lockfile if needed |
| Backend refuses to start: "mock mode requires VSL_ENV=dev" | Set `VSL_ENV=dev` or choose another `VSL_MODEL_MODE` |
| Browser console: `StartGraph failed: UNKNOWN: Unable to open zip archive` | The MediaPipe model was missing, and older builds received Vite's `index.html` instead. Run `uv run python scripts/bootstrap.py --with-models --pin` (step 1 of §11) and reload. Since the fix, the app reports "Thiếu tệp MediaPipe" (MediaPipe files missing) with the file names, and `/mediapipe/*` returns 404 when a file is absent. Check that `apps/web/public/mediapipe/holistic_landmarker.task` exists (about 13.7 MB). |
| `fetch_mediapipe_assets.py`: `PermissionError: [WinError 32]` | Fixed: the script deleted a temp file while it was still open, after wrongly rejecting a valid model. Pull the latest `main` and rerun `bootstrap.py --with-models --pin`. If a `*.task.part` file was left behind in `apps/web/public/mediapipe/`, delete it. |
| L3: "Xử lý trên máy chủ không khả dụng" (server processing unavailable) | The panel's "Chi tiết" (details) line, the backend's startup warning, and `/api/v1/diagnostics` all give the reason. Usually the backend was started without `--extra server-extraction` (step 6), or `VSL_SERVER_EXTRACTION_ENABLED` is not `true`. |
| CRLF line-ending warnings | `.gitattributes` normalises them. Run `git add --renormalize .` once if needed. |

## 11. Phase 3 Windows test procedure {#phase-3-windows-test-procedure}

Everything below runs **only on the Windows laptop**. Steps 1–3 are setup; steps 4–7 produce the P3 exit measurements. Record results in the PR, using numbers only and no recordings.

1. **Assets (first time).** Run `uv run python scripts/bootstrap.py --with-models --pin`. This copies the tasks-vision WASM runtime and downloads the Holistic, Hand and Pose models into `apps/web/public/mediapipe/` (gitignored). On the first run it records their sha256 in `scripts/mediapipe_assets.json`. **Commit that file**; later runs (without `--pin`) verify against it.
2. **Camera mode.** In `.env`, set `VITE_LANDMARK_SOURCE=camera` and keep `VSL_MODEL_MODE=mock`. Start the backend and frontend, turn on the camera, and press "Bắt đầu nhận dạng" (start recognition).
   - Check: the landmark overlay follows you, and Settings → Hiệu năng (performance) shows the source detail (e.g. `L1 worker/GPU`). This is the **worker spike result**: `worker` means MediaPipe runs in the Web Worker; `main` means it fell back to the main thread.
3. **Handedness check** (at L1, L2 and L3). Raise only your **right** hand. In the overlay, your right **arm and hand** must be **orange** and the left green (torso blue). Then move the right hand fast: it must stay orange.
   - Hands are matched to the pose wrists, so if the arm is orange but the hand green (or the reverse), report it.
   - If both arm and hand are swapped, the pose's own left/right is inverted; report that too.
4. **L1 benchmark.** Run recognition for 5 minutes using the production build (`run_web.py --preview`), signing normally so predictions happen. From Settings → Hiệu năng (performance), record: fps; the three latency rows (processing, wait, total) as p50/p95; **how signs ended** (lowered / held still / too long); inference; source line; JS heap; backend RSS. Also record GPU memory from Task Manager. Targets: **≥15 fps** and **processing ≤ 500 ms p95**.
5. **L2 benchmark.** Settings → Mức xử lý hình ảnh (processing level) → L2, then repeat step 4.
6. **L3 benchmark.** Set `VSL_SERVER_EXTRACTION_ENABLED=true` in `.env`, then start the backend **with the extra**:
   ```powershell
   uv run --extra server-extraction python scripts/run_backend.py
   ```
   A plain `uv run` or `bootstrap.py` re-syncs the environment *without* optional packages, which removes MediaPipe again. The backend prints "L3 server extraction: available" or a warning with the reason. Then choose L3 and repeat step 4. (For L3, the fps shown is the rate frames are sent; check that predictions keep up.) If the backend reports `EXTRACTION_UNAVAILABLE`, `/api/v1/diagnostics` gives the reason. The Python HolisticLandmarker API is **unverified**, so report any import or attribute error verbatim.
7. **Template classifier on your own signs.**
   1. Set `VITE_ENABLE_RECORDER=true`.
   2. In Ghi mẫu (recorder), record 3–5 of **your own** signs, 3+ takes each, and download the files. Keep them outside the repo.
   3. Run `uv run python scripts/build_templates.py --model-id dev-01 path\to\recording-*.json`.
   4. Set `VSL_MODEL_MODE=template` and `VSL_SIGN_MODEL_ID=dev-01`, then restart.
   5. Sign each one a few times and note how often it's correct, how often it's "uncertain", and what happens when you sign something not in the set.

   This checks the pipeline only. It is not a model.

If no level reaches 15 fps, the laptop is documented as manual-text-only and the owner decides whether to continue (ROADMAP P3).
