# Security & Privacy

**Design stance:** privacy by design for an educational setting. The MVP is **adults only**. Use with minors or in schools requires institutional approval and legal review first. This document does not assume that any recording or data retention is legally allowed.

## 1. Data inventory

| Data | Where | Stored? | Leaves the laptop? |
|---|---|---|---|
| Camera video | Browser memory | **Never** (except consented raw video in data-collection mode) | Never |
| Landmarks (L1/L2) | Browser → backend over localhost WS | Never, except in data-collection mode | Never |
| JPEG frames (L3, opt-in) | Browser → backend over localhost WS | Never; dropped after extraction | Never |
| Microphone audio (P7) | Browser → backend, push-to-talk only | Never; dropped after transcription | Never |
| Transcript | Browser memory | Only if the user exports it | Never |
| Settings | Browser `localStorage` | Yes | Never |
| Feedback (P6) | `DATA_ROOT/feedback/feedback.jsonl` | Yes (no free text) | Never |
| Research data | `DATA_ROOT` (Windows laptop, outside the repo) | Yes, under consent | Only via encrypted, logged transfer |
| Recorder uploads (P4) | Browser → backend over localhost, landmarks only | Yes: `.npz` plus a manifest row in `DATA_ROOT` (refused if `DATA_ROOT` is inside the repo) | Never |
| Identity register | Encrypted, outside `DATA_ROOT` | Yes | Never |

## 2. Controls

**Camera and microphone:**
- Requested only after a user action, with an explanation first.
- A persistent "Camera đang bật" (camera on) indicator.
- The microphone is active only **while push-to-talk is held**, with a "Đang nghe" (listening) indicator. No always-on voice detection.

**Notice and consent:** a PrivacyView in plain Vietnamese. Data collection is behind a flag, requires a consent ID, and shows a red banner.

**Local processing:**
- The backend binds to `127.0.0.1`.
- The Origin allow-list (`VSL_ALLOWED_ORIGINS`) is enforced for HTTP **and WebSocket** connections. This prevents cross-site WebSocket hijacking by other sites open in the same browser.
- CSP: `default-src 'self'; connect-src 'self' ws://127.0.0.1:* ws://localhost:*`.
- No CDN at runtime; MediaPipe assets are self-hosted.

**Safe logging:**
- Logged: counts, latencies, status and error codes, request IDs.
- **Never logged:** landmarks, frames, audio, transcript text, or the content of feedback.
- A redaction test enforces this.

**Temporary data:** ring buffers are bounded and cleared when a segment or session ends. Nothing is written to temporary files.

**Deletion:** "Xoá dữ liệu cục bộ" (delete local data) clears `localStorage`, the transcript, and (P6) feedback through `DELETE /api/v1/feedback`.

**Input validation:**
- Pydantic everywhere.
- Body ≤ 64 KB (REST), WS message ≤ 64 KB, WS binary ≤ 200 KB, STT upload ≤ 2 MB and ≤ 30 s.
- Per-field numeric ranges and a frame-rate limit.
- Unknown message types are rejected.

**Secrets:** the MVP needs none. `.env` is gitignored, and gitleaks runs in CI from P1.

**Dependencies:** lockfiles are committed. `npm audit` and `pip-audit` run (warnings first, gating from P8). Dependency changes need a justification in the PR.

**Model integrity:** the sha256 of every artifact is checked before loading. ONNX or `.npz` (`allow_pickle=False`) only. No pickle and no `torch.load` in the backend.

**Public repo:**
- Synthetic fixtures only.
- `guard_no_media.py` blocks media, model, and dataset files and anything over 1 MB.
- Reviewer role IDs instead of names.
- Model publication follows the consent scope.

**Unauthorised access:** binding to loopback and the Origin checks are enough on a single laptop. LAN mode would need HTTPS plus a pairing token (future, ADR-006).

**Bystanders:** recording happens only in controlled settings. Live mode never stores anything. The overlay makes wrong-person tracking visible.

## 3. Mock mode safety

`VSL_MODEL_MODE=mock` is refused unless `VSL_ENV=dev`. In mock mode the UI shows a permanent MOCK badge and **speech is disabled**, so scripted output can never be spoken in a real setting.

## 4. Privacy review checklist (run before P8 and P9)

- [ ] No network requests to anything other than localhost (Playwright egress test passes)
- [ ] CSP header present
- [ ] Log redaction test passes; manual log inspection after a 10-minute session
- [ ] No files written outside `DATA_ROOT` during live use
- [ ] Delete-local-data verified
- [ ] Consent scopes match how data and models are actually used; identity register up to date
- [ ] Legal applicability review documented (B2)
