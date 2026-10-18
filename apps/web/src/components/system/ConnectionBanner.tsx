import type { BackendHealthState } from "../../features/health/useBackendHealth";
import { vi } from "../../i18n/vi";

/** Shown on every view while the backend is unreachable or incompatible. */
export function ConnectionBanner({ state }: { state: BackendHealthState }) {
  if (state.kind !== "offline" && state.kind !== "incompatible") return null;
  return (
    <div className="banner banner--danger" role="alert" data-testid="connection-banner">
      <span aria-hidden="true">✖</span> {vi.connectionBanner[state.kind]}
    </div>
  );
}
