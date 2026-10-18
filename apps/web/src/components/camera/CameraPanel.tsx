import type { CameraState } from "../../features/camera/useCamera";
import type { CameraDevice } from "../../features/camera/useMediaDevices";
import { vi } from "../../i18n/vi";
import { StatusLine } from "../ui/StatusLine";
import { CameraPreview } from "./CameraPreview";
import { CameraSelector } from "./CameraSelector";

interface Props {
  state: CameraState;
  devices: CameraDevice[];
  preferredCameraId: string | null;
  onStart: () => void;
  onStop: () => void;
  onSelectCamera: (deviceId: string) => void;
}

export function CameraPanel({ state, devices, preferredCameraId, onStart, onStop, onSelectCamera }: Props) {
  return (
    <section className="card camera" aria-labelledby="camera-heading">
      <h2 id="camera-heading">{vi.camera.heading}</h2>

      {state.kind === "idle" && (
        <>
          <p>{vi.camera.intro}</p>
          <button type="button" className="btn btn--primary" onClick={onStart}>
            {vi.camera.start}
          </button>
        </>
      )}

      {state.kind === "requesting" && (
        <>
          <StatusLine tone="info" text={vi.camera.requesting} />
          <p className="hint">{vi.camera.requestingHint}</p>
        </>
      )}

      {state.kind === "active" && (
        <>
          <StatusLine tone="active" text={vi.camera.active} icon="●" />
          <div className="camera__frame">
            <CameraPreview stream={state.stream} />
          </div>
          <div className="row">
            <CameraSelector
              devices={devices}
              value={state.deviceId ?? preferredCameraId}
              onChange={onSelectCamera}
            />
            <button type="button" className="btn" onClick={onStop}>
              {vi.camera.stop}
            </button>
          </div>
        </>
      )}

      {state.kind === "failed" && (
        <div role="alert">
          <StatusLine tone="danger" text={vi.camera.failure[state.failure]} />
          <p>{vi.camera.help[state.failure]}</p>
          <button type="button" className="btn btn--primary" onClick={onStart}>
            {vi.camera.retry}
          </button>
        </div>
      )}
    </section>
  );
}
