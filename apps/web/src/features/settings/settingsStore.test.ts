import { describe, expect, it } from "vitest";

import { DEFAULT_SETTINGS, parseSettings } from "./settingsStore";

describe("parseSettings", () => {
  it("returns defaults for missing or corrupt storage", () => {
    expect(parseSettings(null)).toEqual(DEFAULT_SETTINGS);
    expect(parseSettings("{not json")).toEqual(DEFAULT_SETTINGS);
    expect(parseSettings("42")).toEqual(DEFAULT_SETTINGS);
  });

  it("keeps valid fields and clamps the speech rate", () => {
    const parsed = parseSettings(
      JSON.stringify({
        preferredCameraId: "cam",
        voiceURI: "Linh",
        allowNetworkVoices: true,
        speechRate: 9,
        extractionLevel: "L2",
      }),
    );
    expect(parsed).toEqual({
      preferredCameraId: "cam",
      voiceURI: "Linh",
      allowNetworkVoices: true,
      speechRate: 2,
      extractionLevel: "L2",
    });
  });

  it("never enables network voices from a non-boolean value", () => {
    expect(parseSettings(JSON.stringify({ allowNetworkVoices: "yes" })).allowNetworkVoices).toBe(false);
  });

  it("rejects unknown extraction levels", () => {
    expect(parseSettings(JSON.stringify({ extractionLevel: "L9" })).extractionLevel).toBe("L1");
  });

  it("drops wrongly typed and unknown fields", () => {
    const parsed = parseSettings(JSON.stringify({ preferredCameraId: 5, transcript: ["secret"] }));
    expect(parsed).toEqual(DEFAULT_SETTINGS);
  });
});
