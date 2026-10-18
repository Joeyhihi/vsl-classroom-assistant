import type { PredictionMessage, ScoredLabelWire } from "../../api/generated/contracts";
import { alternatives } from "../../features/recognition/recognitionMachine";
import { iconFor } from "../../features/vocabulary/icons";
import { vi } from "../../i18n/vi";
import { StatusLine } from "../ui/StatusLine";

interface Props {
  candidate: PredictionMessage | null;
  lastRejected: PredictionMessage | null;
  skipped: PredictionMessage[];
  speechBlocked: boolean;
  onConfirm: (label: ScoredLabelWire, prediction: PredictionMessage) => void;
  onDismiss: () => void;
}

/** Candidate text ≥32 px with icon; confirm before anything reaches the transcript. */
export function PredictionCard({ candidate, lastRejected, skipped, speechBlocked, onConfirm, onDismiss }: Props) {
  const top = candidate?.top[0];
  return (
    <div className="prediction" aria-live="polite">
      {candidate && top && candidate.status === "confident" && (
        <div className="prediction__card prediction__card--confident" data-testid="prediction-candidate">
          <p className="prediction__text" lang="vi">
            <span className="prediction__icon" aria-hidden="true">
              {iconFor(top.icon)}
            </span>{" "}
            {top.text_vi}
          </p>
          <p className="hint">{vi.candidate.confidence(top.score)}</p>
          <div className="row">
            <button type="button" className="btn btn--primary" onClick={() => onConfirm(top, candidate)}>
              {vi.candidate.confirm}
            </button>
            <button type="button" className="btn" onClick={onDismiss}>
              {vi.candidate.dismiss}
            </button>
          </div>
        </div>
      )}

      {candidate && candidate.status === "uncertain" && (
        <div className="prediction__card prediction__card--uncertain" data-testid="prediction-candidate">
          <StatusLine tone="warning" text={vi.candidate.uncertainPrompt} icon="?" />
          <div className="row">
            {alternatives(candidate).map((label) => (
              <button
                key={label.gloss_id}
                type="button"
                className="btn"
                aria-label={vi.candidate.choose(label.text_vi)}
                onClick={() => onConfirm(label, candidate)}
              >
                <span aria-hidden="true">{iconFor(label.icon)}</span> <span lang="vi">{label.text_vi}</span>
              </button>
            ))}
            <button type="button" className="btn" onClick={onDismiss}>
              {vi.candidate.dismiss}
            </button>
          </div>
        </div>
      )}

      {!candidate && lastRejected && (
        <div data-testid="prediction-rejected">
          <StatusLine tone="info" text={vi.candidate.rejected} icon="✖" />
        </div>
      )}

      {speechBlocked && candidate && <p className="hint">{vi.candidate.mockNoSpeech}</p>}

      {skipped.length > 0 && (
        <details className="skipped">
          <summary>
            {vi.candidate.skippedHeading} ({skipped.length})
          </summary>
          <ul>
            {skipped.map((p) => (
              <li key={p.prediction_id} lang="vi">
                {p.top[0]?.text_vi}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
