import type { KeyboardEvent } from "react";

import type { ComponentHealth } from "../../api/generated/contracts";
import type { PushToTalkController } from "../../features/stt/usePushToTalk";
import { MAX_RECORDING_S } from "../../features/stt/wav";
import { errorMessages, vi } from "../../i18n/vi";
import { StatusLine } from "../ui/StatusLine";

interface Props {
  health: ComponentHealth;
  ptt: PushToTalkController;
}

/** Teacher speech → subtitles (P7, gated). Hold the button (or Space) while speaking. */
export function SubtitlePanel({ health, ptt }: Props) {
  const ready = health.status === "ready";
  const { state } = ptt;
  const busy = state.kind === "starting" || state.kind === "transcribing";

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if ((event.key === " " || event.key === "Enter") && !event.repeat) {
      event.preventDefault();
      ptt.press();
    }
  };
  const onKeyUp = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      ptt.release();
    }
  };

  return (
    <section className="card subtitles" aria-labelledby="subtitles-heading">
      <h2 id="subtitles-heading">{vi.stt.heading}</h2>
      <p className="hint">{vi.stt.intro(MAX_RECORDING_S)}</p>
      {!ready && (
        <StatusLine tone="warning" icon="🎤" text={vi.stt.unavailable(health.detail ?? vi.stt.noReason)} />
      )}
      <button
        type="button"
        className={`btn btn--primary btn--ptt${state.kind === "listening" ? " btn--ptt-active" : ""}`}
        disabled={!ready || state.kind === "transcribing"}
        aria-pressed={state.kind === "listening" || state.kind === "starting"}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture?.(e.pointerId);
          ptt.press();
        }}
        onPointerUp={ptt.release}
        onPointerCancel={ptt.release}
        onKeyDown={onKeyDown}
        onKeyUp={onKeyUp}
        onContextMenu={(e) => e.preventDefault()}
      >
        <span aria-hidden="true">🎤</span> {state.kind === "listening" ? vi.stt.listening : vi.stt.hold}
      </button>
      <div aria-live="polite">
        {state.kind === "listening" && <StatusLine tone="info" icon="●" text={vi.stt.listening} />}
        {busy && <StatusLine tone="info" icon="…" text={state.kind === "starting" ? vi.stt.starting : vi.stt.transcribing} />}
        {state.kind === "error" && (
          <StatusLine tone="warning" icon="!" text={vi.stt.errors[state.code] ?? errorMessages[state.code] ?? vi.stt.errorGeneric} />
        )}
        {ptt.lastText && (
          <p className="subtitles__text" lang="vi" data-testid="subtitle-text">
            {ptt.lastText}
          </p>
        )}
      </div>
    </section>
  );
}
