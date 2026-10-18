import { useEffect, useState } from "react";

import { ApiError, fetchHealth } from "../../api/http";
import type { HealthResponse } from "../../api/types";

export const HEALTH_POLL_MS = 10_000;

export type BackendHealthState =
  | { kind: "checking" }
  | { kind: "online"; health: HealthResponse }
  | { kind: "offline" }
  | { kind: "incompatible" };

/** Polls GET /health; manual text and TTS must keep working when offline. */
export function useBackendHealth(pollMs: number = HEALTH_POLL_MS): BackendHealthState {
  const [state, setState] = useState<BackendHealthState>({ kind: "checking" });

  useEffect(() => {
    const controller = new AbortController();

    const check = async () => {
      try {
        const health = await fetchHealth(controller.signal);
        setState({ kind: "online", health });
      } catch (error) {
        if (controller.signal.aborted) return;
        const incompatible = error instanceof ApiError && error.kind === "invalid_response";
        setState({ kind: incompatible ? "incompatible" : "offline" });
      }
    };

    void check();
    const timer = setInterval(() => void check(), pollMs);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [pollMs]);

  return state;
}
