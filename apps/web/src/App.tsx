import { useEffect, useState } from "react";

import type { ScoredLabelWire } from "./api/generated/contracts";

import { ConnectionBanner } from "./components/system/ConnectionBanner";
import { useCamera } from "./features/camera/useCamera";
import { useMediaDevices } from "./features/camera/useMediaDevices";
import { useBackendHealth } from "./features/health/useBackendHealth";
import { canSpeakPrediction } from "./features/recognition/recognitionMachine";
import { useRecognitionSession, type SourceKind } from "./features/recognition/useRecognitionSession";
import { useSettings } from "./features/settings/settingsStore";
import {
  createManualEntry,
  createSignEntry,
  useTranscript,
  type TranscriptEntry,
} from "./features/transcript/transcriptStore";
import { useTts } from "./features/tts/useTts";
import { vi } from "./i18n/vi";
import { CommunicationView } from "./views/CommunicationView";
import { PrivacyView } from "./views/PrivacyView";
import { RecorderView } from "./views/RecorderView";
import { SettingsView } from "./views/SettingsView";

type View = "communicate" | "settings" | "privacy" | "record";

// Build-time switches (.env, docs/CROSS_PLATFORM_SETUP.md §5).
const SOURCE_KIND: SourceKind = import.meta.env.VITE_LANDMARK_SOURCE === "replay" ? "replay" : "camera";
const RECORDER_ENABLED = import.meta.env.VITE_ENABLE_RECORDER === "true";
const MIN_FPS = Number(import.meta.env.VITE_MIN_FPS) || 15;
const VIEWS: readonly View[] = RECORDER_ENABLED
  ? ["communicate", "settings", "privacy", "record"]
  : ["communicate", "settings", "privacy"];

export function App() {
  const [view, setView] = useState<View>("communicate");
  const backend = useBackendHealth();
  const { settings, update, reset } = useSettings();
  const camera = useCamera();
  const devices = useMediaDevices(camera.state.kind === "active" ? camera.state.stream : null);
  const tts = useTts(settings);
  const transcript = useTranscript();
  const isMock = backend.kind === "online" && backend.health.model_mode === "mock";
  const stream = camera.state.kind === "active" ? camera.state.stream : null;
  const recognition = useRecognitionSession({
    sourceKind: SOURCE_KIND,
    stream,
    level: settings.extractionLevel,
    minFps: MIN_FPS,
  });

  // Ladder (ADR-002): L1 → L2 is automatic but applies from the next session.
  const { ladder } = recognition;
  useEffect(() => {
    if (ladder.kind === "too_slow" && ladder.next.action === "auto_switch" && settings.extractionLevel === "L1") {
      update({ extractionLevel: "L2" });
    }
  }, [ladder, settings.extractionLevel, update]);

  // The user accepted L3: restarting is the session boundary, so switch now.
  const acceptL3 = () => {
    update({ extractionLevel: "L3" });
    recognition.stop();
    recognition.start("L3");
  };

  const cameraIdToUse = (deviceId: string | null) =>
    deviceId && devices.some((d) => d.deviceId === deviceId) ? deviceId : null;

  const startCamera = () => void camera.start(cameraIdToUse(settings.preferredCameraId));

  const selectCamera = (deviceId: string) => {
    update({ preferredCameraId: deviceId });
    if (camera.state.kind === "active") void camera.start(deviceId);
  };

  const speakEntry = (entry: TranscriptEntry) =>
    tts.speak(entry.text, entry.id, () => transcript.markSpoken(entry.id));

  const sendMessage = (text: string, speaker: TranscriptEntry["speaker"], speak: boolean) => {
    const entry = createManualEntry(text, speaker);
    transcript.add(entry);
    if (speak) speakEntry(entry);
  };

  const confirmPrediction = (label: ScoredLabelWire) => {
    const entry = createSignEntry(label);
    transcript.add(entry);
    recognition.resolveCandidate();
    // Scripted mock output is never spoken (ADR-016).
    if (canSpeakPrediction(recognition.state.model) && tts.availability === "ready") speakEntry(entry);
  };

  const deleteLocalData = () => {
    tts.cancel();
    transcript.clear();
    reset();
  };

  return (
    <div className="app">
      <header className="app__header">
        <h1>{vi.appTitle}</h1>
        {isMock && (
          <span className="badge badge--mock" title={vi.mockBadgeLabel} data-testid="mock-badge">
            {vi.mockBadge}
            <span className="visually-hidden">: {vi.mockBadgeLabel}</span>
          </span>
        )}
        {camera.state.kind === "active" && (
          <span className="badge badge--live">
            <span aria-hidden="true">●</span> {vi.camera.active}
          </span>
        )}
      </header>

      <nav aria-label={vi.nav.label} className="nav">
        {VIEWS.map((v) => (
          <button
            key={v}
            type="button"
            className="nav__item"
            aria-current={view === v ? "page" : undefined}
            onClick={() => setView(v)}
          >
            {vi.nav[v]}
          </button>
        ))}
      </nav>

      <ConnectionBanner state={backend} />

      <main className="app__main">
        <p className="tagline">{vi.appTagline}</p>
        <p className="notice">{vi.phaseNotice}</p>
        {view === "communicate" && (
          <CommunicationView
            camera={camera.state}
            devices={devices}
            preferredCameraId={settings.preferredCameraId}
            onStartCamera={startCamera}
            onStopCamera={camera.stop}
            onSelectCamera={selectCamera}
            tts={tts}
            entries={transcript.entries}
            onSendMessage={sendMessage}
            onSpeakEntry={speakEntry}
            onClearTranscript={transcript.clear}
            recognition={recognition}
            sourceKind={SOURCE_KIND}
            onConfirmPrediction={confirmPrediction}
            onAcceptL3={acceptL3}
          />
        )}
        {view === "settings" && (
          <SettingsView
            settings={settings}
            onUpdate={update}
            devices={devices}
            onSelectCamera={selectCamera}
            tts={tts}
            backend={backend}
            onDeleteLocalData={deleteLocalData}
            recognition={recognition}
          />
        )}
        {view === "privacy" && <PrivacyView />}
        {view === "record" && RECORDER_ENABLED && (
          <RecorderView sourceKind={SOURCE_KIND} stream={stream} level={settings.extractionLevel} />
        )}
      </main>
    </div>
  );
}
