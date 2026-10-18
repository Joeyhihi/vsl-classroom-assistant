import { useEffect, useState } from "react";

import type { VocabularyEntry } from "../../api/generated/contracts";
import { fetchVocabulary } from "../../api/http";

export type VocabularyState =
  | { kind: "loading" }
  | { kind: "ready"; version: string; entries: VocabularyEntry[] }
  | { kind: "unavailable" };

function isEntry(value: unknown): value is VocabularyEntry {
  const v = value as Partial<VocabularyEntry> | null;
  return typeof v?.gloss_id === "string" && typeof v.text_vi === "string" && typeof v.icon === "string";
}

/** The signs the current model knows (GET /vocabulary). Reloaded when `key` changes. */
export function useVocabulary(enabled: boolean, key: string | null): VocabularyState {
  // The fetched result is tagged with the key it was fetched for, so a stale
  // result reads as "loading" without a synchronous setState in the effect.
  const [loaded, setLoaded] = useState<{ key: string | null; state: VocabularyState } | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    fetchVocabulary()
      .then((body) => {
        if (cancelled) return;
        const entries = Array.isArray(body?.entries) ? body.entries.filter(isEntry) : null;
        setLoaded({
          key,
          state: entries ? { kind: "ready", version: String(body.vocabulary_version), entries } : { kind: "unavailable" },
        });
      })
      .catch(() => {
        if (!cancelled) setLoaded({ key, state: { kind: "unavailable" } });
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, key]);
  if (!enabled) return { kind: "unavailable" };
  return loaded && loaded.key === key ? loaded.state : { kind: "loading" };
}
