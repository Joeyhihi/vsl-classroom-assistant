// Landmark sources (docs/ARCHITECTURE.md §5):
//   replay  – synthetic fixture, no camera, no MediaPipe (M1 dev loop, tests)
//   camera  – L1/L2 MediaPipe in the browser
//   server  – L3: unmirrored JPEG frames sent to the local backend

import type { FeatureSpecWire, WireFrame } from "../../api/generated/contracts";
import type { ExtractionLevel } from "../metrics/ladder";
import { createExtractor, type Extractor } from "./extractor";

export interface FrameSink {
  onFrame: (frame: WireFrame) => void;
  onBinary: (data: ArrayBuffer, tMs: number) => void;
  /** Called once per processed camera frame (fps measurement). */
  onProcessed: () => void;
}

export interface LandmarkSource {
  readonly kind: "replay" | "camera" | "server";
  readonly imageWidth: number;
  readonly imageHeight: number;
  /** Diagnostics: "worker"/"main" + delegate for camera, "-" otherwise. */
  readonly detail: string;
  start(sink: FrameSink, spec: FeatureSpecWire): Promise<void>;
  stop(): void;
}

// --- replay ------------------------------------------------------------------

export interface ReplayFile {
  format: "vsl-replay-v1";
  synthetic: boolean;
  feature_spec_version: string;
  fps: number;
  image_width: number;
  image_height: number;
  frames: WireFrame[];
}

export const REPLAY_URL = "/replay/synthetic-replay-v1.json";
const LOOP_GAP_MS = 1000;

export async function loadReplay(url: string = REPLAY_URL): Promise<ReplayFile> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`replay not found (${response.status})`);
  const data = (await response.json()) as ReplayFile;
  if (data.format !== "vsl-replay-v1" || !Array.isArray(data.frames) || data.frames.length === 0) {
    throw new Error("invalid replay file");
  }
  return data;
}

/** Plays frames in real time and loops; t_ms is rebased so it always increases. */
export class ReplayLandmarkSource implements LandmarkSource {
  readonly kind = "replay";
  readonly detail = "replay";
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly replay: ReplayFile,
    private readonly clock: () => number = () => performance.now(),
  ) {}

  get imageWidth() {
    return this.replay.image_width;
  }

  get imageHeight() {
    return this.replay.image_height;
  }

  async start(sink: FrameSink): Promise<void> {
    const frames = this.replay.frames;
    const duration = (frames[frames.length - 1] as WireFrame).t_ms + LOOP_GAP_MS;
    const t0 = this.clock();
    let index = 0;
    let loop = 0;
    const tick = () => {
      const frame = frames[index] as WireFrame;
      const t = loop * duration + frame.t_ms;
      sink.onFrame({ ...frame, t_ms: Math.round(t * 10) / 10 });
      sink.onProcessed();
      index += 1;
      if (index >= frames.length) {
        index = 0;
        loop += 1;
      }
      const next = loop * duration + (frames[index] as WireFrame).t_ms;
      this.timer = setTimeout(tick, Math.max(0, next - (this.clock() - t0)));
    };
    this.timer = setTimeout(tick, 0);
  }

  stop() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }
}

// --- camera helpers ------------------------------------------------------------

async function hiddenVideo(stream: MediaStream): Promise<HTMLVideoElement> {
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.srcObject = stream;
  await video.play();
  return video;
}

type FrameCallbackVideo = HTMLVideoElement & {
  requestVideoFrameCallback?: (cb: () => void) => number;
  cancelVideoFrameCallback?: (id: number) => void;
};

/** Calls `onFrame` once per new video frame (rVFC where available). */
function frameLoop(video: FrameCallbackVideo, onFrame: () => void): () => void {
  let active = true;
  let handle = 0;
  const schedule = () => {
    if (!active) return;
    handle = video.requestVideoFrameCallback
      ? video.requestVideoFrameCallback(step)
      : requestAnimationFrame(step);
  };
  const step = () => {
    onFrame();
    schedule();
  };
  schedule();
  return () => {
    active = false;
    if (video.cancelVideoFrameCallback) video.cancelVideoFrameCallback(handle);
    else cancelAnimationFrame(handle);
  };
}

// --- L1 / L2 -------------------------------------------------------------------

export class CameraLandmarkSource implements LandmarkSource {
  readonly kind = "camera";
  private extractor: Extractor | null = null;
  private stopLoop: (() => void) | null = null;
  private video: HTMLVideoElement | null = null;

  constructor(
    private readonly stream: MediaStream,
    private readonly level: Exclude<ExtractionLevel, "L3">,
  ) {}

  get imageWidth() {
    return this.stream.getVideoTracks()[0]?.getSettings().width ?? 640;
  }

  get imageHeight() {
    return this.stream.getVideoTracks()[0]?.getSettings().height ?? 480;
  }

  get detail() {
    return this.extractor ? `${this.level} ${this.extractor.mode}/${this.extractor.delegate}` : this.level;
  }

  async start(sink: FrameSink, spec: FeatureSpecWire): Promise<void> {
    this.video = await hiddenVideo(this.stream);
    this.extractor = await createExtractor(this.level, spec);
    const t0 = performance.now();
    let busy = false; // back-pressure: drop camera frames while one is processing
    this.stopLoop = frameLoop(this.video, () => {
      if (busy || !this.extractor || !this.video) return;
      busy = true;
      this.extractor
        .detect(this.video, performance.now() - t0)
        .then((frame) => {
          sink.onFrame(frame);
          sink.onProcessed();
        })
        .catch(() => undefined)
        .finally(() => {
          busy = false;
        });
    });
  }

  stop() {
    this.stopLoop?.();
    this.extractor?.close();
    if (this.video) this.video.srcObject = null;
    this.extractor = null;
    this.video = null;
  }
}

// --- L3 ---------------------------------------------------------------------------

export const SERVER_MAX_WIDTH = 640;
export const SERVER_MAX_HEIGHT = 480;
export const SERVER_MAX_FPS = 20;
export const SERVER_JPEG_QUALITY = 0.7;

/** 16-byte header: t_ms uint64, width uint16, height uint16, 4 reserved (little-endian). */
export function binaryFrame(tMs: number, width: number, height: number, jpeg: ArrayBuffer): ArrayBuffer {
  const out = new Uint8Array(16 + jpeg.byteLength);
  const view = new DataView(out.buffer);
  view.setBigUint64(0, BigInt(Math.max(0, Math.round(tMs))), true);
  view.setUint16(8, width, true);
  view.setUint16(10, height, true);
  out.set(new Uint8Array(jpeg), 16);
  return out.buffer;
}

export class ServerExtractionSource implements LandmarkSource {
  readonly kind = "server";
  readonly detail = "L3 server";
  private stopLoop: (() => void) | null = null;
  private video: HTMLVideoElement | null = null;

  constructor(private readonly stream: MediaStream) {}

  get imageWidth() {
    return Math.min(SERVER_MAX_WIDTH, this.stream.getVideoTracks()[0]?.getSettings().width ?? 640);
  }

  get imageHeight() {
    return Math.min(SERVER_MAX_HEIGHT, this.stream.getVideoTracks()[0]?.getSettings().height ?? 480);
  }

  async start(sink: FrameSink): Promise<void> {
    this.video = await hiddenVideo(this.stream);
    const canvas = new OffscreenCanvas(this.imageWidth, this.imageHeight);
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("no 2d context");
    const t0 = performance.now();
    let last = -Infinity;
    let busy = false;
    this.stopLoop = frameLoop(this.video, () => {
      const now = performance.now();
      if (busy || !this.video || now - last < 1000 / SERVER_MAX_FPS) return;
      busy = true;
      last = now;
      // Drawn unmirrored: the server sees the same orientation as browser extraction.
      ctx.drawImage(this.video, 0, 0, canvas.width, canvas.height);
      const tMs = now - t0;
      canvas
        .convertToBlob({ type: "image/jpeg", quality: SERVER_JPEG_QUALITY })
        .then((blob) => blob.arrayBuffer())
        .then((jpeg) => {
          sink.onBinary(binaryFrame(tMs, canvas.width, canvas.height, jpeg), tMs);
          sink.onProcessed();
        })
        .catch(() => undefined)
        .finally(() => {
          busy = false;
        });
    });
  }

  stop() {
    this.stopLoop?.();
    if (this.video) this.video.srcObject = null;
    this.video = null;
  }
}
