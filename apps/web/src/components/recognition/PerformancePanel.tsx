import { useId, useState } from "react";

import { fetchDiagnostics } from "../../api/http";
import type { ExtractionLevel } from "../../features/metrics/ladder";
import type { RecognitionController } from "../../features/recognition/useRecognitionSession";
import { vi } from "../../i18n/vi";

interface Props {
  controller: RecognitionController;
  level: ExtractionLevel;
  onLevelChange: (level: ExtractionLevel) => void;
}

const fmt = (v: number | null | undefined, unit: string, digits = 0) =>
  v === null || v === undefined ? vi.performance.none : `${v.toFixed(digits)} ${unit}`;

function jsHeapMb(): number | null {
  // Chrome-only, approximate; enough to spot leaks during the P3 benchmark.
  const memory = (performance as Performance & { memory?: { usedJSHeapSize: number } }).memory;
  return memory ? memory.usedJSHeapSize / 2 ** 20 : null;
}

/** Diagnostics for the Windows P3 benchmark: fps, latency, memory, ladder level. */
export function PerformancePanel({ controller, level, onLevelChange }: Props) {
  const { metrics, state } = controller;
  const levelId = useId();
  const [backendRss, setBackendRss] = useState<number | null>(null);
  const [heap, setHeap] = useState<number | null>(jsHeapMb);

  const refresh = () => {
    setHeap(jsHeapMb());
    fetchDiagnostics()
      .then((d) => setBackendRss(d.rss_mb))
      .catch(() => setBackendRss(null));
  };

  return (
    <section className="card" aria-labelledby="performance-heading">
      <h3 id="performance-heading">{vi.performance.heading}</h3>
      <div className="field">
        <label htmlFor={levelId}>{vi.performance.levelHeading}</label>
        <select id={levelId} value={level} onChange={(e) => onLevelChange(e.target.value as ExtractionLevel)}>
          {(["L1", "L2", "L3"] as const).map((l) => (
            <option key={l} value={l}>
              {vi.performance.levels[l]}
            </option>
          ))}
        </select>
        <p className="hint">{vi.performance.levelHint}</p>
      </div>
      {state.phase !== "running" && <p className="hint">{vi.performance.notRunning}</p>}
      <dl className="components" data-testid="performance-metrics">
        <div className="components__row">
          <dt>{vi.performance.fps}</dt>
          <dd>{fmt(metrics.fps, "fps", 1)}</dd>
        </div>
        <div className="components__row">
          <dt>{vi.performance.latency}</dt>
          <dd>
            {fmt(metrics.latency.p50, "ms")} / {fmt(metrics.latency.p95, "ms")} (n={metrics.latency.count})
          </dd>
        </div>
        <div className="components__row">
          <dt>{vi.performance.inference}</dt>
          <dd>{fmt(metrics.inferenceMs, "ms", 1)}</dd>
        </div>
        <div className="components__row">
          <dt>{vi.performance.source}</dt>
          <dd>{metrics.sourceDetail}</dd>
        </div>
        <div className="components__row">
          <dt>{vi.performance.dropped}</dt>
          <dd>{state.droppedFrames}</dd>
        </div>
        <div className="components__row">
          <dt>{vi.performance.heap}</dt>
          <dd>{fmt(heap, "MB")}</dd>
        </div>
        <div className="components__row">
          <dt>{vi.performance.backendRss}</dt>
          <dd>{fmt(backendRss, "MB")}</dd>
        </div>
      </dl>
      <button type="button" className="btn" onClick={refresh}>
        {vi.performance.refresh}
      </button>
    </section>
  );
}
