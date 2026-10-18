// Maps getUserMedia failures to the user-facing camera states
// (docs/ARCHITECTURE.md § Failure modes).

export type CameraFailure = "denied" | "unavailable" | "in_use" | "insecure" | "error";

export function classifyCameraError(error: unknown): CameraFailure {
  const name = error instanceof DOMException || error instanceof Error ? error.name : "";
  switch (name) {
    case "NotAllowedError":
    case "PermissionDeniedError":
      return "denied";
    case "NotFoundError":
    case "DevicesNotFoundError":
    case "OverconstrainedError":
      return "unavailable";
    case "NotReadableError":
    case "TrackStartError":
    case "AbortError":
      return "in_use";
    case "SecurityError":
      return "insecure";
    default:
      return "error";
  }
}
