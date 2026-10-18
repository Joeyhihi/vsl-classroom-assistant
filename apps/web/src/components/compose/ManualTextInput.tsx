import { useId, useState, type FormEvent, type KeyboardEvent } from "react";

import { MAX_MESSAGE_LENGTH, normalizeMessage, type TranscriptEntry } from "../../features/transcript/transcriptStore";
import { vi } from "../../i18n/vi";

type Speaker = TranscriptEntry["speaker"];

interface Props {
  canSpeak: boolean;
  onSubmit: (text: string, speaker: Speaker, speak: boolean) => void;
}

/** Fallback communication: works with no camera, no backend and no model (FR-9). */
export function ManualTextInput({ canSpeak, onSubmit }: Props) {
  const [text, setText] = useState("");
  const [speaker, setSpeaker] = useState<Speaker>("student");
  const inputId = useId();
  const hintId = useId();
  const isEmpty = normalizeMessage(text) === "";

  const submit = (speak: boolean) => {
    if (isEmpty) return;
    onSubmit(text, speaker, speak && canSpeak);
    setText("");
  };

  const onFormSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit(false);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit(false);
    }
  };

  return (
    <section className="card" aria-labelledby="compose-heading">
      <h2 id="compose-heading">{vi.compose.heading}</h2>
      <form onSubmit={onFormSubmit}>
        <fieldset className="speaker">
          <legend>{vi.compose.speakerLegend}</legend>
          {(["student", "teacher"] as const).map((s) => (
            <label key={s} className="speaker__option">
              <input
                type="radio"
                name="speaker"
                value={s}
                checked={speaker === s}
                onChange={() => setSpeaker(s)}
              />
              {vi.speakers[s]}
            </label>
          ))}
        </fieldset>
        <div className="field">
          <label htmlFor={inputId}>{vi.compose.label}</label>
          <textarea
            id={inputId}
            value={text}
            maxLength={MAX_MESSAGE_LENGTH}
            rows={3}
            placeholder={vi.compose.placeholder}
            aria-describedby={hintId}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <p id={hintId} className="hint">
            {vi.compose.enterHint} {vi.compose.counter(text.length, MAX_MESSAGE_LENGTH)}
          </p>
        </div>
        <div className="row">
          <button type="submit" className="btn" disabled={isEmpty}>
            {vi.compose.send}
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={isEmpty || !canSpeak}
            onClick={() => submit(true)}
          >
            {vi.compose.sendAndSpeak}
          </button>
        </div>
      </form>
    </section>
  );
}
