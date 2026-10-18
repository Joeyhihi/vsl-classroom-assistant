// Every message unit shows an icon (UX_AND_ACCESSIBILITY.md, literacy). The
// vocabulary names an icon; these emoji stand in until experts supply pictograms.

const ICONS: Record<string, string> = {
  hand: "✋",
  wave: "👋",
  thanks: "🙏",
  repeat: "🔁",
  rest: "💤",
  pause: "⏸️",
  question: "❓",
  circle: "⭕",
  push: "👉",
  yes: "👍",
  no: "👎",
  help: "🆘",
  toilet: "🚻",
  water: "💧",
  book: "📖",
  write: "✍️",
};

export const DEFAULT_ICON = "✋";

export function iconFor(name: string | undefined): string {
  return (name && ICONS[name]) || DEFAULT_ICON;
}
