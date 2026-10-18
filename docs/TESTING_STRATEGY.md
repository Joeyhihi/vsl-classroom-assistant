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

CI adds **gitleaks** and runs everything on **Ubuntu and Windows**.

## Merge gates

- All gates green on both CI operating systems.
- Contract files unchanged after regeneration (P3+).
- No new dependency without a justification.
- For ML changes: parity test passes and the model card is updated.
- Docs updated.
- The owner has reviewed.
