import { useEffect, useId, useRef, useState } from "react";

import type { RecorderConfig, SampleSummary, WireFrame } from "../api/generated/contracts";
import {
  ApiCallError,
  createRecordingSession,
  fetchFeatureSpec,
  fetchRecorderConfig,
  uploadSample,
} from "../api/http";
import {
  CameraLandmarkSource,
  ReplayLandmarkSource,
  loadReplay,
  type LandmarkSource,
} from "../features/landmarks/sources";
import type { ExtractionLevel } from "../features/metrics/ladder";
import type { SourceKind } from "../features/recognition/useRecognitionSession";
import { errorMessages, vi } from "../i18n/vi";

// Phase 4 recorder: the developer's OWN signs only (consent "SELF"; anything else is
// refused by the backend until B2). Landmarks only, saved by the backend into
// DATA_ROOT, outside the repository.

const COUNTDOWN_S = 3;
// 6 s takes fit a sign AND the hands resting visibly afterwards (the live
// "sign never ends" case found in P3); 3 s is enough for a sign alone.
const TAKE_DURATIONS_MS = [3000, 6000] as const;
type TakeMs = (typeof TAKE_DURATIONS_MS)[number];
const EXTRACTOR_VERSION = "tasks-vision@1.0.1";
const CONDITIONS = {
  lighting: ["normal", "bright", "dim"],
  background: ["plain", "busy"],
  camera: ["laptop", "external"],
  distance: ["normal", "near", "far"],
} as const;
type ConditionKey = keyof typeof CONDITIONS;

interface Props {
  sourceKind: SourceKind;
  stream: MediaStream | null;
  level: ExtractionLevel;
}

type Phase =
  | { kind: "idle" }
  | { kind: "countdown"; n: number }
  | { kind: "recording" }
  | { kind: "saving" }
  | { kind: "message"; text: string; tone: "success" | "danger" };

const describe = (error: unknown) =>
  error instanceof ApiCallError
    ? `${errorMessages[error.code] ?? ""} ${error.message}`.trim()
    : vi.recorder.sourceFailed;

export function RecorderView({ sourceKind, stream, level }: Props) {
  const ids = { signer: useId(), consent: useId(), hand: useId(), duration: useId() };
  const conditionIds = { lighting: useId(), background: useId(), camera: useId(), distance: useId() };
  const [config, setConfig] = useState<RecorderConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [signer, setSigner] = useState("DEV-01");
  const [consent, setConsent] = useState("SELF");
  const [hand, setHand] = useState<"right" | "left">("right");
  const [conditions, setConditions] = useState<Record<ConditionKey, string>>({
    lighting: "normal",
    background: "plain",
    camera: "laptop",
    distance: "normal",
  });
  const [session, setSession] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [takeMs, setTakeMs] = useState<TakeMs>(3000);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [saved, setSaved] = useState<SampleSummary[]>([]);
  const source = useRef<LandmarkSource | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const busy = phase.kind === "countdown" || phase.kind === "recording" || phase.kind === "saving";
  const l2 = level === "L2";

  useEffect(() => {
    fetchRecorderConfig()
      .then(setConfig)
      .catch((e: unknown) => setConfigError(describe(e)));
    const pending = timers.current; // same array for the component's lifetime
    const live = source;
    return () => {
      pending.forEach(clearTimeout);
      live.current?.stop();
    };
  }, []);

  const later = (ms: number, fn: () => void) => timers.current.push(setTimeout(fn, ms));

  const makeSource = async (): Promise<LandmarkSource> => {
    if (sourceKind === "replay") return new ReplayLandmarkSource(await loadReplay());
    if (!stream) throw new Error("camera");
    return new CameraLandmarkSource(stream, l2 ? "L2" : "L1");
  };

  const fail = (e: unknown) => {
    const text = e instanceof Error && e.message === "camera" ? vi.recorder.needCamera : describe(e);
    setPhase({ kind: "message", text, tone: "danger" });
  };

  const startSession = async () => {
    try {
      const probe = await makeSource(); // only for the image size; not started
      const created = await createRecordingSession({
        signer_id: signer.trim(),
        consent_id: consent.trim(),
        dominant_hand: hand,
        conditions,
        image_width: probe.imageWidth,
        image_height: probe.imageHeight,
        feature_spec_version: (await fetchFeatureSpec()).version,
        extractor_version: sourceKind === "replay" ? "synthetic" : EXTRACTOR_VERSION,
        extractor_backend: sourceKind === "replay" ? "replay" : `browser-${l2 ? "L2" : "L1"}`,
      });
      setSession(created.session_id);
      setSaved([]);
      setPhase({ kind: "idle" });
    } catch (e) {
      fail(e);
    }
  };

  const recordTake = async () => {
    if (!session || !selected) return;
    const label = selected;
    const duration = takeMs;
    try {
      const spec = await fetchFeatureSpec();
      const src = await makeSource();
      const frames: WireFrame[] = [];
      let capturing = false;
      await src.start(
        {
          onFrame: (f) => {
            if (capturing) frames.push(f);
          },
          onBinary: () => undefined,
          onProcessed: () => undefined,
        },
        spec,
        () => performance.now(),
      );
      source.current = src;
      for (let n = COUNTDOWN_S; n > 0; n--) later((COUNTDOWN_S - n) * 1000, () => setPhase({ kind: "countdown", n }));
      later(COUNTDOWN_S * 1000, () => {
        capturing = true;
        setPhase({ kind: "recording" });
      });
      later(COUNTDOWN_S * 1000 + duration, () => {
        capturing = false;
        src.stop();
        source.current = null;
        setPhase({ kind: "saving" });
        uploadSample(session, { label, take_ms: duration, frames })
          .then((sample) => {
            setSaved((s) => [sample, ...s]);
            setPhase({
              kind: "message",
              tone: "success",
              text: vi.recorder.saved(sample.label, sample.n_frames, sample.dropped_frames),
            });
          })
          .catch(fail);
      });
    } catch (e) {
      fail(e);
    }
  };

  if (configError) {
    return (
      <section className="card" aria-labelledby="recorder-heading">
        <h2 id="recorder-heading">{vi.recorder.heading}</h2>
        <p role="alert" className="status status--danger">
          {configError}
        </p>
      </section>
    );
  }
  if (!config) return <p className="hint">{vi.recorder.loading}</p>;
  if (!config.enabled) {
    return (
      <section className="card" aria-labelledby="recorder-heading">
        <h2 id="recorder-heading">{vi.recorder.heading}</h2>
        <p className="status status--warning" data-testid="recorder-disabled">
          {vi.recorder.disabled} {config.reason}
        </p>
        <p className="hint mono">{vi.recorder.enableHint}</p>
      </section>
    );
  }

  const groups = (["target", "distractor", "background"] as const).map((kind) => ({
    kind,
    items: config.items.filter((i) => i.sample_kind === kind),
  }));

  return (
    <section className="card" aria-labelledby="recorder-heading">
      <h2 id="recorder-heading">{vi.recorder.heading}</h2>
      <p className="notice notice--warning">{vi.recorder.warning}</p>
      {config.data_root && <p className="hint mono">{vi.recorder.dataRoot(config.data_root)}</p>}
      {config.developer_only_vocabulary && <p className="hint">{vi.recorder.devVocabulary}</p>}

      <fieldset className="session" disabled={session !== null}>
        <legend>{vi.recorder.session.heading}</legend>
        <div className="field">
          <label htmlFor={ids.signer}>{vi.recorder.session.signerLabel}</label>
          <input id={ids.signer} value={signer} onChange={(e) => setSigner(e.target.value.toUpperCase())} />
        </div>
        <div className="field">
          <label htmlFor={ids.consent}>{vi.recorder.session.consentLabel}</label>
          <input
            id={ids.consent}
            value={consent}
            disabled={!config.third_party_allowed}
            onChange={(e) => setConsent(e.target.value.toUpperCase())}
          />
          {!config.third_party_allowed && <p className="hint">{vi.recorder.session.consentSelfOnly}</p>}
        </div>
        <div className="field">
          <label htmlFor={ids.hand}>{vi.recorder.session.handLabel}</label>
          <select id={ids.hand} value={hand} onChange={(e) => setHand(e.target.value as "right" | "left")}>
            <option value="right">{vi.recorder.session.hands.right}</option>
            <option value="left">{vi.recorder.session.hands.left}</option>
          </select>
        </div>
        {(Object.keys(CONDITIONS) as ConditionKey[]).map((key) => (
          <div className="field" key={key}>
            <label htmlFor={conditionIds[key]}>{vi.recorder.session[key]}</label>
            <select
              id={conditionIds[key]}
              value={conditions[key]}
              onChange={(e) => setConditions({ ...conditions, [key]: e.target.value })}
            >
              {CONDITIONS[key].map((value) => (
                <option key={value} value={value}>
                  {vi.recorder.conditionOptions[key]?.[value] ?? value}
                </option>
              ))}
            </select>
          </div>
        ))}
      </fieldset>
      <div className="row">
        {session ? (
          <>
            <p className="status status--success" data-testid="session-active">
              {vi.recorder.session.active(session)}
            </p>
            <button type="button" className="btn" disabled={busy} onClick={() => setSession(null)}>
              {vi.recorder.session.end}
            </button>
          </>
        ) : (
          <button type="button" className="btn btn--primary" onClick={() => void startSession()}>
            {vi.recorder.session.start}
          </button>
        )}
      </div>

      {session && (
        <>
          <fieldset className="items" disabled={busy}>
            <legend>{vi.recorder.itemLegend}</legend>
            {groups.map(
              (group) =>
                group.items.length > 0 && (
                  <div key={group.kind} className="items__group">
                    <p className="items__kind">{vi.recorder.kinds[group.kind]}</p>
                    {group.items.map((item) => (
                      <label key={item.gloss_id} className="check">
                        <input
                          type="radio"
                          name="recorder-item"
                          value={item.gloss_id}
                          checked={selected === item.gloss_id}
                          onChange={() => setSelected(item.gloss_id)}
                        />
                        <span className="mono">{item.gloss_id}</span> — <span lang="vi">{item.text_vi}</span>
                      </label>
                    ))}
                  </div>
                ),
            )}
          </fieldset>
          <div className="field">
            <label htmlFor={ids.duration}>{vi.recorder.durationLabel}</label>
            <select
              id={ids.duration}
              value={takeMs}
              disabled={busy}
              onChange={(e) => setTakeMs(Number(e.target.value) as TakeMs)}
            >
              {TAKE_DURATIONS_MS.map((ms) => (
                <option key={ms} value={ms}>
                  {vi.recorder.duration(ms / 1000)}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            className="btn btn--primary"
            disabled={busy || !selected}
            onClick={() => void recordTake()}
          >
            {vi.recorder.record(takeMs / 1000)}
          </button>
        </>
      )}

      <div role="status" aria-live="assertive" className="recorder__status">
        {phase.kind === "countdown" && <p className="status status--warning">{vi.recorder.countdown(phase.n)}</p>}
        {phase.kind === "recording" && (
          <p className="banner banner--danger" data-testid="recording-banner">
            <span aria-hidden="true">●</span> {vi.recorder.recording}
          </p>
        )}
        {phase.kind === "saving" && <p className="status status--info">{vi.recorder.saving}</p>}
        {phase.kind === "message" && (
          <p className={`status status--${phase.tone}`} data-testid="recorder-message">
            {phase.text}
          </p>
        )}
      </div>

      {session && (
        <>
          <p data-testid="take-count">{vi.recorder.takesInSession(saved.length)}</p>
          <ul className="voice-list">
            {saved.map((s) => (
              <li key={s.sample_id} className="mono">
                {s.sample_id} · {s.label} · {s.n_frames}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
