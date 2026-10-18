import { Component, type ErrorInfo, type ReactNode } from "react";

import { vi } from "../i18n/vi";

interface State {
  failed: boolean;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(_error: Error, info: ErrorInfo) {
    // Component stack only; never log message content.
    console.error("UI error", info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="app" role="alert">
        <h1>{vi.errorBoundary.title}</h1>
        <p>{vi.errorBoundary.body}</p>
        <button type="button" className="btn btn--primary" onClick={() => window.location.reload()}>
          {vi.errorBoundary.reload}
        </button>
      </main>
    );
  }
}
