import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useCamera } from "./useCamera";

function fakeStream() {
  const track = new EventTarget() as EventTarget & { stop: () => void; getSettings: () => object };
  track.stop = vi.fn();
  track.getSettings = () => ({ deviceId: "cam-1" });
  const stream = { getTracks: () => [track], getVideoTracks: () => [track] } as unknown as MediaStream;
  return { stream, track };
}

function mockGetUserMedia(impl: () => Promise<MediaStream>) {
  const getUserMedia = vi.fn(impl);
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia },
    configurable: true,
  });
  return getUserMedia;
}

afterEach(() => {
  Reflect.deleteProperty(navigator, "mediaDevices");
});

describe("useCamera", () => {
  it("does not request the camera until start() is called", () => {
    const getUserMedia = mockGetUserMedia(() => Promise.resolve(fakeStream().stream));
    const { result } = renderHook(() => useCamera());

    expect(result.current.state.kind).toBe("idle");
    expect(getUserMedia).not.toHaveBeenCalled();
  });

  it("becomes active, and stop() releases the tracks", async () => {
    const { stream, track } = fakeStream();
    mockGetUserMedia(() => Promise.resolve(stream));
    const { result } = renderHook(() => useCamera());

    await act(() => result.current.start());
    expect(result.current.state).toMatchObject({ kind: "active", deviceId: "cam-1" });

    act(() => result.current.stop());
    expect(result.current.state.kind).toBe("idle");
    expect(track.stop).toHaveBeenCalled();
  });

  it.each([
    ["NotAllowedError", "denied"],
    ["NotFoundError", "unavailable"],
    ["NotReadableError", "in_use"],
  ])("reports %s as %s", async (name, failure) => {
    mockGetUserMedia(() => Promise.reject(new DOMException("x", name)));
    const { result } = renderHook(() => useCamera());

    await act(() => result.current.start());
    expect(result.current.state).toEqual({ kind: "failed", failure });
  });

  it("reports unavailable when the track ends (camera unplugged)", async () => {
    const { stream, track } = fakeStream();
    mockGetUserMedia(() => Promise.resolve(stream));
    const { result } = renderHook(() => useCamera());
    await act(() => result.current.start());

    act(() => {
      track.dispatchEvent(new Event("ended"));
    });
    expect(result.current.state).toEqual({ kind: "failed", failure: "unavailable" });
  });

  it("reports insecure when mediaDevices is missing", async () => {
    const { result } = renderHook(() => useCamera());

    await act(() => result.current.start());
    expect(result.current.state).toEqual({ kind: "failed", failure: "insecure" });
  });

  it("stops a stream that arrives after stop() was pressed", async () => {
    const { stream, track } = fakeStream();
    let resolve!: (s: MediaStream) => void;
    mockGetUserMedia(() => new Promise((r) => (resolve = r)));
    const { result } = renderHook(() => useCamera());

    let pending!: Promise<void>;
    act(() => {
      pending = result.current.start();
    });
    act(() => result.current.stop());
    await act(async () => {
      resolve(stream);
      await pending;
    });

    expect(result.current.state.kind).toBe("idle");
    expect(track.stop).toHaveBeenCalled();
  });
});
