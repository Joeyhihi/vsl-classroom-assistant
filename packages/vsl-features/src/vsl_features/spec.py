"""Feature spec "fs-1": which landmarks travel over the wire and in what shape.

The server sends this to the browser in `session.started`, so the packer never
hard-codes indices (docs/API_CONTRACTS.md, ADR-009).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# MediaPipe Face Mesh indices kept for non-manual features (about 40 points):
# outer lips, eyebrows, eye corners/lids, nose tip and chin.
FACE_INDICES: tuple[int, ...] = (
    # outer lips
    61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185,
    # eyebrows (signer's right, then left)
    70, 63, 105, 66, 107, 336, 296, 334, 293, 300,
    # eyes
    33, 133, 159, 145, 362, 263, 386, 374,
    # nose tip, chin
    1, 152,
)  # fmt: skip

# MediaPipe Pose indices used for normalisation and upper-body features.
POSE_NOSE = 0
POSE_LEFT_SHOULDER = 11
POSE_RIGHT_SHOULDER = 12
POSE_UPPER_BODY: tuple[int, ...] = (0, 11, 12, 13, 14, 15, 16, 23, 24)

HAND_WRIST = 0
HAND_MIDDLE_MCP = 9
FACE_NOSE_TIP_POSITION = FACE_INDICES.index(1)


@dataclass(frozen=True)
class FeatureSpec:
    version: str
    pose_shape: tuple[int, int]
    hand_shape: tuple[int, int]
    face_indices: tuple[int, ...] = field(default=FACE_INDICES)

    @property
    def face_shape(self) -> tuple[int, int]:
        return (len(self.face_indices), 3)

    @property
    def feature_dim(self) -> int:
        """Length of the per-frame vector produced by `normalize.frame_features`."""
        pose = len(POSE_UPPER_BODY) * 2
        hand = 2 + self.hand_shape[0] * 3 + 1  # wrist position, shape, presence
        face = len(self.face_indices) * 2 + 1  # positions, presence
        return pose + 2 * hand + face

    def to_wire(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "face_indices": list(self.face_indices),
            "shapes": {
                "pose": list(self.pose_shape),
                "hand": list(self.hand_shape),
                "face": list(self.face_shape),
            },
        }


FEATURE_SPEC = FeatureSpec(version="fs-1", pose_shape=(33, 4), hand_shape=(21, 3))
