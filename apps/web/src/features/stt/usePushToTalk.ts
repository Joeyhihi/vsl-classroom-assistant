import { useCallback, useEffect, useRef, useState } from "react";

import { ApiCallError, transcribeAudio } from "../../api/http";
import { MAX_RECORDING_S, toUploadWav } from "./wav";

// Hold to talk: the microphone is open only while the button is held, and the
// audio goes only to the local backend (127.0.0.1). Nothing is stored.

export type PushToTalkState =
  | { kind: "idle" }
  | { kind: "starting" }
  | { kind: "listening" }
  | { kind: "transcribing" }
  | { kind: "error"; code: string };

export interface PushToTalkController {
  state: PushToTalkState;
  lastText: string | null;
  press: () => void;
  release: () => void;
}

const MIN_RECORDING_MS = 300;

// Inline AudioWorklet: copies each 128-sample input block to the main thread.
const WORKLET_SOURCE = `
class VslCapture extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) this.port.postMessage(channel.slice(0));
    return true;
  }
}
registerProcessor("vsl-capture", VslCapture);
`;

interface Capture {
  stream: MediaStream;
  context: AudioContext;
  chunks: Float32Array[];
  startedAt: number;
}

function micErrorCode(error: unknown): string {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") return "MIC_DENIED";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "MIC_UNAVAILABLE";
  if (name === "NotReadableError") return "MIC_IN_USE";
  return "MIC_ERROR";
}

async function openCapture(): Promise<Capture> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  const context = new AudioContext();
  const url = URL.createObjectURL(new Blob([WORKLET_SOURCE], { type: "application/javascript" }));
  try {
    await context.audioWorklet.addModule(url);
  } finally {
    URL.revokeObjectURL(url);
  }
  const chunks: Float32Array[] = [];
  const node = new AudioWorkletNode(context, "vsl-capture");
  node.port.onmessage = (event: MessageEvent<Float32Array>) => chunks.push(event.data);
  const silent = context.createGain();
  silent.gain.value = 0; // keeps the graph pulled without playing the mic back
  context.createMediaStreamSource(stream).connect(node);
  node.connect(silent).connect(context.destination);
  return { stream, context, chunks, startedAt: performance.now() };
}

function closeCapture(capture: Capture) {
  capture.stream.getTracks().forEach((t) => t.stop());
  void capture.context.close();
}

export function usePushToTalk(onTranscript: (text: string) => void): PushToTalkController {
  const [state, setState] = useState<PushToTalkState>({ kind: "idle" });
  const [lastText, setLastText] = useState<string | null>(null);
  const capture = useRef<Capture | null>(null);
  const held = useRef(false);
  const limitTimer = useRef<number | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  const finish = useCallback(async () => {
    const current = capture.current;
    capture.current = null;
    if (limitTimer.current !== null) window.clearTimeout(limitTimer.current);
    limitTimer.current = null;
    if (!current) return;
    closeCapture(current);
    if (performance.now() - current.startedAt < MIN_RECORDING_MS || current.chunks.length === 0) {
      setState({ kind: "error", code: "TOO_SHORT" });
      return;
    }
    setState({ kind: "transcribing" });
    try {
      const result = await transcribeAudio(toUploadWav(current.chunks, current.context.sampleRate));
      const text = result.text.trim();
      if (!text) {
        setState({ kind: "error", code: "NO_SPEECH" });
        return;
      }
      setLastText(text);
      onTranscriptRef.current(text);
      setState({ kind: "idle" });
    } catch (error) {
      setState({ kind: "error", code: error instanceof ApiCallError ? error.code : "UNREACHABLE" });
    }
  }, []);

  const press = useCallback(() => {
    if (held.current || capture.current) return;
    held.current = true;
    setState({ kind: "starting" });
    openCapture()
      .then((opened) => {
        capture.current = opened;
        if (!held.current) {
          void finish(); // released while the mic was still opening
          return;
        }
        setState({ kind: "listening" });
        limitTimer.current = window.setTimeout(() => {
          held.current = false;
          void finish();
        }, MAX_RECORDING_S * 1000);
      })
      .catch((error: unknown) => {
        held.current = false;
        setState({ kind: "error", code: micErrorCode(error) });
      });
  }, [finish]);

  const release = useCallback(() => {
    if (!held.current) return;
    held.current = false;
    if (capture.current) void finish();
  }, [finish]);

  useEffect(
    () => () => {
      if (capture.current) closeCapture(capture.current);
      if (limitTimer.current !== null) window.clearTimeout(limitTimer.current);
    },
    [],
  );

  return { state, lastText, press, release };
}
