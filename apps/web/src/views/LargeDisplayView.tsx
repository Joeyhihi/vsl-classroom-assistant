import { useRef, useState } from "react";

import type { TranscriptEntry } from "../features/transcript/transcriptStore";
import { iconFor } from "../features/vocabulary/icons";
import { vi } from "../i18n/vi";

interface Props {
  entries: readonly TranscriptEntry[];
}

/** The last confirmed message, very large, for the teacher across the room. */
export function LargeDisplayView({ entries }: Props) {
  const ref = useRef<HTMLElement>(null);
  const [fullscreenFailed, setFullscreenFailed] = useState(false);
  const last = [...entries].reverse().find((e) => e.confirmed);

  const goFullscreen = () => {
    const element = ref.current;
    if (!element?.requestFullscreen) {
      setFullscreenFailed(true);
      return;
    }
    element.requestFullscreen().catch(() => setFullscreenFailed(true));
  };

  return (
    <section ref={ref} className="large-display" aria-labelledby="large-heading">
      <h2 id="large-heading" className="visually-hidden">
        {vi.largeDisplay.heading}
      </h2>
      <div className="large-display__message" aria-live="polite" data-testid="large-display-message">
        {last ? (
          <>
            <p className="large-display__speaker">
              {vi.speakers[last.speaker]} · {vi.transcript.sources[last.source]}
            </p>
            <p className="large-display__text" lang="vi">
              {last.source === "sign" && (
                <span className="large-display__icon" aria-hidden="true">
                  {iconFor(last.icon)}{" "}
                </span>
              )}
              {last.text}
            </p>
          </>
        ) : (
          <p className="large-display__empty">{vi.largeDisplay.empty}</p>
        )}
      </div>
      <div className="row large-display__controls">
        <button type="button" className="btn" onClick={goFullscreen}>
          {vi.largeDisplay.fullscreen}
        </button>
        <span className="hint">{vi.largeDisplay.exitHint}</span>
      </div>
      {fullscreenFailed && <p className="hint">{vi.largeDisplay.fullscreenFailed}</p>}
    </section>
  );
}
