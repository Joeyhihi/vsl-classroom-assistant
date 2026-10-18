import type { TtsController } from "../../features/tts/useTts";
import { vi } from "../../i18n/vi";
import { StatusLine } from "../ui/StatusLine";

/** Visible playback state and voice problems — never sound alone. */
export function TtsStatus({ tts }: { tts: TtsController }) {
  return (
    <div role="status" aria-live="polite" className="tts-status">
      {tts.speakingId && (
        <div className="row speaking" data-testid="speaking-indicator">
          <StatusLine tone="active" text={vi.tts.speaking} icon="🔊" />
          <button type="button" className="btn btn--small" onClick={tts.cancel}>
            {vi.tts.stop}
          </button>
        </div>
      )}
      {tts.availability === "loading" && <StatusLine tone="info" text={vi.tts.loading} />}
      {tts.availability === "unsupported" && <StatusLine tone="warning" text={vi.tts.unsupported} />}
      {tts.availability === "no_voice" && (
        <div className="notice notice--warning">
          <StatusLine tone="warning" text={vi.tts.noVoice} />
          <p className="hint">{vi.tts.installHelp.mac}</p>
          <p className="hint">{vi.tts.installHelp.windows}</p>
        </div>
      )}
    </div>
  );
}
