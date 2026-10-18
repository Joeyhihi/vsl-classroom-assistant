# Pilot protocol (P9) — DRAFT

> **Status: draft for owner review.** It must not be used with participants until the consent package (B2), the legal applicability review and, where required, an ethics review have approved it. Placeholders are marked `[…]`.

## 1. Purpose

A **controlled adult pilot** checks whether the assistant helps a Deaf or hard-of-hearing student and a hearing teacher exchange short classroom messages. The pilot measures usefulness and failure modes. It does **not** measure translation quality, because the app recognises a closed list of signs and does not translate.

Questions:
1. Can participants complete short classroom exchanges (requests, answers, check-ins) with the app?
2. How often is a confirmed sign wrong, and how often does the confirm step catch errors?
3. Is push-to-talk subtitling useful for the teacher (if G7 approved STT)?
4. What breaks: lighting, framing, hands-busy confirmation, latency, vocabulary gaps?

## 2. Participants and roles

- **Adults only** (18+), who give informed consent in Vietnamese text **and** VSL video (B2).
- `[n]` Deaf/HoH signers fluent in VSL, `[n]` hearing teachers or volunteers.
- A **VSL-fluent facilitator** is present for every session. The facilitator never interprets *for* the app; they help only when the participant asks or the session must stop.
- The developer runs the laptop and takes notes. They do not coach signing.
- Compensation: `[agreed in B0]`.

## 3. Setup

- The Windows laptop runs the packaged app: `uv run --extra windows python scripts/run_app.py` with the G5-approved model (`VSL_MODEL_MODE=onnx`, `VSL_SIGN_MODEL_ID=[id]`).
- Check before each day: the privacy checklist ([SECURITY_AND_PRIVACY.md §4](SECURITY_AND_PRIVACY.md#4-privacy-review-checklist-run-before-p8-and-p9)), camera framing (shoulders visible), lighting, and the "Màn hình lớn" (large display) on the second screen for the teacher.
- **No video and no landmarks are recorded during the pilot.** The only data kept is: the session notes (no names), the in-app feedback (`feedback.jsonl`: IDs and verdicts only) and the questionnaires.
- Participants are identified by pseudonymous IDs (`PIL-01`…). The identity register is kept separately, as in the dataset procedure.

## 4. Session plan (about 45 minutes)

| Step | Minutes | What happens |
|---|---|---|
| Welcome and consent check | 5 | Confirm consent; explain that anyone can stop at any time without giving a reason |
| Familiarisation | 10 | "Danh sách ký hiệu" (sign list): the participant tries every sign once, with no data kept |
| Scripted exchanges | 15 | `[n]` short scenarios (e.g. ask to repeat, say "I understand", ask for the toilet). The teacher answers by typing or by push-to-talk |
| Free exchange | 5 | A short exchange within the vocabulary, chosen by the participants |
| Questionnaire + interview | 10 | Usefulness, effort, trust, confirmation method (button, space bar, pedal), what was missing |

The participant marks every confirmed sign ✓ / ✗ / ? in the app. The developer notes rejected and uncertain events and when the facilitator had to step in.

## 5. Stop rules

Stop the session immediately if the participant is distressed, asks to stop, or someone who did not consent appears in the camera view and cannot be avoided. Stop the pilot (all sessions) if a privacy check fails or data is found outside `DATA_ROOT`.

## 6. Analysis

- `uv run python scripts/feedback_report.py`: correct share with a 95% CI per model, and the most common confusions.
- From the notes: task completion per scenario, rejected/uncertain rate, facilitator interventions, latency complaints.
- Questionnaires: summarised per item. Quotes are anonymised and confirmed with the participant.
- Findings and decisions go into `docs/` (no personal data). The raw notes stay in `DATA_ROOT`.

## 7. Withdrawal and deletion

A participant may withdraw during or after the pilot. Their feedback rows are deleted with "Xoá dữ liệu cục bộ" (delete local data) on the pilot laptop, or by session, and their notes and questionnaires are destroyed. The identity register entry is removed last.
