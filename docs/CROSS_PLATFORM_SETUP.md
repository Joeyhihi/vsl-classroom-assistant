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
- [ ] (P2+) Local vi-VN voice availability recorded; (P3+) fps and latency benchmark recorded

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `uv` not found | Reopen the terminal after installing; run `uv --version` |
| Port 8000 or 5173 in use | Set `VSL_PORT` or run `run_web.py --port 5174` (and add that origin to `VSL_ALLOWED_ORIGINS`) |
| Vite fails on Windows with a missing `@rollup/rollup-win32-*` | See the npm risk above: delete `node_modules`, run `npm ci`, and regenerate the lockfile if needed |
| Backend refuses to start: "mock mode requires VSL_ENV=dev" | Set `VSL_ENV=dev` or choose another `VSL_MODEL_MODE` |
| CRLF line-ending warnings | `.gitattributes` normalises them. Run `git add --renormalize .` once if needed. |
