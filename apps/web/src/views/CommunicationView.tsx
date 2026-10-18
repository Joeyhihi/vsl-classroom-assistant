import { CameraPanel } from "../components/camera/CameraPanel";
import { ManualTextInput } from "../components/compose/ManualTextInput";
import { TtsStatus } from "../components/speech/TtsStatus";
import { TranscriptPanel } from "../components/transcript/TranscriptPanel";
import type { CameraState } from "../features/camera/useCamera";
import type { CameraDevice } from "../features/camera/useMediaDevices";
import type { TranscriptEntry } from "../features/transcript/transcriptStore";
import type { TtsController } from "../features/tts/useTts";

interface Props {
  camera: CameraState;
  devices: CameraDevice[];
  preferredCameraId: string | null;
  onStartCamera: () => void;
  onStopCamera: () => void;
  onSelectCamera: (deviceId: string) => void;
  tts: TtsController;
  entries: readonly TranscriptEntry[];
  onSendMessage: (text: string, speaker: TranscriptEntry["speaker"], speak: boolean) => void;
  onSpeakEntry: (entry: TranscriptEntry) => void;
  onClearTranscript: () => void;
}

export function CommunicationView(props: Props) {
  const canSpeak = props.tts.availability === "ready";
  return (
    <div className="layout">
      <div className="layout__main">
        <CameraPanel
          state={props.camera}
          devices={props.devices}
          preferredCameraId={props.preferredCameraId}
          onStart={props.onStartCamera}
          onStop={props.onStopCamera}
          onSelectCamera={props.onSelectCamera}
        />
        <ManualTextInput canSpeak={canSpeak} onSubmit={props.onSendMessage} />
        <TtsStatus tts={props.tts} />
      </div>
      <div className="layout__side">
        <TranscriptPanel
          entries={props.entries}
          canSpeak={canSpeak}
          speakingId={props.tts.speakingId}
          onSpeak={props.onSpeakEntry}
          onClear={props.onClearTranscript}
        />
      </div>
    </div>
  );
}
