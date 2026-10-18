import { transcriptToText, type TranscriptEntry } from "../../features/transcript/transcriptStore";
import { vi } from "../../i18n/vi";

interface Props {
  entries: readonly TranscriptEntry[];
  canSpeak: boolean;
  speakingId: string | null;
  onSpeak: (entry: TranscriptEntry) => void;
  onClear: () => void;
}

const timeFormat = new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" });

function exportTranscript(entries: readonly TranscriptEntry[]) {
  const blob = new Blob([transcriptToText(entries, vi.speakers)], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `hoi-thoai-${new Date().toISOString().slice(0, 10)}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

export function TranscriptPanel({ entries, canSpeak, speakingId, onSpeak, onClear }: Props) {
  return (
    <section className="card transcript" aria-labelledby="transcript-heading">
      <h2 id="transcript-heading">{vi.transcript.heading}</h2>
      <p className="hint">{vi.transcript.memoryNote}</p>

      <div className="transcript__log" role="log" aria-live="polite" aria-labelledby="transcript-heading">
        {entries.length === 0 && <p className="transcript__empty">{vi.transcript.empty}</p>}
        <ol className="transcript__list">
          {entries.map((entry) => (
            <li key={entry.id} className={`transcript__entry transcript__entry--${entry.speaker}`}>
              <div className="transcript__meta">
                <strong>{vi.speakers[entry.speaker]}</strong>
                <span>
                  {vi.transcript.sources[entry.source]} ·{" "}
                  <time dateTime={entry.created_at}>{timeFormat.format(new Date(entry.created_at))}</time>
                </span>
                {entry.spoken && <span className="badge">{vi.transcript.spoken}</span>}
              </div>
              <p className="transcript__text" lang="vi">
                {entry.text}
              </p>
              <button
                type="button"
                className="btn btn--small"
                disabled={!canSpeak || speakingId === entry.id}
                aria-label={vi.transcript.speakLabel(entry.text)}
                onClick={() => onSpeak(entry)}
              >
                <span aria-hidden="true">🔊</span> {vi.transcript.speak}
              </button>
            </li>
          ))}
        </ol>
      </div>

      {entries.length > 0 && (
        <div className="row">
          <button type="button" className="btn" onClick={() => exportTranscript(entries)}>
            {vi.transcript.export}
          </button>
          <button type="button" className="btn" onClick={onClear}>
            {vi.transcript.clear}
          </button>
        </div>
      )}
    </section>
  );
}
