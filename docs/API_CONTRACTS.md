# API & Interface Contracts

## Conventions

- **Base path:** `/api/v1` for REST. The WebSocket messages also carry `protocol_version: 1`.
- **Versioning:** a breaking change means a new path (`/api/v2`) or a new `protocol_version`. Fields are only ever added in a backwards-compatible way.
- **Naming:** `snake_case` on the wire **and** in the TypeScript types. There is no case-conversion layer.
- **Units:** time is always in **milliseconds** (`*_ms`). Scores are calibrated probabilities in [0, 1].
- **Text:** Vietnamese text is normalised to Unicode NFC.
- **Single source of truth:** Pydantic models in `services/ai-backend/src/vsl_backend/schemas/`. `scripts/gen_contracts.py` turns them into JSON Schema and then `apps/web/src/api/generated/contracts.ts` (via `json-schema-to-typescript`). `scripts/check.py` and CI fail if the generated file is out of date. `apps/web/src/api/types.ts` keeps only a runtime guard for health, checked against the shared example by both test suites.
- **Sync vs async:**
  - Health, vocabulary, models, and feedback are fast handlers that block nothing.
  - ONNX inference runs inline if it takes under 10 ms (measured), otherwise in a threadpool.
  - STT always runs in a threadpool, one job at a time.

## Error envelope {#error-envelope}

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Human-readable (English, for developers)", "details": {}, "request_id": "b3f1c2..." } }
```

| Code | HTTP | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 422 | The request failed schema validation |
| `PAYLOAD_TOO_LARGE` | 413 | Body or message exceeds the size limit |
| `RATE_LIMITED` | 429 | Too many frames or requests |
| `ORIGIN_FORBIDDEN` | 403 | The Origin is not in the allow-list |
| `NOT_FOUND` | 404 | Unknown route |
| `PROTOCOL_MISMATCH` | — (WS) | Unsupported `protocol_version` |
| `FEATURE_SPEC_MISMATCH` | — (WS) | The client's spec version differs from the server's |
| `EXTRACTION_UNAVAILABLE` | — (WS) | L3 was requested but is not installed or enabled |
| `MODEL_UNAVAILABLE` | 503 | No usable sign model |
| `RESOURCE_EXHAUSTED` | 503 | The RAM or VRAM guard refused to load a model |
| `STT_UNAVAILABLE` | 503 | STT is disabled or failed |
| `RECORDER_DISABLED` | 403 | Recorder off, or `DATA_ROOT` invalid (reason given) |
| `CONSENT_REQUIRED` | 403 | Consent rule refused the session |
| `INTERNAL` | 500 | Unexpected error. The log has details; the response never echoes the payload. |

The frontend maps each `code` to a Vietnamese message in `apps/web/src/i18n/vi.ts`. Every response carries an `X-Request-ID` header.

## REST endpoints

| Method | Path | Phase | Request | Response |
|---|---|---|---|---|
| GET | `/api/v1/health` | **P1** | — | `HealthResponse` |
| GET | `/api/v1/vocabulary` | P3 | — | `VocabularyResponse` `{vocabulary_version, entries:[{gloss_id, text_vi, icon}]}`. Internal `__*__` classes are excluded. 503 `MODEL_UNAVAILABLE` without a model. |
| GET | `/api/v1/models` | P3 | — | `ModelInfo` `{model_id, kind: mock\|template-dtw\|onnx, vocabulary_version, feature_spec_version, developer_only}`. When `developer_only` is true the UI shows a badge. |
| GET | `/api/v1/feature-spec` | P3 | — | `FeatureSpecWire`, the same object as in `session.started`. Used by the recorder, which has no WS session. |
| GET | `/api/v1/recordings/config` | P4 | — | `RecorderConfig`: `{enabled, reason, third_party_allowed, data_root, vocabulary_version, developer_only_vocabulary, items[]}` |
| POST | `/api/v1/recordings/sessions` | P4 | `SessionCreate` | 201 `{session_id, signer_id}`. 403 `CONSENT_REQUIRED` unless consent is `SELF` with a `DEV-..` signer (until B2); 403 `RECORDER_DISABLED` when off |
| POST | `/api/v1/recordings/sessions/{id}/samples` | P4 | `{label, take_ms, frames[]}` (≤ 600 frames, 2 MB body limit) | 201 `SampleSummary`. Frames validated one by one; < 50 % valid → 422 |
| GET | `/api/v1/recordings/samples?status=&session_id=` | P4 | — | `SampleList` (current view: latest review, deletions hidden) |
| GET | `/api/v1/recordings/samples/{id}/frames` | P4 | — | `SampleFrames` (for the review replay) |
| POST | `/api/v1/recordings/samples/{id}/review` | P4 | `{status: accepted\|rejected\|relabelled, reviewer, reject_reason?, relabel_to?}` | `SampleSummary` |
| GET | `/api/v1/diagnostics` | P3 | — | `{rss_mb, python_version, platform, model, server_extraction:{available, reason}}` for the performance panel. |
| POST | `/api/v1/feedback` | P6 | `FeedbackCreate` | 201 `{feedback_id}` |
| DELETE | `/api/v1/feedback` | P6 | — | 204 (deletes all local feedback) |
| POST | `/api/v1/stt/transcriptions` | P7 (gated) | multipart: `audio` (WAV, 16 kHz mono, ≤30 s, ≤2 MB), `language=vi` | `TranscriptionResponse` |

`POST /api/v1/tts` is **not part of the MVP** (ADR-010). It is reserved as a post-MVP sketch: `{text: 1–500 chars NFC, voice_id?, rate: 0.5–2.0}` → `audio/wav`. In the MVP, the health `tts` component reports `disabled`.

### Health (P1)

```python
ComponentStatus = Literal["ready", "loading", "unavailable", "disabled", "mock"]

class ComponentHealth(BaseModel):
    status: ComponentStatus
    detail: str | None = None          # e.g. "device=cpu resident=false"

class HealthComponents(BaseModel):
    sign_model: ComponentHealth
    stt: ComponentHealth
    tts: ComponentHealth

class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]  # degraded = an enabled component is unavailable
    version: str                       # backend package version
    api_version: Literal["v1"]
    environment: Literal["dev", "prod"]
    model_mode: Literal["mock", "template", "onnx"]
    components: HealthComponents
```

```ts
export type ComponentStatus = "ready" | "loading" | "unavailable" | "disabled" | "mock";
export interface ComponentHealth { status: ComponentStatus; detail: string | null }
export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  api_version: "v1";
  environment: "dev" | "prod";
  model_mode: "mock" | "template" | "onnx";
  components: { sign_model: ComponentHealth; stt: ComponentHealth; tts: ComponentHealth };
}
```

Example (P1, mock mode):

```json
{ "status": "ok", "version": "0.1.0", "api_version": "v1", "environment": "dev", "model_mode": "mock",
  "components": { "sign_model": {"status": "mock", "detail": "scripted predictions (cycle)"},
                  "stt": {"status": "disabled", "detail": null},
                  "tts": {"status": "disabled", "detail": "browser speechSynthesis is used"} } }
```

P1 rules:
- `template` mode loads `model-artifacts/sign/<VSL_SIGN_MODEL_ID>/` (P3). If it can't, `sign_model` is `unavailable` with the reason as `detail` (for example `"VSL_SIGN_MODEL_ID is not set"`, `"sha256 mismatch for 'labels.json'"`), and the app runs in manual-only mode. `onnx` stays unavailable until P5.
- `mock` with `environment != dev` is refused at startup, not reported.

### Vocabulary (P3)

```python
class VocabularyEntry(BaseModel):
    gloss_id: str          # "VSL_0001"
    gloss: str             # "XIN_CHAO"
    text_vi: str           # "Xin chào" (NFC)
    icon: str              # icon key
    category: str
    unit_type: Literal["sign", "phrase"]
    status: Literal["provisional", "validated"]

class VocabularyResponse(BaseModel):
    vocabulary_version: str
    entries: list[VocabularyEntry]
```

### Feedback (P6) — built

Rows go to `DATA_ROOT/feedback/feedback.jsonl` with a server `feedback_id` and `at`. IDs are pattern-checked, unknown fields (for example a comment) give 422, and a `DATA_ROOT` inside the repo gives 422. `DELETE` is idempotent.

```python
class FeedbackCreate(BaseModel):
    session_id: str
    prediction_id: str
    model_id: str
    predicted_gloss_id: str | None
    confidence: float = Field(ge=0, le=1)
    verdict: Literal["correct", "incorrect", "unsure"]
    expected_gloss_id: str | None = None
    # no free-text comment in the MVP (privacy)
```

### STT (P7) — built, gated

`VSL_STT_ENABLED=false` gives 503 `STT_UNAVAILABLE`. Wrong format, more than 30 s, or `language` other than `vi` gives 422. A body over `VSL_STT_MAX_BODY_BYTES` (about 2 MB) gives 413. Jobs run one at a time in a threadpool. Audio and text are never logged or stored.

```python
class TranscriptSegment(BaseModel):
    start_ms: int; end_ms: int; text: str

class TranscriptionResponse(BaseModel):
    text: str
    segments: list[TranscriptSegment]
    duration_ms: int
    model_id: str
    processing_ms: int
```

## WebSocket: `/api/v1/recognition/ws` (P3)

- **Lifecycle:** connect (Origin checked) → `session.start` → `session.started` → stream → `session.stop` → `session.stopped`. **Each connection is exactly one session.** After a reconnect the client starts a new session.
- **Heartbeat:** the client sends `ping` every 5 s. If nothing arrives for 15 s, the server closes with 4004.
- **Batching:** the client sends each frame as soon as it is extracted (a batch of 1). Batching added up to ~100 ms of latency in Windows run 1. The server still accepts up to 8 frames per batch.
- **Limits:** a JSON message is at most 64 KB. A batch holds at most 8 frames. At most 30 frames/s (20 in L3). A session lasts at most `VSL_MAX_SESSION_S`, default 7200.

### Client → server

```jsonc
// session.start
{ "type": "session.start", "protocol_version": 1, "feature_spec_version": "fs-1",
  "extraction_mode": "client",            // "client" (L1/L2) | "server" (L3)
  "image_width": 640, "image_height": 480, "fps_hint": 20, "dominant_hand": "right" }

// frames.batch  (client mode only)
{ "type": "frames.batch", "frames": [
  { "t_ms": 1234,
    "pose": [[0.51, 0.32, -0.10, 0.99], "... 33 rows of [x,y,z,visibility]"],
    "left_hand": null,                      // signer's anatomical left; 21×[x,y,z] or null
    "right_hand": [[0.40, 0.55, -0.02], "... 21 rows"],
    "face": [[0.50, 0.20, -0.03], "... K rows; indices from feature_spec"] } ] }

{ "type": "session.stop" }
{ "type": "ping" }
```

- **Coordinates:** MediaPipe normalised image coordinates from the **unmirrored** frame. The preview is mirrored in CSS only.
- **Ranges:** x and y ∈ [-0.5, 1.5]; visibility ∈ [0, 1]; z is bounded per the spec.
- **Validation:** a NaN or out-of-range frame is **dropped and counted** (`status.dropped_frames`). It does not end the session. `t_ms` must increase monotonically.
- **Server extraction mode (L3):** binary messages only. Each has a 16-byte header (`t_ms` uint64 little-endian, width uint16, height uint16, 4 reserved bytes) followed by a JPEG of at most 200 KB and at most 640×480. JSON `frames.batch` is rejected in this mode, and binary frames are rejected in client mode.

### Server → client

```jsonc
{ "type": "session.started", "session_id": "s_8f2c...", "extraction_mode": "client",
  "model": { "model_id": "mock", "vocabulary_version": "v1", "feature_spec_version": "fs-1" },
  "feature_spec": { "version": "fs-1", "face_indices": [1, 33, 61, "..."],
                    "shapes": { "pose": [33, 4], "hand": [21, 3], "face": [40, 3] } },
  "limits": { "max_fps": 30, "max_batch": 8, "max_session_s": 7200 } }

{ "type": "status", "state": "signing",     // waiting_for_hands | ready | signing  ("paused" is client-side only)
  "hands_visible": true, "pose_visible": true, "dropped_frames": 0 }   // sent on change, ≤4/s

{ "type": "prediction", "prediction_id": "p_0012", "model_id": "gru-2027-01-v1",
  "status": "uncertain",                    // confident | uncertain | rejected
  "utterance": { "start_ms": 10450, "end_ms": 11980, "n_frames": 31, "close_reason": "rest" },  // rest | still | max_duration
  "top": [ { "gloss_id": "VSL_0003", "text_vi": "Xin nhắc lại", "icon": "repeat", "score": 0.58 },
           { "gloss_id": "VSL_0007", "text_vi": "Chậm lại", "icon": "slow", "score": 0.21 },
           { "gloss_id": "VSL_0002", "text_vi": "Cảm ơn", "icon": "thanks", "score": 0.09 } ],
  "timings": { "hysteresis_ms": 520, "inference_ms": 4 } }

{ "type": "error", "code": "FEATURE_SPEC_MISMATCH", "message": "...", "fatal": true }
{ "type": "session.stopped", "reason": "client_stop" }
{ "type": "pong" }
```

**Prediction status semantics:**

| Status | Rule (thresholds set at G5) | UI |
|---|---|---|
| `confident` | top-1 score ≥ τ **and** (top-1 − top-2) ≥ margin **and** top-1 is not a rejection class | Large candidate text with Confirm |
| `uncertain` | Above the rejection floor but fails τ or margin | Top-3 alternatives plus Dismiss |
| `rejected` | Rejection class wins, or score < floor | "Không nhận ra" (not recognised). `top` is sent but hidden in the UI. |

**Close codes:** 1000 normal · 1008 origin/policy · 1009 message too big · 1011 internal · 4001 protocol mismatch · 4002 feature spec mismatch · 4003 rate limited · 4004 heartbeat timeout · 4005 extraction unavailable · **4006 model unavailable** (added in P3). The client does not reconnect after 1000, 1008, 1009, 4001, 4002, 4005 or 4006; for other codes it retries with backoff (1, 2, 4, 8 s, at most 5 attempts).

**Implementation notes (P3):**
- A fatal `error` message always comes before the close, and the UI shows the specific code.
- `status` is sent only when (state, hands_visible, pose_visible) changes, at most every 250 ms.
- Rate limit: more than `max_fps + max_batch` frames in any 1 s window closes the session with 4003.
- The same gloss repeated within `VSL_COOLDOWN_MS` (default 1500) is suppressed. Rejected predictions are always sent.

## Transcript entry (browser domain type)

```ts
export interface TranscriptEntry {
  id: string;
  created_at: string;              // ISO 8601
  source: "sign" | "manual" | "speech";
  speaker: "student" | "teacher";
  text: string;
  gloss_id?: string;
  confidence?: number;
  confirmed: boolean;
  spoken: boolean;
}
```

Transcript entries are kept in memory only. They are exported as `.txt` or `.json` only when the user asks.
