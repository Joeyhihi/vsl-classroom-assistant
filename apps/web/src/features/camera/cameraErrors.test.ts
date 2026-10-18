import { describe, expect, it } from "vitest";

import { classifyCameraError } from "./cameraErrors";

describe("classifyCameraError", () => {
  it.each([
    ["NotAllowedError", "denied"],
    ["PermissionDeniedError", "denied"],
    ["NotFoundError", "unavailable"],
    ["OverconstrainedError", "unavailable"],
    ["NotReadableError", "in_use"],
    ["AbortError", "in_use"],
    ["SecurityError", "insecure"],
    ["TypeError", "error"],
  ])("maps %s to %s", (name, expected) => {
    expect(classifyCameraError(new DOMException("x", name))).toBe(expected);
  });

  it("treats non-errors as a generic failure", () => {
    expect(classifyCameraError("boom")).toBe("error");
    expect(classifyCameraError(undefined)).toBe("error");
  });
});
