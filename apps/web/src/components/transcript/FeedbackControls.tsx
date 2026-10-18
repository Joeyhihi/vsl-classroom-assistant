import { useId, useState } from "react";

import type { VocabularyEntry } from "../../api/generated/contracts";
import type { FeedbackVerdict, TranscriptEntry } from "../../features/transcript/transcriptStore";
import { vi } from "../../i18n/vi";

interface Props {
  entry: TranscriptEntry;
  vocabulary: readonly VocabularyEntry[];
  onSend: (entry: TranscriptEntry, verdict: FeedbackVerdict, expected: string | null) => Promise<void>;
}

/** "Was this right?" for one confirmed sign (FR-13). No free text, by design. */
export function FeedbackControls({ entry, vocabulary, onSend }: Props) {
  const selectId = useId();
  const [choosing, setChoosing] = useState(false);
  const [expected, setExpected] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  if (entry.feedback) {
    return <p className="hint feedback__done">{vi.feedback.thanks(vi.feedback.verdicts[entry.feedback])}</p>;
  }

  const send = (verdict: FeedbackVerdict, expectedGloss: string | null) => {
    setBusy(true);
    setFailed(false);
    onSend(entry, verdict, expectedGloss)
      .catch(() => setFailed(true))
      .finally(() => setBusy(false));
  };

  const others = vocabulary.filter((v) => v.gloss_id !== entry.gloss_id);
  return (
    <div className="feedback" role="group" aria-label={vi.feedback.groupLabel(entry.text)}>
      {!choosing ? (
        <div className="row">
          <span className="hint">{vi.feedback.question}</span>
          <button type="button" className="btn btn--small" disabled={busy} onClick={() => send("correct", null)}>
            <span aria-hidden="true">✓</span> {vi.feedback.verdicts.correct}
          </button>
          <button type="button" className="btn btn--small" disabled={busy} onClick={() => setChoosing(true)}>
            <span aria-hidden="true">✗</span> {vi.feedback.verdicts.incorrect}
          </button>
          <button type="button" className="btn btn--small" disabled={busy} onClick={() => send("unsure", null)}>
            <span aria-hidden="true">?</span> {vi.feedback.verdicts.unsure}
          </button>
        </div>
      ) : (
        <div className="row">
          <label htmlFor={selectId}>{vi.feedback.expectedLabel}</label>
          <select id={selectId} value={expected} onChange={(e) => setExpected(e.target.value)}>
            <option value="">{vi.feedback.expectedUnknown}</option>
            {others.map((v) => (
              <option key={v.gloss_id} value={v.gloss_id} lang="vi">
                {v.text_vi}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn btn--small btn--primary"
            disabled={busy}
            onClick={() => send("incorrect", expected || null)}
          >
            {vi.feedback.send}
          </button>
          <button type="button" className="btn btn--small" disabled={busy} onClick={() => setChoosing(false)}>
            {vi.feedback.cancel}
          </button>
        </div>
      )}
      {failed && (
        <p className="hint" role="alert">
          {vi.feedback.failed}
        </p>
      )}
    </div>
  );
}
