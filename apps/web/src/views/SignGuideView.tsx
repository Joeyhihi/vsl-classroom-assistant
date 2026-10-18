import { iconFor } from "../features/vocabulary/icons";
import type { VocabularyState } from "../features/vocabulary/useVocabulary";
import { vi } from "../i18n/vi";

interface Props {
  vocabulary: VocabularyState;
  developerOnly: boolean;
}

/** The closed list of signs the current model recognises (honest UI: not translation). */
export function SignGuideView({ vocabulary, developerOnly }: Props) {
  return (
    <section className="card" aria-labelledby="guide-heading">
      <h2 id="guide-heading">{vi.guide.heading}</h2>
      <p className="hint">{vi.guide.intro}</p>
      {developerOnly && <p className="notice">{vi.guide.devNotice}</p>}

      {vocabulary.kind === "loading" && <p>{vi.guide.loading}</p>}
      {vocabulary.kind === "unavailable" && <p>{vi.guide.unavailable}</p>}
      {vocabulary.kind === "ready" && vocabulary.entries.length === 0 && <p>{vi.guide.empty}</p>}
      {vocabulary.kind === "ready" && vocabulary.entries.length > 0 && (
        <>
          <p className="hint">{vi.guide.count(vocabulary.entries.length, vocabulary.version)}</p>
          <ul className="guide__grid">
            {vocabulary.entries.map((entry) => (
              <li key={entry.gloss_id} className="guide__item">
                <span className="guide__icon" aria-hidden="true">
                  {iconFor(entry.icon)}
                </span>
                <span className="guide__text" lang="vi">
                  {entry.text_vi}
                </span>
                <span className="guide__gloss">{entry.gloss_id}</span>
              </li>
            ))}
          </ul>
          <p className="hint">{vi.guide.clipsLater}</p>
        </>
      )}
    </section>
  );
}
