import { describe, expect, it } from "vitest";

import { LOCAL_EN, LOCAL_VI, NETWORK_VI } from "../../test/fakeSpeech";
import { isVietnamese, partitionVietnameseVoices, pickVoice, usableVoices } from "./speechSynthesis";

const voices = [LOCAL_EN, NETWORK_VI, LOCAL_VI];

describe("voice selection", () => {
  it("recognises vi, vi-VN and vi_VN", () => {
    expect(["vi", "vi-VN", "vi_VN", "VI-vn"].every((lang) => isVietnamese({ lang }))).toBe(true);
    expect(isVietnamese({ lang: "en-US" })).toBe(false);
  });

  it("separates local and network Vietnamese voices", () => {
    expect(partitionVietnameseVoices(voices)).toEqual({ local: [LOCAL_VI], network: [NETWORK_VI] });
  });

  it("excludes network voices unless allowed (privacy default)", () => {
    expect(usableVoices(voices, false)).toEqual([LOCAL_VI]);
    expect(usableVoices(voices, true)).toEqual([LOCAL_VI, NETWORK_VI]);
  });

  it("never picks a non-Vietnamese voice", () => {
    expect(pickVoice([LOCAL_EN], null, true)).toBeNull();
  });

  it("honours the preferred voice only while it is usable", () => {
    expect(pickVoice(voices, NETWORK_VI.voiceURI, true)).toBe(NETWORK_VI);
    expect(pickVoice(voices, NETWORK_VI.voiceURI, false)).toBe(LOCAL_VI);
    expect(pickVoice(voices, "gone", false)).toBe(LOCAL_VI);
  });
});
