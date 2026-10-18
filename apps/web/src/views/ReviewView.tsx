import { useEffect, useId, useRef, useState, type RefObject } from "react";

import type { RecorderConfig, SampleSummary, WireFrame } from "../api/generated/contracts";
import { ApiCallError, fetchRecorderConfig, fetchSampleFrames, listSamples, reviewSample } from "../api/http";
import { LandmarkOverlay } from "../components/recognition/LandmarkOverlay";
import { errorMessages, vi } from "../i18n/vi";

// Phase 4 review: replay a sample's landmark skeleton, then accept, reject (with a
// fixed reason) or relabel within the vocabulary. Every decision is an append-only
// review event in DATA_ROOT/manifests/reviews.jsonl.

type Filter = "pending" | "accepted" | "rejected" | "relabelled" | "all";
const FILTERS: readonly Filter[] = ["pending", "accepted", "rejected", "relabelled", "all"];
const REASONS = ["wrong_sign", "incomplete", "out_of_frame", "tracking_failure", "other"] as const;
type Reason = (typeof REASONS)[number];

/** Replays frames in real time into `frameRef` (read by LandmarkOverlay). Returns a stop function. */
function playFrames(frames: WireFrame[], frameRef: RefObject<WireFrame | null>): () => void {
  const t0 = frames[0]?.t_ms ?? 0;
  const start = performance.now();
  let timer: ReturnType<typeof setTimeout> | null = null;
  let i = 0;
  const step = () => {
    const frame = frames[i];
    if (!frame) return;
    frameRef.current = frame;
    i += 1;
    const next = frames[i];
    if (next) timer = setTimeout(step, Math.max(0, next.t_ms - t0 - (performance.now() - start)));
  };
  step();
  return () => {
    if (timer) clearTimeout(timer);
  };
}

const describe = (error: unknown) =>
  error instanceof ApiCallError ? `${errorMessages[error.code] ?? ""} ${error.message}`.trim() : String(error);

export function ReviewView() {
  const ids = { filter: useId(), reason: useId(), relabel: useId() };
  const [config, setConfig] = useState<RecorderConfig | null>(null);
  const [filter, setFilter] = useState<Filter>("pending");
  const [samples, setSamples] = useState<SampleSummary[]>([]);
  const [current, setCurrent] = useState<SampleSummary | null>(null);
  const [reason, setReason] = useState<Reason>("incomplete");
  const [relabelTo, setRelabelTo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const frameRef = useRef<WireFrame | null>(null);
  const stopPlayback = useRef<(() => void) | null>(null);
  const enabled = config?.enabled ?? false;

  useEffect(() => {
    fetchRecorderConfig()
      .then(setConfig)
      .catch((e: unknown) => setError(describe(e)));
    return () => stopPlayback.current?.();
  }, []);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    listSamples(filter === "all" ? undefined : filter)
      .then((list) => {
        if (!cancelled) {
          setSamples(list.samples);
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(describe(e));
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, filter, reload]);

  const refresh = () => setReload((n) => n + 1);

  const play = async (sample: SampleSummary) => {
    setCurrent(sample);
    setRelabelTo(sample.label);
    stopPlayback.current?.();
    try {
      const { frames } = await fetchSampleFrames(sample.sample_id);
      stopPlayback.current = playFrames(frames, frameRef);
    } catch (e) {
      setError(describe(e));
    }
  };

  const decide = async (status: "accepted" | "rejected" | "relabelled") => {
    if (!current) return;
    try {
      await reviewSample(current.sample_id, {
        status,
        reviewer: vi.review.reviewer,
        reject_reason: status === "rejected" ? reason : null,
        relabel_to: status === "relabelled" ? relabelTo : null,
      });
      setCurrent(null);
      stopPlayback.current?.();
      frameRef.current = null;
      refresh();
    } catch (e) {
      setError(describe(e));
    }
  };

  if (config && !config.enabled) {
    return (
      <section className="card" aria-labelledby="review-heading">
        <h2 id="review-heading">{vi.review.heading}</h2>
        <p className="status status--warning">
          {vi.recorder.disabled} {config.reason}
        </p>
      </section>
    );
  }

  const targets = config?.items ?? [];

  return (
    <section className="card" aria-labelledby="review-heading">
      <h2 id="review-heading">{vi.review.heading}</h2>
      {error && (
        <p role="alert" className="status status--danger">
          {error}
        </p>
      )}
      <div className="row">
        <div className="field">
          <label htmlFor={ids.filter}>{vi.review.filterLabel}</label>
          <select id={ids.filter} value={filter} onChange={(e) => setFilter(e.target.value as Filter)}>
            {FILTERS.map((f) => (
              <option key={f} value={f}>
                {vi.review.statuses[f]}
              </option>
            ))}
          </select>
        </div>
        <button type="button" className="btn" onClick={refresh}>
          {vi.review.refresh}
        </button>
      </div>

      {samples.length === 0 ? (
        <p className="hint">{vi.review.empty}</p>
      ) : (
        <ul className="review__list" data-testid="review-list">
          {samples.map((s) => (
            <li key={s.sample_id} className="review__item">
              <span className="mono">{s.label}</span> <span className="badge">{vi.review.statuses[s.status]}</span>{" "}
              <span className="hint">{vi.review.meta(s.n_frames, s.fps, s.dropped_frames)}</span>
              <button type="button" className="btn btn--small" onClick={() => void play(s)}>
                {vi.review.play} <span className="visually-hidden">{s.sample_id}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {current && (
        <div className="review__current" data-testid="review-current">
          <p className="mono">{current.sample_id}</p>
          {current.label !== current.recorded_label && <p className="hint">{vi.review.recordedAs(current.recorded_label)}</p>}
          <LandmarkOverlay frameRef={frameRef} />
          <div className="row">
            <button type="button" className="btn btn--primary" onClick={() => void decide("accepted")}>
              {vi.review.accept}
            </button>
            <div className="field">
              <label htmlFor={ids.reason}>{vi.review.reasonLabel}</label>
              <select id={ids.reason} value={reason} onChange={(e) => setReason(e.target.value as Reason)}>
                {REASONS.map((r) => (
                  <option key={r} value={r}>
                    {vi.review.reasons[r]}
                  </option>
                ))}
              </select>
            </div>
            <button type="button" className="btn" onClick={() => void decide("rejected")}>
              {vi.review.reject}
            </button>
            <div className="field">
              <label htmlFor={ids.relabel}>{vi.review.relabelLabel}</label>
              <select id={ids.relabel} value={relabelTo} onChange={(e) => setRelabelTo(e.target.value)}>
                {targets.map((item) => (
                  <option key={item.gloss_id} value={item.gloss_id}>
                    {item.gloss_id}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              className="btn"
              disabled={relabelTo === current.label}
              onClick={() => void decide("relabelled")}
            >
              {vi.review.relabel}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
