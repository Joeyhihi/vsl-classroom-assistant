import { useCallback, useEffect, useState } from "react";

import type { Settings } from "../settings/settingsStore";
import { pickVoice, usableVoices } from "./speechSynthesis";

// Chrome fills getVoices() asynchronously; give up waiting after this long.
const VOICE_LOAD_TIMEOUT_MS = 1500;

export type TtsAvailability = "unsupported" | "loading" | "no_voice" | "ready";

export interface TtsState {
  availability: TtsAvailability;
  allVoices: SpeechSynthesisVoice[];
  voice: SpeechSynthesisVoice | null;
  speakingId: string | null;
}

function synth(): SpeechSynthesis | null {
  return typeof window !== "undefined" && "speechSynthesis" in window
    ? window.speechSynthesis
    : null;
}

export function useTts(settings: Settings) {
  const [allVoices, setAllVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [speakingId, setSpeakingId] = useState<string | null>(null);

  useEffect(() => {
    const s = synth();
    if (!s) return;
    const refresh = () => {
      const voices = s.getVoices();
      setAllVoices(voices);
      if (voices.length > 0) setLoaded(true);
    };
    refresh();
    s.addEventListener("voiceschanged", refresh);
    const timer = setTimeout(() => setLoaded(true), VOICE_LOAD_TIMEOUT_MS);
    return () => {
      s.removeEventListener("voiceschanged", refresh);
      clearTimeout(timer);
      s.cancel();
    };
  }, []);

  const voice = pickVoice(allVoices, settings.voiceURI, settings.allowNetworkVoices);
  const availability: TtsAvailability = !synth()
    ? "unsupported"
    : voice
      ? "ready"
      : loaded
        ? "no_voice"
        : "loading";

  const speak = useCallback(
    (text: string, id: string, onDone?: () => void): boolean => {
      const s = synth();
      if (!s || !voice) return false;
      s.cancel(); // one utterance at a time
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.voice = voice;
      utterance.lang = voice.lang;
      utterance.rate = settings.speechRate;
      utterance.onstart = () => setSpeakingId(id);
      utterance.onend = () => {
        setSpeakingId((current) => (current === id ? null : current));
        onDone?.();
      };
      utterance.onerror = () => setSpeakingId((current) => (current === id ? null : current));
      setSpeakingId(id);
      s.speak(utterance);
      return true;
    },
    [voice, settings.speechRate],
  );

  const cancel = useCallback(() => {
    synth()?.cancel();
    setSpeakingId(null);
  }, []);

  const state: TtsState = { availability, allVoices, voice, speakingId };
  return {
    ...state,
    usable: usableVoices(allVoices, settings.allowNetworkVoices),
    speak,
    cancel,
  };
}

export type TtsController = ReturnType<typeof useTts>;
