# Project status

_Last updated: 2026-10-19_

## Summary

**The build is complete.** Every software deliverable in the [roadmap](ROADMAP.md), Phases 0–9, is built, merged into `main` and passing CI on Ubuntu and Windows.

What remains is:
1. **Testing on the Windows laptop** with the real camera, models and microphone. Small fixes are expected here, because some code has only run on synthetic data or fakes.
2. **People work** that code cannot do: vocabulary validation, consent, recording more signers, sessions with Deaf users, and the pilot.

## Build status by phase

| Phase | What it is | Code | Verified so far | Still to verify |
|---|---|---|---|---|
| P0–P3 | Foundation, UI, walking skeleton | ✅ Merged | Mac, CI, Windows (P1–P3 runs) | — |
| P4 | Recording, review, deletion, quality report | ✅ Merged (#10) | Unit tests, CI | Live segmentation check, a full recording session (Windows) |
| P5 | Training, evaluation, calibration, ONNX export | ✅ Merged (#11) | CI trains on synthetic signers, checks ONNX parity and reloads the model | First model on real recordings, live test (Windows) |
| P6 | Feedback, sign list, large display, ResourceManager | ✅ Merged (#12) | Unit + browser tests (mock mode) | With a real model (Windows) |
| P7 | Speech-to-text subtitles (off by default) | ✅ Merged (#13) | Tests with a fake speech model | Real microphone + Whisper, benchmark (Windows) |
| P8 | Evaluation, accessibility, privacy | ✅ Automated parts | WCAG axe checks on every view (light/dark), no network egress, CSP | Manual WCAG audit, Deaf user sessions, privacy sign-off |
| P9 | One-command app, feedback report, pilot protocol | ✅ Merged (#14) | Packaged app checked in Chrome (mock mode) | Real models on Windows; pilot protocol is a **draft** |

## Windows test checklist

Do this with strong wifi; the first install downloads a few hundred MB. Full instructions: [CROSS_PLATFORM_SETUP.md §8b–8d](CROSS_PLATFORM_SETUP.md#phase-4-workflow).

1. **Update:** GitHub Desktop → Fetch → `main` → Pull. Then run `uv sync --extra windows` and `uv run python scripts/bootstrap.py --with-models`.
2. **Smoke test:** `uv run python scripts/run_app.py --mock` opens the app with scripted predictions. Check the camera and the sign list.
3. **Record (P4):** at least 10 accepted takes per sign, plus "other sign" and rest takes, on 2–3 different days if possible. Review them in "Duyệt mẫu".
4. **Train (P5):** `uv run --extra windows python scripts/train_sign_model.py --model-id vsl-01`. Read the report in `DATA_ROOT/reports/models/`.
5. **Run live:** set `VSL_MODEL_MODE=onnx` and `VSL_SIGN_MODEL_ID=vsl-01` in `.env`, then run `uv run --extra windows python scripts/run_app.py`. Sign, confirm, and mark results ✓ / ✗ / ?.
6. **Speech (P7, optional):** set `VSL_STT_ENABLED=true`, then hold "Giữ để nói" (hold to talk) and speak. For gate G7, run `scripts/benchmark_stt.py` on consented clips.
7. **Report:** `uv run python scripts/feedback_report.py`.

**If something breaks:** copy the error text, or take a screenshot of the terminal and the browser, and open a GitHub issue or send it to the developer. Fixes are made on the Mac and pulled again.

## People work (not code)

| Step | Owner | Needed for |
|---|---|---|
| B0 Roles and compensation | Team lead | Everything below |
| B1 Vocabulary validated by Deaf signers (+ which signs may be mirrored) | Deaf co-design partners | Real vocabulary in the app |
| B2 Consent package (Vietnamese text + VSL video), legal review | Team lead + partner | **Recording anyone other than the developer** |
| B3–B4 Pilot recording, then ≥12 signers × ≥5 takes | Team | Gate G5: does the model work for new signers? |
| G5 / G7 decisions | Owner | Approving the sign model / speech-to-text |
| Deaf user UX sessions | Team + partners | P6/P8 exit |
| Ethics/legal review of the [pilot protocol](PILOT_PROTOCOL.md) | Team lead | Running the pilot |

## Honest expectations

- With only the developer's recordings, the model recognises **the developer's own signing**. Its report says "prototype numbers, not a G5 result". It is good for demos, not for other students yet.
- The app recognises a **closed list of signs**. It does not translate VSL.
