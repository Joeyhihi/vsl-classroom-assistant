"""Utterance segmenter (docs/AI_ML_STRATEGY.md §2, step 5).

Turns a frame stream into whole message units, so a single camera frame is
never treated as a sign. Timing uses `t_ms`, not frame counts, so behaviour
does not change with the frame rate.

    waiting_for_hands ── hand above rest line + moving ──▶ signing
          ▲   ready ◀──────── utterance closed ◀────────────┘
          │                (rest/no hands ≥ pause_tolerance, long stillness,
          └ no hands          or max duration)

Hands are "active" when visible and above the rest line (roughly the waist).
Pauses shorter than `pause_tolerance_ms` inside a unit are tolerated.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from vsl_features.frames import Frame
from vsl_features.normalize import BodyFrame, body_frame

SegmenterState = Literal["waiting_for_hands", "ready", "signing"]


@dataclass(frozen=True)
class SegmenterConfig:
    """Defaults tuned on the developer's own L2 takes, laptop webcam (P4, 2026-10-18):
    resting hands visible at the frame bottom sit at ~0.6 shoulder widths below the
    shoulders, a raised hold at ~0.4, signing at <= 0.2; held-still jitter reaches
    ~0.6 shoulder widths/s, signing ~1.3. PROVISIONAL (1 take per label, one
    person, one framing); re-check with more takes and with Deaf signers.
    """

    rest_line: float = 0.45  # shoulder widths below the shoulder midpoint (was 1.2)
    start_speed: float = 1.0  # smoothed shoulder widths per second (was 0.6, raw)
    start_ms: float = 120.0
    still_speed: float = 0.7  # smoothed; above tracker jitter of a held pose (was 0.15)
    speed_smoothing_ms: float = 150.0  # EMA time constant; 0 disables smoothing
    still_end_ms: float = 1500.0  # hands up but motionless this long ends the unit
    pause_tolerance_ms: float = 600.0  # rest/no hands this long ends the unit
    min_duration_ms: float = 300.0
    max_duration_ms: float = 4000.0
    preroll_ms: float = 150.0


@dataclass(frozen=True)
class Utterance:
    frames: list[Frame]
    start_ms: float
    end_ms: float
    closed_ms: float  # t_ms of the frame that closed the unit
    reason: Literal["rest", "still", "max_duration"]

    @property
    def hysteresis_ms(self) -> float:
        return self.closed_ms - self.end_ms


@dataclass
class _Track:
    frames: list[Frame] = field(default_factory=list)
    start_ms: float = 0.0
    last_active_ms: float = 0.0
    last_moving_ms: float = 0.0
    last_active_index: int = 0
    last_moving_index: int = 0


Wrists = dict[str, np.ndarray]  # "left"/"right" → wrist (shoulder widths)


def _active_wrists(body: BodyFrame | None, rest_line: float) -> Wrists:
    if body is None:
        return {}
    wrists = {"left": body.left_wrist, "right": body.right_wrist}
    return {side: w for side, w in wrists.items() if w is not None and w[1] < rest_line}


def wrist_speed(prev: tuple[float, Wrists] | None, t_ms: float, wrists: Wrists) -> float:
    """Fastest wrist, comparing each hand only with ITSELF in the previous frame.

    Comparing unlabelled lists measured the distance between the two hands as
    "motion" when one hand appeared and the other vanished.
    """
    if prev is None:
        return 0.0
    dt = (t_ms - prev[0]) / 1000.0
    common = wrists.keys() & prev[1].keys()
    if dt <= 0 or not common:
        return 0.0
    return max(float(np.linalg.norm(wrists[s] - prev[1][s])) for s in common) / dt


class UtteranceSegmenter:
    def __init__(self, aspect: float, config: SegmenterConfig | None = None) -> None:
        self.aspect = aspect
        self.config = config or SegmenterConfig()
        self._preroll: deque[Frame] = deque()
        self.reset()

    def reset(self) -> None:
        self.state: SegmenterState = "waiting_for_hands"
        self._preroll.clear()
        self._candidate_since: float | None = None
        self._prev: tuple[float, Wrists] | None = None
        self._smoothed: float | None = None
        self._track: _Track | None = None

    def _speed(self, t_ms: float, wrists: Wrists) -> float:
        """Exponentially smoothed wrist speed: tracker jitter must not look like motion."""
        prev_t = self._prev[0] if self._prev else None
        raw = wrist_speed(self._prev, t_ms, wrists)
        self._prev = (t_ms, wrists)
        tau = self.config.speed_smoothing_ms
        if tau <= 0 or self._smoothed is None or prev_t is None or t_ms <= prev_t:
            self._smoothed = raw
        else:
            alpha = 1.0 - math.exp(-(t_ms - prev_t) / tau)
            self._smoothed += alpha * (raw - self._smoothed)
        return self._smoothed

    def push(self, frame: Frame) -> Utterance | None:
        """Feed one frame; returns an utterance when one closes."""
        cfg = self.config
        t = frame.t_ms
        body = body_frame(frame, self.aspect)
        wrists = _active_wrists(body, cfg.rest_line)
        active = bool(wrists)
        speed = self._speed(t, wrists)

        if self._track is None:
            self._preroll.append(frame)
            if active and speed >= cfg.start_speed:
                if self._candidate_since is None:
                    self._candidate_since = t
            else:
                self._candidate_since = None
            # Keep `preroll_ms` before the candidate start (not before now), so a
            # low frame rate does not cut the first moving frames off the unit.
            anchor = self._candidate_since if self._candidate_since is not None else t
            while self._preroll and anchor - self._preroll[0].t_ms > cfg.preroll_ms:
                self._preroll.popleft()
            if self._candidate_since is not None and t - self._candidate_since >= cfg.start_ms:
                self._begin(t)
            if self._track is None:
                self.state = "ready" if frame.hands_visible else "waiting_for_hands"
            return None

        track = self._track
        track.frames.append(frame)
        if active:
            track.last_active_ms = t
            track.last_active_index = len(track.frames)
            if speed >= cfg.still_speed:
                track.last_moving_ms = t
                track.last_moving_index = len(track.frames)
        if t - track.start_ms >= cfg.max_duration_ms:
            return self._close(t, "max_duration")
        if not active and t - track.last_active_ms >= cfg.pause_tolerance_ms:
            return self._close(t, "rest")
        if active and t - track.last_moving_ms >= cfg.still_end_ms:
            return self._close(t, "still")
        return None

    def _begin(self, t_ms: float) -> None:
        frames = list(self._preroll)
        self._track = _Track(
            frames=frames,
            start_ms=frames[0].t_ms if frames else t_ms,
            last_active_ms=t_ms,
            last_moving_ms=t_ms,
            last_active_index=len(frames),
            last_moving_index=len(frames),
        )
        self._preroll.clear()
        self._candidate_since = None
        self.state = "signing"

    def _close(
        self, t_ms: float, reason: Literal["rest", "still", "max_duration"]
    ) -> Utterance | None:
        track = self._track
        assert track is not None
        self._track = None
        self._prev = None
        self._smoothed = None
        self.state = "ready"
        # A "still" close ends the unit at the last MOVING frame: the motionless
        # hold is the wait, not part of the sign (and must not reach the classifier).
        cut = track.last_moving_index if reason == "still" else track.last_active_index
        frames = track.frames[:cut]
        end_ms = frames[-1].t_ms if frames else track.start_ms
        if end_ms - track.start_ms < self.config.min_duration_ms:
            return None
        return Utterance(frames, track.start_ms, end_ms, t_ms, reason)
