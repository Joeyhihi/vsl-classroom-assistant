import { BackendStatus } from "./components/system/BackendStatus";
import { useBackendHealth } from "./features/health/useBackendHealth";
import { vi } from "./i18n/vi";

export function App() {
  const backend = useBackendHealth();
  const isMock = backend.kind === "online" && backend.health.model_mode === "mock";

  return (
    <div className="app">
      <header className="app__header">
        <h1>{vi.appTitle}</h1>
        {isMock && (
          <span className="badge badge--mock" title={vi.mockBadgeLabel}>
            {vi.mockBadge}
            <span className="visually-hidden">: {vi.mockBadgeLabel}</span>
          </span>
        )}
      </header>
      <main className="app__main">
        <p className="tagline">{vi.appTagline}</p>
        <p className="notice">{vi.phaseNotice}</p>
        <BackendStatus state={backend} />
      </main>
    </div>
  );
}
