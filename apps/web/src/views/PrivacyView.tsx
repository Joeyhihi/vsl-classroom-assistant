import { vi } from "../i18n/vi";

export function PrivacyView() {
  return (
    <section className="card" aria-labelledby="privacy-heading">
      <h2 id="privacy-heading">{vi.privacy.heading}</h2>
      <ul className="privacy-list">
        {vi.privacy.points.map((point) => (
          <li key={point}>{point}</li>
        ))}
      </ul>
    </section>
  );
}
