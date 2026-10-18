import { useCallback, useEffect, useRef, useState } from "react";

import { classifyCameraError, type CameraFailure } from "./cameraErrors";

export type CameraState =
  | { kind: "idle" }
  | { kind: "requesting" }
  | { kind: "active"; stream: MediaStream; deviceId: string | null }
  | { kind: "failed"; failure: CameraFailure };

const VIDEO_CONSTRAINTS: MediaTrackConstraints = {
  width: { ideal: 640 },
  height: { ideal: 480 },
  frameRate: { ideal: 30 },
};

function stopStream(stream: MediaStream) {
  for (const track of stream.getTracks()) track.stop();
}

/**
 * Camera lifecycle. Permission is requested only from `start()` (a user action),
 * never on mount. Video stays in the browser; nothing is recorded.
 */
export function useCamera() {
  const [state, setState] = useState<CameraState>({ kind: "idle" });
  const streamRef = useRef<MediaStream | null>(null);
  const requestRef = useRef(0);

  const release = useCallback(() => {
    if (streamRef.current) stopStream(streamRef.current);
    streamRef.current = null;
  }, []);

  const start = useCallback(
    async (deviceId?: string | null) => {
      const request = ++requestRef.current;
      release();
      if (!navigator.mediaDevices?.getUserMedia) {
        setState({ kind: "failed", failure: "insecure" });
        return;
      }
      setState({ kind: "requesting" });
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: deviceId ? { ...VIDEO_CONSTRAINTS, deviceId: { exact: deviceId } } : VIDEO_CONSTRAINTS,
        });
        if (request !== requestRef.current) {
          stopStream(stream); // a newer start/stop superseded this request
          return;
        }
        streamRef.current = stream;
        const track = stream.getVideoTracks()[0];
        // Camera unplugged or taken over by the OS while running.
        track?.addEventListener("ended", () => {
          if (streamRef.current === stream) {
            release();
            setState({ kind: "failed", failure: "unavailable" });
          }
        });
        setState({ kind: "active", stream, deviceId: track?.getSettings().deviceId ?? null });
      } catch (error) {
        if (request === requestRef.current) {
          setState({ kind: "failed", failure: classifyCameraError(error) });
        }
      }
    },
    [release],
  );

  const stop = useCallback(() => {
    requestRef.current++;
    release();
    setState({ kind: "idle" });
  }, [release]);

  useEffect(() => release, [release]);

  return { state, start, stop };
}
