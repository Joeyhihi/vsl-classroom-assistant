import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SessionStart, WireFrame } from "./generated/contracts";
import { NO_RECONNECT_CODES, RecognitionSocket, parseServerMessage, recognitionUrl } from "./ws";

class FakeSocket {
  static instances: FakeSocket[] = [];
  static OPEN = 1;
  readyState = 0;
  binaryType = "blob";
  bufferedAmount = 0;
  sent: (string | ArrayBuffer)[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;

  constructor(public url: string) {
    FakeSocket.instances.push(this);
  }

  open() {
    this.readyState = 1;
    this.onopen?.();
  }

  send(data: string | ArrayBuffer) {
    this.sent.push(data);
  }

  close(code = 1000) {
    this.readyState = 3;
    this.onclose?.({ code });
  }

  json() {
    return this.sent.filter((d): d is string => typeof d === "string").map((d) => JSON.parse(d) as { type: string });
  }
}

const START: SessionStart = {
  type: "session.start",
  protocol_version: 1,
  feature_spec_version: "fs-1",
  extraction_mode: "client",
  image_width: 640,
  image_height: 480,
  fps_hint: 20,
  dominant_hand: "right",
};

const frame = (t: number): WireFrame => ({ t_ms: t, pose: null, left_hand: null, right_hand: null, face: null });

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("WebSocket", FakeSocket);
  FakeSocket.instances = [];
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function connect(handlers = { onMessage: vi.fn(), onClose: vi.fn() }) {
  const socket = new RecognitionSocket("ws://x", START, handlers, { batchSize: 3, flushMs: 100, pingMs: 5000 }, FakeSocket as unknown as typeof WebSocket);
  const fake = FakeSocket.instances[0] as FakeSocket;
  fake.open();
  return { socket, fake, handlers };
}

describe("RecognitionSocket", () => {
  it("sends session.start on open, batches frames and flushes on a timer", () => {
    const { socket, fake } = connect();
    expect(fake.json()[0]?.type).toBe("session.start");

    [1, 2, 3, 4].forEach((t) => socket.sendFrame(frame(t)));
    expect(fake.json().filter((m) => m.type === "frames.batch")).toHaveLength(1); // full batch of 3
    vi.advanceTimersByTime(100);
    const batches = fake.json().filter((m) => m.type === "frames.batch") as unknown as { frames: WireFrame[] }[];
    expect(batches.map((b) => b.frames.length)).toEqual([3, 1]);
  });

  it("pings to keep the session alive", () => {
    const { fake } = connect();
    vi.advanceTimersByTime(10_000);
    expect(fake.json().filter((m) => m.type === "ping")).toHaveLength(2);
  });

  it("parses known server messages only", () => {
    const { fake, handlers } = connect();
    fake.onmessage?.({ data: JSON.stringify({ type: "pong" }) });
    fake.onmessage?.({ data: JSON.stringify({ type: "unknown" }) });
    fake.onmessage?.({ data: "not json" });
    expect(handlers.onMessage).toHaveBeenCalledTimes(1);
  });

  it("stop() sends session.stop and reports a normal close", () => {
    const { socket, fake, handlers } = connect();
    socket.stop();
    expect(fake.json().at(-1)?.type).toBe("session.stop");
    fake.close(1006);
    expect(handlers.onClose).toHaveBeenCalledWith(1000);
  });

  it("reports abnormal closes", () => {
    const { fake, handlers } = connect();
    fake.close(1006);
    expect(handlers.onClose).toHaveBeenCalledWith(1006);
  });

  it("drops binary frames when the socket is congested", () => {
    const { socket, fake } = connect();
    socket.sendBinary(new ArrayBuffer(8));
    fake.bufferedAmount = 10 * 1024 * 1024;
    socket.sendBinary(new ArrayBuffer(8));
    expect(fake.sent.filter((d) => d instanceof ArrayBuffer)).toHaveLength(1);
  });
});

describe("helpers", () => {
  it("builds the WS URL through the same origin", () => {
    expect(recognitionUrl({ protocol: "http:", host: "localhost:5173" } as Location)).toBe(
      "ws://localhost:5173/api/v1/recognition/ws",
    );
  });

  it("does not reconnect after protocol or policy closes", () => {
    expect([1008, 4001, 4002, 4005, 4006].every((c) => NO_RECONNECT_CODES.has(c))).toBe(true);
    expect(NO_RECONNECT_CODES.has(1006)).toBe(false);
    expect(parseServerMessage('{"type":"status"}')).not.toBeNull();
  });
});
