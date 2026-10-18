// Voice selection for browser speechSynthesis (ADR-010).
// Only voices with localService === true run on this computer; others send the
// text to a cloud service and are excluded unless the user opts in.

export interface VoiceLike {
  voiceURI: string;
  name: string;
  lang: string;
  localService: boolean;
  default?: boolean;
}

export function isVietnamese(voice: Pick<VoiceLike, "lang">): boolean {
  return voice.lang.replace("_", "-").toLowerCase().split("-")[0] === "vi";
}

export function partitionVietnameseVoices<V extends VoiceLike>(voices: readonly V[]) {
  const vietnamese = voices.filter(isVietnamese);
  return {
    local: vietnamese.filter((v) => v.localService),
    network: vietnamese.filter((v) => !v.localService),
  };
}

export function usableVoices<V extends VoiceLike>(
  voices: readonly V[],
  allowNetworkVoices: boolean,
): V[] {
  const { local, network } = partitionVietnameseVoices(voices);
  return allowNetworkVoices ? [...local, ...network] : local;
}

/** The preferred voice if still usable, otherwise the first usable one. */
export function pickVoice<V extends VoiceLike>(
  voices: readonly V[],
  preferredURI: string | null,
  allowNetworkVoices: boolean,
): V | null {
  const usable = usableVoices(voices, allowNetworkVoices);
  return usable.find((v) => v.voiceURI === preferredURI) ?? usable[0] ?? null;
}
