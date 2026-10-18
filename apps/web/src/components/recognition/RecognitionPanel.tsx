import type { PredictionMessage, ScoredLabelWire } from "../../api/generated/contracts";
import type { LadderVerdict } from "../../features/metrics/ladder";
import { canSpeakPrediction, type RecognitionState } from "../../features/recognition/recognitionMachine";
import type { RecognitionController, SourceKind } from "../../features/recognition/useRecognitionSession";
import { errorMessages, vi } from "../../i18n/vi";
import { StatusLine, type Tone } from "../ui/StatusLine";
import { LandmarkOverlay } from "./LandmarkOverlay";
import { PredictionCard } from "./PredictionCard";

interface Props {
  controller: RecognitionController;
  sourceKind: SourceKind;
  onConfirm: (label: ScoredLabelWire, prediction: PredictionMessage) => void;
  onAcceptL3: () => void;
}

function statusLine(state: RecognitionState): { tone: Tone; text: string } | null {
  switch (state.phase) {
    case "idle":
      return null;
    case "connecting":
      return { tone: "info", text: vi.recognition.state.connecting };
    case "paused":
      return { tone: "warning", text: vi.recognition.state.paused };
    case "reconnecting":
      return { tone: "warning", text: vi.recognition.state.reconnecting(state.reconnectAttempt) };
    case "failed": {
      const reason = state.failure ?? "";
      const code = reason.replace(/^CLOSE_\d+$/, "");
      const text = vi.recognition.failure[reason] ?? errorMessages[code] ?? vi.recognition.failureGeneric;
      return { tone: "danger", text };
    }
    case "running":
      if (state.serverState === "signing") return { tone: "active", text: vi.recognition.state.signing };
      if (state.serverState === "ready") return { tone: "success", text: vi.recognition.state.ready };
      return { tone: "warning", text: vi.recognition.state.waiting_for_hands };
  }
}

function LadderNotice({ ladder, onAcceptL3 }: { ladder: LadderVerdict; onAcceptL3: () => void }) {
  if (ladder.kind !== "too_slow") return null;
  const { next, fps } = ladder;
  return (
    <div className="notice notice--warning" role="status" data-testid="ladder-notice">
      {next.action === "auto_switch" && <p>{vi.ladder.autoSwitch(fps)}</p>}
      {next.action === "offer" && (
        <>
          <p>{vi.ladder.offerL3(fps)}</p>
          <button type="button" className="btn" onClick={onAcceptL3}>
            {vi.ladder.acceptL3}
          </button>
        </>
      )}
      {next.action === "unsupported" && <p>{vi.ladder.unsupported}</p>}
    </div>
  );
}

export function RecognitionPanel({ controller, sourceKind, onConfirm, onAcceptL3 }: Props) {
  const { state, ladder } = controller;
  const active = state.phase !== "idle" && state.phase !== "failed";
  const line = statusLine(state);

  return (
    <section className="card recognition" aria-labelledby="recognition-heading">
      <div className="row recognition__header">
        <h2 id="recognition-heading">{vi.recognition.heading}</h2>
        {sourceKind === "replay" && <span className="badge badge--replay">{vi.recognition.replayBadge}</span>}
        {state.model?.developer_only && state.model.kind !== "mock" && (
          <span className="badge badge--dev">{vi.recognition.devModelBadge}</span>
        )}
      </div>
      {sourceKind === "replay" && <p className="hint">{vi.recognition.replayNotice}</p>}

      <div className="row">
        {state.phase === "paused" ? (
          <button type="button" className="btn btn--primary" onClick={() => controller.start()}>
            {vi.recognition.resume}
          </button>
        ) : active ? (
          <button type="button" className="btn" onClick={controller.stop}>
            {vi.recognition.stop}
          </button>
        ) : (
          <button type="button" className="btn btn--primary" onClick={() => controller.start()}>
            {vi.recognition.start}
          </button>
        )}
      </div>

      <div role="status" aria-live="polite" data-testid="recognition-status">
        {line ? <StatusLine tone={line.tone} text={line.text} /> : <p className="hint">{vi.recognition.idleHint}</p>}
        {state.phase === "failed" && state.failureDetail && (
          <p className="hint mono" data-testid="failure-detail">
            {vi.recognition.failureDetail(state.failureDetail)}
          </p>
        )}
      </div>

      {active && <LandmarkOverlay frameRef={controller.lastFrame} />}

      <LadderNotice ladder={ladder} onAcceptL3={onAcceptL3} />

      <PredictionCard
        candidate={state.candidate}
        lastRejected={state.lastRejected}
        skipped={state.skipped}
        speechBlocked={!canSpeakPrediction(state.model)}
        onConfirm={onConfirm}
        onDismiss={controller.resolveCandidate}
      />
    </section>
  );
}
