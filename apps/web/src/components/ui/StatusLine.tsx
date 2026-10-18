export type Tone = "info" | "success" | "warning" | "danger" | "active";

// Status is always text + icon + colour, never colour or sound alone.
const ICONS: Record<Tone, string> = { info: "⏳", success: "✔", warning: "⚠", danger: "✖", active: "●" };

export function StatusLine({ tone, text, icon }: { tone: Tone; text: string; icon?: string }) {
  return (
    <p className={`status status--${tone}`}>
      <span aria-hidden="true">{icon ?? ICONS[tone]}</span> {text}
    </p>
  );
}
