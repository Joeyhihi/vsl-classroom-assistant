import { useId, useState } from "react";

import { CameraSelector } from "../components/camera/CameraSelector";
import { BackendStatus } from "../components/system/BackendStatus";
import type { CameraDevice } from "../features/camera/useMediaDevices";
import type { BackendHealthState } from "../features/health/useBackendHealth";
import { SPEECH_RATE_MAX, SPEECH_RATE_MIN, type Settings } from "../features/settings/settingsStore";
import { partitionVietnameseVoices } from "../features/tts/speechSynthesis";
import type { TtsController } from "../features/tts/useTts";
import { vi } from "../i18n/vi";

interface Props {
  settings: Settings;
  onUpdate: (patch: Partial<Settings>) => void;
  devices: CameraDevice[];
  onSelectCamera: (deviceId: string) => void;
  tts: TtsController;
  backend: BackendHealthState;
  onDeleteLocalData: () => void;
}

export function SettingsView({ settings, onUpdate, devices, onSelectCamera, tts, backend, onDeleteLocalData }: Props) {
  const voiceId = useId();
  const rateId = useId();
  const [confirming, setConfirming] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const { local, network } = partitionVietnameseVoices(tts.allVoices);

  return (
    <div className="stack">
      <h2 className="visually-hidden">{vi.settings.heading}</h2>

      <section className="card" aria-labelledby="settings-camera">
        <h3 id="settings-camera">{vi.settings.cameraHeading}</h3>
        {devices.length > 0 ? (
          <CameraSelector devices={devices} value={settings.preferredCameraId} onChange={onSelectCamera} />
        ) : (
          <p className="hint">{vi.settings.noCameras}</p>
        )}
      </section>

      <section className="card" aria-labelledby="settings-voice">
        <h3 id="settings-voice">{vi.settings.voiceHeading}</h3>
        {tts.usable.length > 0 ? (
          <div className="field">
            <label htmlFor={voiceId}>{vi.settings.voiceLabel}</label>
            <select
              id={voiceId}
              value={tts.voice?.voiceURI ?? ""}
              onChange={(e) => onUpdate({ voiceURI: e.target.value })}
            >
              {tts.usable.map((v) => (
                <option key={v.voiceURI} value={v.voiceURI}>
                  {v.name} ({v.localService ? vi.settings.voiceLocal : vi.settings.voiceNetwork})
                </option>
              ))}
            </select>
          </div>
        ) : (
          <p className="hint">{tts.availability === "unsupported" ? vi.tts.unsupported : vi.tts.noVoice}</p>
        )}
        <div className="field">
          <label htmlFor={rateId}>
            {vi.settings.rateLabel}: {settings.speechRate.toFixed(1)}×
          </label>
          <input
            id={rateId}
            type="range"
            min={SPEECH_RATE_MIN}
            max={SPEECH_RATE_MAX}
            step={0.1}
            value={settings.speechRate}
            onChange={(e) => onUpdate({ speechRate: Number(e.target.value) })}
          />
        </div>
        <button
          type="button"
          className="btn"
          disabled={tts.availability !== "ready"}
          onClick={() => tts.speak(vi.settings.testPhrase, "settings-test")}
        >
          {vi.settings.test}
        </button>
        <label className="check">
          <input
            type="checkbox"
            checked={settings.allowNetworkVoices}
            onChange={(e) => onUpdate({ allowNetworkVoices: e.target.checked })}
          />
          {vi.settings.allowNetwork}
        </label>
        <p className="hint">{vi.tts.networkWarning}</p>
      </section>

      <section className="card" aria-labelledby="settings-diagnostics">
        <h3 id="settings-diagnostics">{vi.settings.diagnosticsHeading}</h3>
        <p data-testid="voice-summary">{vi.settings.voicesFound(local.length, network.length)}</p>
        {local.length + network.length > 0 && (
          <ul className="voice-list">
            {[...local, ...network].map((v) => (
              <li key={v.voiceURI}>
                {v.name} — {v.lang} — {v.localService ? vi.settings.voiceLocal : vi.settings.voiceNetwork}
              </li>
            ))}
          </ul>
        )}
      </section>

      <BackendStatus state={backend} />

      <section className="card" aria-labelledby="settings-data">
        <h3 id="settings-data">{vi.settings.dataHeading}</h3>
        <p className="hint">{vi.settings.deleteExplain}</p>
        {confirming ? (
          <div className="row">
            <button
              type="button"
              className="btn btn--danger"
              onClick={() => {
                onDeleteLocalData();
                setConfirming(false);
                setDeleted(true);
              }}
            >
              {vi.settings.deleteConfirm}
            </button>
            <button type="button" className="btn" onClick={() => setConfirming(false)}>
              {vi.settings.deleteCancel}
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="btn"
            onClick={() => {
              setDeleted(false);
              setConfirming(true);
            }}
          >
            {vi.settings.deleteData}
          </button>
        )}
        <p role="status" aria-live="polite">
          {deleted ? vi.settings.deleted : ""}
        </p>
      </section>
    </div>
  );
}
