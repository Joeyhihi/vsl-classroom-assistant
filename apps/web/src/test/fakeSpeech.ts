// Minimal speechSynthesis double for jsdom (which has none).
import type { VoiceLike } from "../features/tts/speechSynthesis";

export const LOCAL_VI: VoiceLike = { voiceURI: "Linh", name: "Linh", lang: "vi-VN", localService: true };
export const NETWORK_VI: VoiceLike = {
  voiceURI: "Google Tiếng Việt",
  name: "Google Tiếng Việt",
  lang: "vi-VN",
  localService: false,
};
export const LOCAL_EN: VoiceLike = { voiceURI: "Samantha", name: "Samantha", lang: "en-US", localService: true };

class FakeUtterance {
  text: string;
  voice: VoiceLike | null = null;
  lang = "";
  rate = 1;
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(text: string) {
    this.text = text;
  }
}

export interface FakeSpeech {
  spoken: FakeUtterance[];
  /** Simulate the end of the current utterance. */
  finish: () => void;
  uninstall: () => void;
}

export function installFakeSpeech(voices: VoiceLike[]): FakeSpeech {
  const spoken: FakeUtterance[] = [];
  let current: FakeUtterance | null = null;
  const target = new EventTarget();
  const synth = {
    getVoices: () => voices,
    speak: (u: FakeUtterance) => {
      spoken.push(u);
      current = u;
      u.onstart?.();
    },
    cancel: () => {
      current = null;
    },
    addEventListener: target.addEventListener.bind(target),
    removeEventListener: target.removeEventListener.bind(target),
  };
  Object.defineProperty(window, "speechSynthesis", { value: synth, configurable: true });
  Object.defineProperty(window, "SpeechSynthesisUtterance", { value: FakeUtterance, configurable: true });
  return {
    spoken,
    finish: () => {
      const u = current;
      current = null;
      u?.onend?.();
    },
    uninstall: () => {
      Reflect.deleteProperty(window, "speechSynthesis");
      Reflect.deleteProperty(window, "SpeechSynthesisUtterance");
    },
  };
}
