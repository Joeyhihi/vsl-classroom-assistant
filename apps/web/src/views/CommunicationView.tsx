import type { ComponentHealth, PredictionMessage, ScoredLabelWire } from "../api/generated/contracts";
import { CameraPanel } from "../components/camera/CameraPanel";
import { ManualTextInput } from "../components/compose/ManualTextInput";
import { RecognitionPanel } from "../components/recognition/RecognitionPanel";
import { SubtitlePanel } from "../components/speech/SubtitlePanel";
import { TtsStatus } from "../components/speech/TtsStatus";
import { TranscriptPanel, type FeedbackOptions } from "../components/transcript/TranscriptPanel";
import type { CameraState } from "../features/camera/useCamera";
import type { CameraDevice } from "../features/camera/useMediaDevices";
import type { RecognitionController, SourceKind } from "../features/recognition/useRecognitionSession";
import type { PushToTalkController } from "../features/stt/usePushToTalk";
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
  recognition: RecognitionController;
  sourceKind: SourceKind;
  onConfirmPrediction: (label: ScoredLabelWire, prediction: PredictionMessage) => void;
  onAcceptL3: () => void;
  feedback?: FeedbackOptions;
  /** Shown only when the backend has STT enabled (P7, gated). */
  stt?: { health: ComponentHealth; ptt: PushToTalkController };
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
        <RecognitionPanel
          controller={props.recognition}
          sourceKind={props.sourceKind}
          onConfirm={props.onConfirmPrediction}
          onAcceptL3={props.onAcceptL3}
        />
        <ManualTextInput canSpeak={canSpeak} onSubmit={props.onSendMessage} />
        <TtsStatus tts={props.tts} />
        {props.stt && <SubtitlePanel health={props.stt.health} ptt={props.stt.ptt} />}
      </div>
      <div className="layout__side">
        <TranscriptPanel
          entries={props.entries}
          canSpeak={canSpeak}
          speakingId={props.tts.speakingId}
          onSpeak={props.onSpeakEntry}
          onClear={props.onClearTranscript}
          feedback={props.feedback}
        />
      </div>
    </div>
  );
}
