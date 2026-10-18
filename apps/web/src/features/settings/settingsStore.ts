import { useCallback, useState } from "react";

// Per-browser preferences only (docs/SECURITY_AND_PRIVACY.md §1). Never
// transcript text or anything about other people.
export interface Settings {
  preferredCameraId: string | null;
  voiceURI: string | null;
  /** Network voices send text to a cloud service; off by default (ADR-010). */
  allowNetworkVoices: boolean;
  speechRate: number;
}

export const SETTINGS_KEY = "vsl.settings.v1";

export const DEFAULT_SETTINGS: Settings = {
  preferredCameraId: null,
  voiceURI: null,
  allowNetworkVoices: false,
  speechRate: 1,
};

export const SPEECH_RATE_MIN = 0.5;
export const SPEECH_RATE_MAX = 2;

const nullableString = (v: unknown): string | null => (typeof v === "string" && v ? v : null);

/** Parse untrusted storage content; unknown or invalid fields fall back to defaults. */
export function parseSettings(raw: string | null): Settings {
  if (!raw) return DEFAULT_SETTINGS;
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return DEFAULT_SETTINGS;
  }
  if (typeof data !== "object" || data === null) return DEFAULT_SETTINGS;
  const d = data as Record<string, unknown>;
  const rate = typeof d.speechRate === "number" ? d.speechRate : DEFAULT_SETTINGS.speechRate;
  return {
    preferredCameraId: nullableString(d.preferredCameraId),
    voiceURI: nullableString(d.voiceURI),
    allowNetworkVoices: d.allowNetworkVoices === true,
    speechRate: Math.min(SPEECH_RATE_MAX, Math.max(SPEECH_RATE_MIN, rate)),
  };
}

function load(): Settings {
  try {
    return parseSettings(window.localStorage.getItem(SETTINGS_KEY));
  } catch {
    return DEFAULT_SETTINGS; // storage blocked (private mode, policy)
  }
}

function save(settings: Settings) {
  try {
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // Not persisted; the in-memory value still applies for this session.
  }
}

export function clearStoredSettings() {
  try {
    window.localStorage.removeItem(SETTINGS_KEY);
  } catch {
    // nothing stored
  }
}

export function useSettings() {
  const [settings, setSettings] = useState<Settings>(load);

  const update = useCallback((patch: Partial<Settings>) => {
    setSettings((current) => {
      const next = { ...current, ...patch };
      save(next);
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    clearStoredSettings();
    setSettings(DEFAULT_SETTINGS);
  }, []);

  return { settings, update, reset };
}
