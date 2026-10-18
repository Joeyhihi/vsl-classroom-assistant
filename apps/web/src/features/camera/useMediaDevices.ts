import { useEffect, useState } from "react";

export interface CameraDevice {
  deviceId: string;
  label: string;
}

/**
 * Lists cameras. Labels are empty until permission is granted, so callers
 * pass `refreshKey` (e.g. the active stream) to re-enumerate after starting.
 */
export function useMediaDevices(refreshKey: unknown): CameraDevice[] {
  const [devices, setDevices] = useState<CameraDevice[]>([]);

  useEffect(() => {
    const mediaDevices = navigator.mediaDevices;
    if (!mediaDevices?.enumerateDevices) return;
    let cancelled = false;

    const refresh = async () => {
      const all = await mediaDevices.enumerateDevices().catch(() => []);
      if (cancelled) return;
      setDevices(
        all
          .filter((d) => d.kind === "videoinput" && d.deviceId)
          .map((d, i) => ({ deviceId: d.deviceId, label: d.label || `Camera ${i + 1}` })),
      );
    };

    void refresh();
    mediaDevices.addEventListener?.("devicechange", refresh);
    return () => {
      cancelled = true;
      mediaDevices.removeEventListener?.("devicechange", refresh);
    };
  }, [refreshKey]);

  return devices;
}
