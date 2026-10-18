// Recognition WebSocket client (docs/API_CONTRACTS.md § WebSocket).
// Batches frames, sends heartbeats and reports close codes; reconnect policy
// lives in useRecognitionSession.

import { API_BASE } from "./http";
import type {
  ErrorMessage,
  Pong,
  PredictionMessage,
  SessionStart,
  SessionStarted,
  SessionStopped,
  StatusMessage,
  WireFrame,
} from "./generated/contracts";

export type ServerMessage =
  | SessionStarted
  | StatusMessage
  | PredictionMessage
  | ErrorMessage
  | SessionStopped
  | Pong;

const SERVER_TYPES: readonly string[] = [
  "session.started",
  "status",
  "prediction",
  "error",
  "session.stopped",
  "pong",
];

/** Close codes after which reconnecting cannot help (protocol, policy, config). */
export const NO_RECONNECT_CODES: ReadonlySet<number> = new Set([1000, 1008, 1009, 4001, 4002, 4005, 4006]);

export interface SocketHandlers {
  onMessage: (message: ServerMessage) => void;
  onClose: (code: number) => void;
}

export interface SocketOptions {
  batchSize: number;
  flushMs: number;
  pingMs: number;
}

// Each frame is sent as soon as it is extracted (batch of 1): on localhost the
// extra messages cost nothing, and batching added up to ~100 ms of latency.
// The flush timer only drains frames queued while the socket was opening.
const DEFAULT_OPTIONS: SocketOptions = { batchSize: 1, flushMs: 100, pingMs: 5000 };

export function recognitionUrl(location: Location = window.location): string {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${location.host}${API_BASE}/recognition/ws`;
}

export function parseServerMessage(data: string): ServerMessage | null {
  try {
    const parsed: unknown = JSON.parse(data);
    if (typeof parsed === "object" && parsed !== null && SERVER_TYPES.includes((parsed as { type: string }).type)) {
      return parsed as ServerMessage;
    }
  } catch {
    // fall through
  }
  return null;
}

export class RecognitionSocket {
  private readonly ws: WebSocket;
  private queue: WireFrame[] = [];
  private flushTimer: ReturnType<typeof setInterval> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private closed = false;

  constructor(
    url: string,
    start: SessionStart,
    private readonly handlers: SocketHandlers,
    private readonly options: SocketOptions = DEFAULT_OPTIONS,
    WebSocketImpl: typeof WebSocket = WebSocket,
  ) {
    this.ws = new WebSocketImpl(url);
    this.ws.binaryType = "arraybuffer";
    this.ws.onopen = () => {
      this.ws.send(JSON.stringify(start));
      this.flushTimer = setInterval(() => this.flush(), options.flushMs);
      this.pingTimer = setInterval(() => this.sendJson({ type: "ping" }), options.pingMs);
    };
    this.ws.onmessage = (event: MessageEvent) => {
      if (typeof event.data !== "string") return;
      const message = parseServerMessage(event.data);
      if (message) handlers.onMessage(message);
    };
    this.ws.onclose = (event: CloseEvent) => this.finish(event.code);
  }

  get isOpen(): boolean {
    return this.ws.readyState === WebSocket.OPEN && !this.closed;
  }

  sendFrame(frame: WireFrame) {
    if (!this.isOpen) return;
    this.queue.push(frame);
    if (this.queue.length >= this.options.batchSize) this.flush();
  }

  /** L3: one binary JPEG frame. Skips when the socket is congested. */
  sendBinary(data: ArrayBuffer) {
    if (this.isOpen && this.ws.bufferedAmount < 512 * 1024) this.ws.send(data);
  }

  stop() {
    if (this.isOpen) {
      this.flush();
      this.sendJson({ type: "session.stop" });
    }
    this.closed = true;
    this.clearTimers();
    // The server answers session.stop by closing with 1000; close anyway after a grace period.
    setTimeout(() => {
      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        this.ws.close(1000);
      }
    }, 500);
  }

  private flush() {
    if (this.queue.length === 0 || !this.isOpen) return;
    const frames = this.queue;
    this.queue = [];
    this.sendJson({ type: "frames.batch", frames });
  }

  private sendJson(message: object) {
    if (this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(message));
  }

  private clearTimers() {
    if (this.flushTimer) clearInterval(this.flushTimer);
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.flushTimer = this.pingTimer = null;
  }

  private finish(code: number) {
    this.clearTimers();
    const wasStopped = this.closed;
    this.closed = true;
    this.handlers.onClose(wasStopped ? 1000 : code);
  }
}
