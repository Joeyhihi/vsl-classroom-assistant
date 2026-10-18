# Testing Strategy

**Rules:**
- **All automated tests run without a webcam, GPU, microphone, or ML model.**
- Fixtures are **synthetic only** (public repo).
- Tests that need real models or hardware are marked `@pytest.mark.windows_hw` and are skipped unless `VSL_RUN_HW_TESTS=1`. They are never run on the M1.

## Test layers

| Layer | Tools | Covers | Phase |
|---|---|---|---|
| Backend unit + API | pytest, FastAPI `TestClient` | health schema; error envelope; Origin allow-list; security headers; config guards (mock outside dev is refused); mock classifier determinism | P1 |
| Contract | pytest + Vitest | P1: health JSON example ↔ Pydantic ↔ hand-written TS type. P3+: generated TS is up to date. | P1/P3 |
| Frontend unit/component | Vitest, React Testing Library, vitest-axe | App shell, health status display, error mapping, a11y | P1 |
| Frontend E2E | Playwright (Chromium, fake media device) | permission denied, manual text → transcript, backend down, replay recognition, **no network egress**, CSP present | P2–P3 |
| WS | pytest `TestClient.websocket_connect` | lifecycle, close codes, validation, dropped frames, rate caps, heartbeat, binary-vs-JSON mode rules | P3 |
| Feature library | pytest + property tests | normalisation invariances (translation, scale), mirroring, segmenter on synthetic traces (including pauses inside a phrase), decoding and cooldown | P3 |
| ML | pytest | signer and distractor leakage, manifest schema, synthetic one-epoch train, PyTorch ↔ ONNX parity | P5 (Windows for real data) |
| Resource policy | pytest with fake engines and a fake memory probe | lazy load, idle unload, RAM and VRAM guard refusal, swap rule, OOM → CPU fallback | P6–P7 |
| Model evaluation | `vsl_ml.evaluate` | per-signer metrics, confusion matrix, open-set FAR, calibration error, CIs | P5 (Windows) |
| Performance | in-app diagnostics + `doctor.py` | fps, latency from rest to rendered, RSS, VRAM | P3, P7 (Windows) |
| Privacy | CI scripts + tests | `guard_no_media`, gitleaks, log redaction, egress test | P1+ |
| Cross-platform smoke | CI matrix + manual checklist | [Windows checklist](CROSS_PLATFORM_SETUP.md#windows-smoke-checklist) | every phase |
| Accessibility | vitest-axe, Playwright + axe, manual | WCAG 2.2 AA; Deaf user sessions | P1+, P8 |

## Failure-mode coverage

Every row in [ARCHITECTURE.md § Failure modes](ARCHITECTURE.md#failure-modes) names its test. Any new failure mode needs a test reference before it is merged.

## `scripts/check.py` gates (local = CI)

1. `guard_no_media.py`
2. `ruff check` + `ruff format --check`
3. `mypy` (strict on `vsl_backend`)
4. `pytest`
5. `npm run lint`
6. `npm run typecheck`
7. `npm test` (Vitest)
8. `npm run build`
9. `npm run e2e` (Playwright; starts the mock backend on port 8765 and the preview on 4173; skip with `--skip-e2e`)
10. `scripts/gen_contracts.py --check` (generated TypeScript matches Pydantic)

CI adds **gitleaks**, installs Playwright Chromium, and runs everything on **Ubuntu and Windows**.

**Phase 3 coverage:**
- vsl-features: spec/frame validation, normalisation invariance (position, distance), segmentation against synthetic ground truth at 10/15/30 fps, pause tolerance, DTW, decision policy, cooldown.
- Backend: the session protocol (handshake, every rejection code, dropped frames, rate limit, status throttle, max duration, server mode with a fake extractor); WS transport (origin refusal, mock and template end to end on the replay, heartbeat); template model integrity (sha256 tampering, path traversal, spec mismatch, no pickle); L3 header/JPEG/result conversion with fakes; replay fixture freshness (numeric tolerance across OSes).
- Frontend: packer, metrics, ladder, recognition reducer, WS client with a fake socket, replay source timing, binary header, RecognitionPanel states with axe.
- E2E: full stack replay (real backend in mock mode) for segmentation → candidate → confirm (no speech in mock) → uncertain → rejected; metrics; tab-hidden pause; recorder export.
- **Not covered on the Mac (Windows procedure):** MediaPipe L1/L2 extraction, the worker vs main-thread spike, real L3 extraction, fps and latency on real hardware.

**Phase 2 e2e coverage:** fake-camera preview (mirrored), camera selector and stop; camera denied, unavailable and in use; manual text → transcript → local-voice speech; offline banner with manual text still working; settings voice diagnostics; axe (full WCAG 2.2 AA rules, including colour contrast) on every view in light and dark mode and in the error states; no requests outside localhost.

## Merge gates

- All gates green on both CI operating systems.
- Contract files unchanged after regeneration (P3+).
- No new dependency without a justification.
- For ML changes: parity test passes and the model card is updated.
- Docs updated.
- The owner has reviewed.
