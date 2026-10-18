"""Dataset storage and manifest (docs/DATASET_AND_ANNOTATION.md §4-§8).

Layout under DATA_ROOT (always outside the repository):

    landmarks/<signer_id>/<session_id>/<sample_id>.npz   one take, landmarks only
    manifests/samples.jsonl     one row per recorded sample (append-only)
    manifests/reviews.jsonl     review events: accept / reject / relabel (append-only)
    manifests/tombstones.jsonl  deletions (append-only; the .npz file is removed)
    reports/                    quality reports

Nothing is rewritten in place: the current state of a sample is the sample row
folded with its latest review and any tombstone. Append-only files keep history
for audits and are friendlier to Windows file locking. No pickle anywhere.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np

from vsl_features.frames import Frame
from vsl_features.spec import FEATURE_SPEC, FeatureSpec

MANIFEST_VERSION = 1

SampleKind = Literal["target", "distractor", "background"]
ReviewStatus = Literal["pending", "accepted", "rejected", "relabelled"]
TombstoneReason = Literal["withdrawal", "cleanup", "rejected"]
SAMPLE_KINDS: tuple[str, ...] = ("target", "distractor", "background")
REVIEW_STATUSES: tuple[str, ...] = ("pending", "accepted", "rejected", "relabelled")
REJECT_REASONS: tuple[str, ...] = (
    "wrong_sign",
    "incomplete",
    "out_of_frame",
    "tracking_failure",
    "other",
)
CONDITION_KEYS: tuple[str, ...] = ("lighting", "background", "camera", "distance")

# Pseudonymous IDs only: never names (public repo, DATASET §3).
SIGNER_ID = re.compile(r"^[A-Z]{2,5}-\d{2,4}$")  # e.g. DEV-01, SGN-0007
SESSION_ID = re.compile(r"^S\d{8}-\d{6}-[0-9a-f]{4}$")
SAMPLE_ID = re.compile(r"^S\d{8}-\d{6}-[0-9a-f]{4}-\d{3}$")
LABEL = re.compile(r"^[A-Z][A-Z0-9_]{1,39}$")  # DEV_01, REST_DESK, VSL_0003
CONSENT_ID = re.compile(r"^(SELF|C-\d{4,6})$")

# Until the consent package (B2) is approved, only the developer's own
# recordings are allowed (owner decision, 2026-10-18).
SELF_CONSENT = "SELF"
DEVELOPER_SIGNER_PREFIX = "DEV-"

RETRIES = 5
RETRY_DELAY_S = 0.2


class DatasetError(ValueError):
    """Invalid manifest data; the message is safe to show (no landmark values)."""


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_session_id(rng: np.random.Generator | None = None, now: datetime | None = None) -> str:
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    suffix = (rng or np.random.default_rng()).integers(0, 16**4)
    return f"S{stamp}-{int(suffix):04x}"


def check_consent(signer_id: str, consent_id: str, third_party_allowed: bool) -> None:
    """Enforce the recording rule in code, not only in documentation."""
    if not SIGNER_ID.fullmatch(signer_id):
        raise DatasetError("signer_id must be pseudonymous, e.g. DEV-01")
    if not CONSENT_ID.fullmatch(consent_id):
        raise DatasetError("consent_id must be SELF or C-<number>")
    if consent_id == SELF_CONSENT:
        if not signer_id.startswith(DEVELOPER_SIGNER_PREFIX):
            raise DatasetError("SELF consent is only for the developer's own signer ID (DEV-..)")
        return
    if not third_party_allowed:
        raise DatasetError(
            "recording other people is blocked until the consent package (B2) is approved"
        )


# --- records -----------------------------------------------------------------------


@dataclass(frozen=True)
class SampleRecord:
    sample_id: str
    signer_id: str
    session_id: str
    label: str
    sample_kind: SampleKind
    consent_id: str
    consent_scopes: list[str]
    dominant_hand: Literal["right", "left"]
    conditions: dict[str, str]
    fps: float
    n_frames: int
    dropped_frames: int
    take_ms: int
    image_w: int
    image_h: int
    feature_spec_version: str
    extractor_version: str
    extractor_backend: str
    file: str  # relative to DATA_ROOT, forward slashes
    sha256: str
    collected_at: str
    manifest_version: int = MANIFEST_VERSION


@dataclass(frozen=True)
class ReviewEvent:
    sample_id: str
    status: ReviewStatus
    reviewer: str
    at: str
    reject_reason: str | None = None
    relabel_to: str | None = None


@dataclass(frozen=True)
class Tombstone:
    sample_id: str
    reason: TombstoneReason
    at: str


@dataclass(frozen=True)
class SampleView:
    """Current state of a sample: record + latest review (tombstoned samples are hidden)."""

    record: SampleRecord
    status: ReviewStatus = "pending"
    reject_reason: str | None = None
    label: str = ""  # effective label (relabel applied)
    reviewed_at: str | None = None

    @property
    def usable(self) -> bool:
        return self.status in ("accepted", "relabelled")


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise DatasetError(message)


def validate_record(record: SampleRecord, spec: FeatureSpec = FEATURE_SPEC) -> None:
    _require(bool(SAMPLE_ID.fullmatch(record.sample_id)), "invalid sample_id")
    _require(bool(SESSION_ID.fullmatch(record.session_id)), "invalid session_id")
    _require(record.sample_id.startswith(record.session_id), "sample_id must extend session_id")
    _require(bool(SIGNER_ID.fullmatch(record.signer_id)), "invalid signer_id")
    _require(bool(LABEL.fullmatch(record.label)), "invalid label")
    _require(record.sample_kind in SAMPLE_KINDS, "invalid sample_kind")
    _require(bool(CONSENT_ID.fullmatch(record.consent_id)), "invalid consent_id")
    _require(record.dominant_hand in ("right", "left"), "invalid dominant_hand")
    _require(set(record.conditions) <= set(CONDITION_KEYS), "unknown condition key")
    _require(record.n_frames > 0 and record.dropped_frames >= 0, "invalid frame counts")
    _require(record.take_ms > 0 and record.fps > 0, "invalid take_ms/fps")
    _require(record.feature_spec_version == spec.version, "feature spec mismatch")
    _require(".." not in record.file and not record.file.startswith("/"), "invalid file path")
    _require(bool(re.fullmatch(r"[0-9a-f]{64}", record.sha256)), "invalid sha256")


def record_from_dict(data: dict[str, Any]) -> SampleRecord:
    names = {f.name for f in fields(SampleRecord)}
    missing = names - set(data) - {"manifest_version"}
    _require(not missing, f"missing fields: {sorted(missing)}")
    unknown = set(data) - names
    _require(not unknown, f"unknown fields: {sorted(unknown)}")
    try:
        record = SampleRecord(**data)
    except TypeError:
        raise DatasetError("malformed sample row") from None
    validate_record(record)
    return record


def review_from_dict(data: dict[str, Any]) -> ReviewEvent:
    try:
        event = ReviewEvent(**data)
    except TypeError:
        raise DatasetError("malformed review row") from None
    _require(event.status in REVIEW_STATUSES and event.status != "pending", "invalid review status")
    if event.status == "rejected":
        _require(event.reject_reason in REJECT_REASONS, "rejected reviews need a known reason")
    if event.status == "relabelled":
        _require(bool(event.relabel_to and LABEL.fullmatch(event.relabel_to)), "invalid relabel_to")
    return event


# --- frames <-> npz ----------------------------------------------------------------


def frames_to_arrays(frames: Sequence[Frame], spec: FeatureSpec = FEATURE_SPEC) -> dict[str, Any]:
    """Fixed-shape arrays with presence masks (absent parts are zeros)."""
    n = len(frames)

    def stack(attr: str, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
        data = np.zeros((n, *shape), dtype=np.float32)
        present = np.zeros(n, dtype=bool)
        for i, frame in enumerate(frames):
            value = getattr(frame, attr)
            if value is not None:
                data[i] = value
                present[i] = True
        return data, present

    out: dict[str, Any] = {"t_ms": np.array([f.t_ms for f in frames], dtype=np.float64)}
    for attr, shape in (
        ("pose", spec.pose_shape),
        ("left_hand", spec.hand_shape),
        ("right_hand", spec.hand_shape),
        ("face", spec.face_shape),
    ):
        out[attr], out[f"{attr}_present"] = stack(attr, shape)
    return out


def arrays_to_frames(arrays: dict[str, Any]) -> list[Frame]:
    def part(attr: str, i: int) -> np.ndarray | None:
        return arrays[attr][i].astype(np.float32) if arrays[f"{attr}_present"][i] else None

    return [
        Frame(
            t_ms=float(t),
            pose=part("pose", i),
            left_hand=part("left_hand", i),
            right_hand=part("right_hand", i),
            face=part("face", i),
        )
        for i, t in enumerate(arrays["t_ms"])
    ]


def load_frames(path: Path) -> list[Frame]:
    with np.load(path, allow_pickle=False) as npz:
        return arrays_to_frames({k: npz[k] for k in npz.files})


def _retry(action: Callable[[], object]) -> None:
    """Windows: antivirus scanners briefly lock newly written files."""
    for attempt in range(RETRIES):
        try:
            action()
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if attempt == RETRIES - 1:
                raise
            time.sleep(RETRY_DELAY_S * (attempt + 1))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --- dataset ---------------------------------------------------------------------


@dataclass
class Dataset:
    root: Path
    _sample_counters: dict[str, int] = field(default_factory=dict)

    @property
    def manifests(self) -> Path:
        return self.root / "manifests"

    def path_of(self, record: SampleRecord) -> Path:
        return self.root / record.file

    def _append(self, name: str, row: dict[str, Any]) -> None:
        self.manifests.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        with (self.manifests / name).open("a", encoding="utf-8") as handle:
            handle.write(line)

    def _rows(self, name: str) -> Iterator[dict[str, Any]]:
        path = self.manifests / name
        if not path.exists():
            return
        with path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        raise DatasetError(f"{name}:{number} is not valid JSON") from None

    def next_sample_id(self, session_id: str) -> str:
        if session_id not in self._sample_counters:
            existing = [r.sample_id for r in self.records() if r.session_id == session_id]
            self._sample_counters[session_id] = len(existing)
        self._sample_counters[session_id] += 1
        return f"{session_id}-{self._sample_counters[session_id]:03d}"

    def write_sample(
        self,
        frames: Sequence[Frame],
        *,
        signer_id: str,
        session_id: str,
        label: str,
        sample_kind: SampleKind,
        consent_id: str,
        consent_scopes: list[str],
        dominant_hand: Literal["right", "left"],
        conditions: dict[str, str],
        take_ms: int,
        image_w: int,
        image_h: int,
        extractor_version: str,
        extractor_backend: str,
        dropped_frames: int = 0,
    ) -> SampleRecord:
        """Write the .npz (temp file, then rename) and append its manifest row."""
        if not frames:
            raise DatasetError("a sample needs at least one frame")
        sample_id = self.next_sample_id(session_id)
        rel = f"landmarks/{signer_id}/{session_id}/{sample_id}.npz"
        dest = self.root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        with tmp.open("wb") as handle:  # closed before rename (Windows)
            np.savez(handle, **frames_to_arrays(frames))
        _retry(lambda: os.replace(tmp, dest))
        span_s = (frames[-1].t_ms - frames[0].t_ms) / 1000.0
        record = SampleRecord(
            sample_id=sample_id,
            signer_id=signer_id,
            session_id=session_id,
            label=label,
            sample_kind=sample_kind,
            consent_id=consent_id,
            consent_scopes=consent_scopes,
            dominant_hand=dominant_hand,
            conditions=conditions,
            fps=round((len(frames) - 1) / span_s, 2) if span_s > 0 else 1.0,
            n_frames=len(frames),
            dropped_frames=dropped_frames,
            take_ms=take_ms,
            image_w=image_w,
            image_h=image_h,
            feature_spec_version=FEATURE_SPEC.version,
            extractor_version=extractor_version,
            extractor_backend=extractor_backend,
            file=rel,
            sha256=sha256_file(dest),
            collected_at=now_iso(),
        )
        try:
            validate_record(record)
        except DatasetError:
            _retry(lambda: dest.unlink(missing_ok=True))
            raise
        self._append("samples.jsonl", asdict(record))
        return record

    def add_review(self, event: ReviewEvent) -> None:
        review_from_dict(asdict(event))  # validate
        if event.sample_id not in {v.record.sample_id for v in self.samples()}:
            raise DatasetError("unknown or deleted sample")
        self._append("reviews.jsonl", asdict(event))

    def delete_sample(self, sample_id: str, reason: TombstoneReason) -> bool:
        """Remove the .npz and append a tombstone. Returns False if already gone."""
        view = next((v for v in self.samples() if v.record.sample_id == sample_id), None)
        if view is None:
            return False
        path = self.path_of(view.record)
        _retry(lambda: path.unlink(missing_ok=True))
        self._append("tombstones.jsonl", asdict(Tombstone(sample_id, reason, now_iso())))
        return True

    def records(self) -> list[SampleRecord]:
        return [record_from_dict(row) for row in self._rows("samples.jsonl")]

    def tombstoned(self) -> set[str]:
        return {str(row["sample_id"]) for row in self._rows("tombstones.jsonl")}

    def samples(self) -> list[SampleView]:
        """Current view: latest review per sample; tombstoned samples are excluded."""
        gone = self.tombstoned()
        latest: dict[str, ReviewEvent] = {}
        for row in self._rows("reviews.jsonl"):
            event = review_from_dict(row)
            latest[event.sample_id] = event
        views = []
        for record in self.records():
            if record.sample_id in gone:
                continue
            review = latest.get(record.sample_id)
            views.append(
                SampleView(
                    record=record,
                    status=review.status if review else "pending",
                    reject_reason=review.reject_reason if review else None,
                    label=(review.relabel_to if review and review.relabel_to else record.label),
                    reviewed_at=review.at if review else None,
                )
            )
        return views

    def verify(self) -> list[str]:
        """Integrity problems (missing files, sha256 mismatches). Empty list = OK."""
        problems = []
        for view in self.samples():
            path = self.path_of(view.record)
            if not path.is_file():
                problems.append(f"{view.record.sample_id}: file missing")
            elif sha256_file(path) != view.record.sha256:
                problems.append(f"{view.record.sample_id}: sha256 mismatch")
        return problems


def ensure_outside_repo(data_root: Path) -> None:
    """Refuse a DATA_ROOT inside a git checkout (public repo: no data in git)."""
    root = data_root.expanduser().resolve()
    for parent in (root, *root.parents):
        if (parent / ".git").exists():
            raise DatasetError(f"DATA_ROOT must be outside the repository (found .git in {parent})")
