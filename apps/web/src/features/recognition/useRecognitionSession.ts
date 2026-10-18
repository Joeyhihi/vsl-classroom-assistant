// Orchestrates a recognition session: landmark source → WebSocket → reducer,
// plus fps / latency metrics, the fallback ladder, tab-visibility pause and
// reconnects. One WebSocket = one session.

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import type { SessionStart, WireFrame } from "../../api/generated/contracts";
import { NO_RECONNECT_CODES, RecognitionSocket, recognitionUrl, type ServerMessage } from "../../api/ws";
import { MediaPipeAssetError } from "../landmarks/assets";
import {
  CameraLandmarkSource,
  ReplayLandmarkSource,
  ServerExtractionSource,
  loadReplay,
  type LandmarkSource,
} from "../landmarks/sources";
import { DEFAULT_LADDER, LadderMonitor, type ExtractionLevel, type LadderVerdict } from "../metrics/ladder";
import { FpsMeter, SampleStats } from "../metrics/stats";
import { initialRecognitionState, recognitionReducer } from "./recognitionMachine";

export type SourceKind = "camera" | "replay";

export const FEATURE_SPEC_VERSION = "fs-1";
const MAX_RECONNECTS = 5;

export interface LatencySummary {
  count: number;
  p50: number | null;
  p95: number | null;
}

/**
 * total      = hands at rest → prediction rendered
 * wait       = the segmenter's deliberate pause tolerance (server hysteresis_ms)
 * processing = total − wait: closing frame captured → extracted → sent → classified
 *              → rendered. P3 hardware criterion: processing p95 ≤ 500 ms.
 */
export type CloseReason = "rest" | "still" | "max_duration";

export interface SessionMetrics {
  fps: number | null;
  latency: { total: LatencySummary; wait: LatencySummary; processing: LatencySummary };
  /** How each sign ended: tells whether "wait" reflects lowering the hands or holding still. */
  closeReasons: Record<CloseReason, number>;
  inferenceMs: number | null;
  sourceDetail: string;
}

const EMPTY_LATENCY: LatencySummary = { count: 0, p50: null, p95: null };
const NO_CLOSES: Record<CloseReason, number> = { rest: 0, still: 0, max_duration: 0 };

interface Options {
  sourceKind: SourceKind;
  stream: MediaStream | null;
  level: ExtractionLevel;
  minFps?: number;
}

export function useRecognitionSession({ sourceKind, stream, level, minFps = DEFAULT_LADDER.minFps }: Options) {
  const [state, dispatch] = useReducer(recognitionReducer, initialRecognitionState);
  const [metrics, setMetrics] = useState<SessionMetrics>({
    fps: null,
    latency: { total: EMPTY_LATENCY, wait: EMPTY_LATENCY, processing: EMPTY_LATENCY },
    closeReasons: NO_CLOSES,
    inferenceMs: null,
    sourceDetail: "-",
  });
  const [ladder, setLadder] = useState<LadderVerdict>({ kind: "measuring" });
  const lastFrame = useRef<WireFrame | null>(null);
  const runRef = useRef<{ stop: () => void } | null>(null);
  const wantRunning = useRef(false);
  const attempt = useRef(0);
  const activeLevel = useRef<ExtractionLevel>(level);
  const reconnect = useRef<(() => void) | null>(null);
  const fpsMeter = useRef(new FpsMeter());
  const latency = useRef({ total: new SampleStats(), wait: new SampleStats(), processing: new SampleStats() });
  const latencySummary = () => ({
    total: latency.current.total.summary(),
    wait: latency.current.wait.summary(),
    processing: latency.current.processing.summary(),
  });

  const teardown = useCallback(() => {
    runRef.current?.stop();
    runRef.current = null;
  }, []);

  const connect = useCallback(async (lvl: ExtractionLevel) => {
    teardown();
    dispatch({ type: "start" });
    let source: LandmarkSource;
    try {
      if (sourceKind === "replay") source = new ReplayLandmarkSource(await loadReplay());
      else if (!stream) throw new Error("camera");
      else if (lvl === "L3") source = new ServerExtractionSource(stream);
      else source = new CameraLandmarkSource(stream, lvl);
    } catch (error) {
      dispatch({ type: "failed", reason: error instanceof Error && error.message === "camera" ? "NO_CAMERA" : "REPLAY_UNAVAILABLE" });
      return;
    }

    // Source clock origin: t_ms of frames and "now" for latency share it.
    const t0 = performance.now();
    const sourceNow = () => performance.now() - t0;
    fpsMeter.current.reset();
    let monitor: LadderMonitor | null = null;
    let metricsTimer: ReturnType<typeof setInterval> | null = null;
    let stopped = false;
    let fatalSeen = false; // a fatal error message already explained the close

    const start: SessionStart = {
      type: "session.start",
      protocol_version: 1,
      feature_spec_version: FEATURE_SPEC_VERSION,
      extraction_mode: source.kind === "server" ? "server" : "client",
      image_width: source.imageWidth,
      image_height: source.imageHeight,
      fps_hint: 20,
      dominant_hand: "right",
    };

    const onMessage = (message: ServerMessage) => {
      switch (message.type) {
        case "session.started":
          attempt.current = 0;
          dispatch({ type: "session_started", message });
          void source
            .start(
              {
                onFrame: (frame) => {
                  lastFrame.current = frame;
                  socket.sendFrame(frame);
                },
                onBinary: (data) => socket.sendBinary(data),
                onProcessed: () => fpsMeter.current.tick(performance.now()),
              },
              message.feature_spec,
              sourceNow,
            )
            .then(() => {
              if (source.kind !== "replay") monitor = new LadderMonitor(lvl, performance.now(), { ...DEFAULT_LADDER, minFps });
            })
            .catch((error: unknown) => {
              if (error instanceof MediaPipeAssetError) {
                dispatch({ type: "failed", reason: "MEDIAPIPE_ASSETS_MISSING", detail: error.missing.join(", ") });
              } else {
                const detail = error instanceof Error ? error.message : undefined;
                dispatch({ type: "failed", reason: "EXTRACTOR_FAILED", detail });
              }
              fatalSeen = true;
              socket.stop();
            });
          metricsTimer = setInterval(() => {
            const now = performance.now();
            const fps = fpsMeter.current.fps(now);
            if (monitor) setLadder(monitor.observe(now, fps));
            setMetrics((m) => ({ ...m, fps, sourceDetail: source.detail, latency: latencySummary() }));
          }, 1000);
          break;
        case "status":
          dispatch({ type: "status", message });
          break;
        case "prediction":
          dispatch({ type: "prediction", message });
          // "Hands at rest → prediction rendered": measured after the next paint.
          requestAnimationFrame(() => {
            const total = sourceNow() - message.utterance.end_ms;
            const wait = message.timings.hysteresis_ms;
            latency.current.total.add(total);
            latency.current.wait.add(wait);
            latency.current.processing.add(Math.max(0, total - wait));
            const reason = message.utterance.close_reason;
            setMetrics((m) => ({
              ...m,
              inferenceMs: message.timings.inference_ms,
              latency: latencySummary(),
              closeReasons: { ...m.closeReasons, [reason]: m.closeReasons[reason] + 1 },
            }));
          });
          break;
        case "error":
          if (message.fatal) {
            fatalSeen = true;
            // The server's message carries the specific reason (e.g. why L3 is unavailable).
            dispatch({ type: "failed", reason: message.code, detail: message.message });
          }
          break;
        default:
          break;
      }
    };

    const onClose = (code: number) => {
      source.stop();
      if (metricsTimer) clearInterval(metricsTimer);
      if (stopped || !wantRunning.current || fatalSeen) return;
      if (NO_RECONNECT_CODES.has(code)) {
        dispatch({ type: "failed", reason: `CLOSE_${code}` });
        return;
      }
      attempt.current += 1;
      if (attempt.current > MAX_RECONNECTS) {
        dispatch({ type: "failed", reason: "BACKEND_UNREACHABLE" });
        return;
      }
      dispatch({ type: "reconnecting", attempt: attempt.current });
      const delay = Math.min(10_000, 1000 * 2 ** (attempt.current - 1));
      setTimeout(() => {
        if (wantRunning.current) reconnect.current?.();
      }, delay);
    };

    const socket = new RecognitionSocket(recognitionUrl(), start, { onMessage, onClose });
    runRef.current = {
      stop: () => {
        stopped = true;
        source.stop();
        socket.stop();
        if (metricsTimer) clearInterval(metricsTimer);
      },
    };
  }, [sourceKind, stream, minFps, teardown]);

  useEffect(() => {
    reconnect.current = () => void connect(activeLevel.current);
  }, [connect]);

  /** Start a session; `levelOverride` lets a ladder switch apply immediately (session boundary). */
  const start = useCallback(
    (levelOverride?: ExtractionLevel) => {
      wantRunning.current = true;
      attempt.current = 0;
      activeLevel.current = levelOverride ?? level;
      Object.values(latency.current).forEach((s) => s.reset());
    setMetrics((m) => ({ ...m, closeReasons: NO_CLOSES }));
      setLadder({ kind: "measuring" });
      void connect(activeLevel.current);
    },
    [connect, level],
  );

  const stop = useCallback(() => {
    wantRunning.current = false;
    teardown();
    lastFrame.current = null;
    dispatch({ type: "stopped" });
  }, [teardown]);

  // Background tabs throttle timers and video callbacks: pause visibly instead.
  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden && wantRunning.current) {
        wantRunning.current = false;
        teardown();
        dispatch({ type: "paused" });
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [teardown]);

  useEffect(() => () => {
    wantRunning.current = false;
    teardown();
  }, [teardown]);

  const resolveCandidate = useCallback(() => dispatch({ type: "resolve_candidate" }), []);

  return { state, metrics, ladder, lastFrame, start, stop, resolveCandidate };
}

export type RecognitionController = ReturnType<typeof useRecognitionSession>;
