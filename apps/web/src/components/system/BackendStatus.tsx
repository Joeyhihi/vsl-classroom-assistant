import type { BackendHealthState } from "../../features/health/useBackendHealth";
import { vi } from "../../i18n/vi";
import { StatusLine, type Tone } from "../ui/StatusLine";

function summary(state: BackendHealthState): { tone: Tone; text: string } {
  switch (state.kind) {
    case "checking":
      return { tone: "info", text: vi.backend.checking };
    case "offline":
      return { tone: "danger", text: vi.backend.offline };
    case "incompatible":
      return { tone: "danger", text: vi.backend.incompatible };
    case "online":
      return state.health.status === "ok"
        ? { tone: "success", text: vi.backend.online }
        : { tone: "warning", text: vi.backend.degraded };
  }
}

export function BackendStatus({ state }: { state: BackendHealthState }) {
  const { tone, text } = summary(state);
  const health = state.kind === "online" ? state.health : null;

  return (
    <section className="card" aria-labelledby="backend-heading">
      <h2 id="backend-heading">{vi.backend.heading}</h2>
      <div role="status" aria-live="polite">
        <StatusLine tone={tone} text={text} />
      </div>
      {state.kind === "offline" && <p className="hint mono">{vi.backend.offlineHelp}</p>}
      {health && (
        <dl className="components">
          {(Object.keys(vi.components) as (keyof typeof vi.components)[]).map((key) => (
            <div key={key} className="components__row">
              <dt>{vi.components[key]}</dt>
              <dd>{vi.componentStatus[health.components[key].status]}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
