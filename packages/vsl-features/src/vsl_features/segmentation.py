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

from collections import deque
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from vsl_features.frames import Frame
from vsl_features.normalize import BodyFrame, body_frame

SegmenterState = Literal["waiting_for_hands", "ready", "signing"]


@dataclass(frozen=True)
class SegmenterConfig:
    rest_line: float = 1.2  # shoulder widths below the shoulder midpoint
    start_speed: float = 0.6  # shoulder widths per second
    start_ms: float = 120.0
    still_speed: float = 0.15
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


def _active_wrists(body: BodyFrame | None, rest_line: float) -> list[np.ndarray]:
    if body is None:
        return []
    wrists = [w for w in (body.left_wrist, body.right_wrist) if w is not None]
    return [w for w in wrists if w[1] < rest_line]


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
        self._prev: tuple[float, list[np.ndarray]] | None = None
        self._track: _Track | None = None

    def _speed(self, t_ms: float, wrists: list[np.ndarray]) -> float:
        prev = self._prev
        self._prev = (t_ms, wrists)
        if prev is None or not wrists or not prev[1] or len(prev[1]) != len(wrists):
            return 0.0
        dt = (t_ms - prev[0]) / 1000.0
        if dt <= 0:
            return 0.0
        return max(float(np.linalg.norm(a - b)) for a, b in zip(wrists, prev[1], strict=True)) / dt

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
        self.state = "ready"
        frames = track.frames[: track.last_active_index]
        end_ms = frames[-1].t_ms if frames else track.start_ms
        if end_ms - track.start_ms < self.config.min_duration_ms:
            return None
        return Utterance(frames, track.start_ms, end_ms, t_ms, reason)
