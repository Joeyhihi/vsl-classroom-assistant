import { useEffect, useId, useRef, useState } from "react";

import type { WireFrame } from "../api/generated/contracts";
import { fetchFeatureSpec } from "../api/http";
import {
  CameraLandmarkSource,
  ReplayLandmarkSource,
  loadReplay,
  type LandmarkSource,
} from "../features/landmarks/sources";
import type { ExtractionLevel } from "../features/metrics/ladder";
import type { SourceKind } from "../features/recognition/useRecognitionSession";
import { vi } from "../i18n/vi";

// Minimal Phase 3 recorder: the developer's OWN signs only, landmarks only,
// kept in memory until downloaded. Phase 4 adds consent IDs and a manifest.

const COUNTDOWN_S = 3;
// 6 s takes fit a sign AND the hands resting visibly afterwards (the live
// "sign never ends" case found in P3); 3 s is enough for a sign alone.
const TAKE_DURATIONS_MS = [3000, 6000] as const;
type TakeMs = (typeof TAKE_DURATIONS_MS)[number];
const EXTRACTOR_VERSION = "tasks-vision@1.0.1";

export interface RecordingFile {
  format: "vsl-recording-v1";
  developer_own_data: true;
  feature_spec_version: string;
  extractor: { version: string; backend: string };
  image_width: number;
  image_height: number;
  label: { gloss_id: string; text_vi: string; icon: string };
  takes: { frames: WireFrame[]; take_ms: number }[];
  created_at: string;
}

interface Props {
  sourceKind: SourceKind;
  stream: MediaStream | null;
  level: ExtractionLevel;
}

type Phase = { kind: "idle" } | { kind: "countdown"; n: number } | { kind: "recording" } | { kind: "error"; text: string };

export function RecorderView({ sourceKind, stream, level }: Props) {
  const ids = { gloss: useId(), text: useId(), icon: useId(), duration: useId(), lockHint: useId() };
  const [label, setLabel] = useState({ gloss_id: "", text_vi: "", icon: "hand" });
  const [takes, setTakes] = useState<{ frames: WireFrame[]; take_ms: number }[]>([]);
  const [takeMs, setTakeMs] = useState<TakeMs>(3000);
  // Every take in a file gets the label shown at download time, so the label is
  // locked while takes exist: download or clear first (no silent data loss).
  const labelLocked = takes.length > 0;
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const meta = useRef<{ width: number; height: number; spec: string; backend: string } | null>(null);
  const source = useRef<LandmarkSource | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(
    () => () => {
      timers.current.forEach(clearTimeout);
      source.current?.stop();
    },
    [],
  );

  const ready = label.gloss_id.trim() !== "" && label.text_vi.trim() !== "";
  const later = (ms: number, fn: () => void) => timers.current.push(setTimeout(fn, ms));

  const recordTake = async () => {
    if (!ready) return setPhase({ kind: "error", text: vi.recorder.needLabel });
    if (sourceKind === "camera" && !stream) return setPhase({ kind: "error", text: vi.recorder.needCamera });
    try {
      const spec = await fetchFeatureSpec();
      const src: LandmarkSource =
        sourceKind === "replay"
          ? new ReplayLandmarkSource(await loadReplay())
          : new CameraLandmarkSource(stream as MediaStream, level === "L2" ? "L2" : "L1");
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
      meta.current = {
        width: src.imageWidth,
        height: src.imageHeight,
        spec: spec.version,
        backend: sourceKind === "replay" ? "replay" : `browser-${level === "L2" ? "L2" : "L1"}`,
      };
      for (let n = COUNTDOWN_S; n > 0; n--) later((COUNTDOWN_S - n) * 1000, () => setPhase({ kind: "countdown", n }));
      later(COUNTDOWN_S * 1000, () => {
        capturing = true;
        setPhase({ kind: "recording" });
      });
      const duration = takeMs;
      later(COUNTDOWN_S * 1000 + duration, () => {
        capturing = false;
        src.stop();
        source.current = null;
        setTakes((t) => [...t, { frames, take_ms: duration }]);
        setPhase({ kind: "idle" });
      });
    } catch {
      setPhase({ kind: "error", text: vi.recorder.sourceFailed });
    }
  };

  const download = () => {
    const m = meta.current;
    if (!m || takes.length === 0) return;
    const file: RecordingFile = {
      format: "vsl-recording-v1",
      developer_own_data: true,
      feature_spec_version: m.spec,
      extractor: { version: m.backend === "replay" ? "synthetic" : EXTRACTOR_VERSION, backend: m.backend },
      image_width: m.width,
      image_height: m.height,
      label: { gloss_id: label.gloss_id.trim(), text_vi: label.text_vi.trim().normalize("NFC"), icon: label.icon.trim() },
      takes,
      created_at: new Date().toISOString(),
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(file)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `recording-${file.label.gloss_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const busy = phase.kind === "countdown" || phase.kind === "recording";

  return (
    <section className="card" aria-labelledby="recorder-heading">
      <h2 id="recorder-heading">{vi.recorder.heading}</h2>
      <p className="notice notice--warning">{vi.recorder.warning}</p>
      <div className="field">
        <label htmlFor={ids.gloss}>{vi.recorder.glossLabel}</label>
        <input
          id={ids.gloss}
          value={label.gloss_id}
          disabled={labelLocked}
          aria-describedby={labelLocked ? ids.lockHint : undefined}
          onChange={(e) => setLabel({ ...label, gloss_id: e.target.value })}
        />
      </div>
      <div className="field">
        <label htmlFor={ids.text}>{vi.recorder.textLabel}</label>
        <input
          id={ids.text}
          value={label.text_vi}
          disabled={labelLocked}
          aria-describedby={labelLocked ? ids.lockHint : undefined}
          onChange={(e) => setLabel({ ...label, text_vi: e.target.value })}
        />
      </div>
      <div className="field">
        <label htmlFor={ids.icon}>{vi.recorder.iconLabel}</label>
        <input
          id={ids.icon}
          value={label.icon}
          disabled={labelLocked}
          aria-describedby={labelLocked ? ids.lockHint : undefined}
          onChange={(e) => setLabel({ ...label, icon: e.target.value })}
        />
      </div>
      {labelLocked && (
        <p id={ids.lockHint} className="hint" data-testid="label-lock-hint">
          {vi.recorder.labelLocked}
        </p>
      )}
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

      <div role="status" aria-live="assertive" className="recorder__status">
        {phase.kind === "countdown" && <p className="status status--warning">{vi.recorder.countdown(phase.n)}</p>}
        {phase.kind === "recording" && (
          <p className="banner banner--danger" data-testid="recording-banner">
            <span aria-hidden="true">●</span> {vi.recorder.recording}
          </p>
        )}
        {phase.kind === "error" && <p className="status status--danger">{phase.text}</p>}
      </div>

      <div className="row">
        <button type="button" className="btn btn--primary" disabled={busy} onClick={() => void recordTake()}>
          {vi.recorder.record(takeMs / 1000)}
        </button>
        <button type="button" className="btn" disabled={busy || takes.length === 0} onClick={download}>
          {vi.recorder.download}
        </button>
        <button type="button" className="btn" disabled={busy || takes.length === 0} onClick={() => setTakes([])}>
          {vi.recorder.clear}
        </button>
      </div>
      <p data-testid="take-count">{vi.recorder.takes(takes.length)}</p>
    </section>
  );
}
