import { useEffect, useRef, type RefObject } from "react";

import type { WireFrame } from "../../api/generated/contracts";
import { vi } from "../../i18n/vi";

const WIDTH = 320;
const HEIGHT = 240;
// Signer's left = green, right = orange (arms and hands), torso = blue: raising
// the right hand must turn the right arm AND hand orange (P3 handedness check).
const LEFT_COLOUR = "#6dd58c";
const RIGHT_COLOUR = "#ffb95c";
const TORSO_COLOUR = "#8ab4f8";
const POSE_LINKS: [number, number, string][] = [
  [11, 12, TORSO_COLOUR], [11, 23, TORSO_COLOUR], [12, 24, TORSO_COLOUR], [23, 24, TORSO_COLOUR],
  [11, 13, LEFT_COLOUR], [13, 15, LEFT_COLOUR],
  [12, 14, RIGHT_COLOUR], [14, 16, RIGHT_COLOUR],
];
const HAND_CHAINS = [[0, 1, 2, 3, 4], [0, 5, 6, 7, 8], [0, 9, 10, 11, 12], [0, 13, 14, 15, 16], [0, 17, 18, 19, 20]];

function draw(ctx: CanvasRenderingContext2D, frame: WireFrame | null) {
  ctx.fillStyle = "#0b0d10";
  ctx.fillRect(0, 0, WIDTH, HEIGHT);
  if (!frame) return;
  const at = (p: number[] | undefined): [number, number] | null =>
    p ? [(p[0] as number) * WIDTH, (p[1] as number) * HEIGHT] : null;
  const line = (a: number[] | undefined, b: number[] | undefined) => {
    const pa = at(a);
    const pb = at(b);
    if (!pa || !pb) return;
    ctx.beginPath();
    ctx.moveTo(...pa);
    ctx.lineTo(...pb);
    ctx.stroke();
  };
  ctx.lineWidth = 3;
  if (frame.pose) {
    for (const [a, b, colour] of POSE_LINKS) {
      ctx.strokeStyle = colour;
      line(frame.pose[a], frame.pose[b]);
    }
  }
  ctx.lineWidth = 2;
  for (const [hand, colour] of [
    [frame.left_hand, LEFT_COLOUR],
    [frame.right_hand, RIGHT_COLOUR],
  ] as const) {
    if (!hand) continue;
    ctx.strokeStyle = colour;
    for (const chain of HAND_CHAINS) for (let i = 1; i < chain.length; i++) line(hand[chain[i - 1] as number], hand[chain[i] as number]);
  }
  ctx.fillStyle = "#c4cad3";
  for (const p of frame.face ?? []) {
    const xy = at(p);
    if (xy) ctx.fillRect(xy[0] - 1, xy[1] - 1, 2, 2);
  }
}

/** Mirrored like the camera preview. Redraws from a ref, so frames do not re-render React. */
export function LandmarkOverlay({ frameRef }: { frameRef: RefObject<WireFrame | null> }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const ctx = canvasRef.current?.getContext("2d");
    if (!ctx) return;
    let handle = 0;
    let lastT = -1;
    const loop = () => {
      const frame = frameRef.current;
      if ((frame?.t_ms ?? -1) !== lastT) {
        lastT = frame?.t_ms ?? -1;
        draw(ctx, frame);
      }
      handle = requestAnimationFrame(loop);
    };
    draw(ctx, null);
    handle = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(handle);
  }, [frameRef]);

  return (
    <canvas
      ref={canvasRef}
      className="overlay"
      width={WIDTH}
      height={HEIGHT}
      role="img"
      aria-label={vi.recognition.overlayLabel}
      data-testid="landmark-overlay"
    />
  );
}
