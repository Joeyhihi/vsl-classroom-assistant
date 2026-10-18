import { useId } from "react";

import type { CameraDevice } from "../../features/camera/useMediaDevices";
import { vi } from "../../i18n/vi";

interface Props {
  devices: CameraDevice[];
  value: string | null;
  onChange: (deviceId: string) => void;
}

export function CameraSelector({ devices, value, onChange }: Props) {
  const id = useId();
  if (devices.length === 0) return null;
  const selected = devices.some((d) => d.deviceId === value) ? value! : devices[0]!.deviceId;

  return (
    <div className="field">
      <label htmlFor={id}>{vi.camera.selectorLabel}</label>
      <select id={id} value={selected} onChange={(e) => onChange(e.target.value)}>
        {devices.map((d) => (
          <option key={d.deviceId} value={d.deviceId}>
            {d.label}
          </option>
        ))}
      </select>
    </div>
  );
}
