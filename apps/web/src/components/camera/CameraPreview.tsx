import { useEffect, useRef } from "react";

import { vi } from "../../i18n/vi";

/** Mirrored by CSS only; the stream itself stays unmirrored (docs/API_CONTRACTS.md). */
export function CameraPreview({ stream }: { stream: MediaStream }) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.srcObject = stream;
    return () => {
      video.srcObject = null;
    };
  }, [stream]);

  return (
    <video
      ref={videoRef}
      className="camera__video"
      aria-label={vi.camera.previewLabel}
      autoPlay
      muted
      playsInline
      data-testid="camera-preview"
    />
  );
}
