"""Recorder service: sessions, sample ingest and review on top of `vsl_features.dataset`.

Enforces in code: the recorder is off unless enabled; DATA_ROOT is outside the
repository; only SELF consent for DEV-.. signers until B2 is approved; labels
must come from the configured vocabulary; frames are validated one by one.
Landmark values are never logged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from vsl_backend.config import Settings
from vsl_backend.errors import AppError
from vsl_backend.schemas.common import ErrorCode
from vsl_backend.schemas.recordings import (
    RecorderConfig,
    RecorderVocabularyItem,
    ReviewCreate,
    SampleCreate,
    SampleSummary,
    SessionCreate,
)
from vsl_features import FEATURE_SPEC
from vsl_features.dataset import (
    CONDITION_KEYS,
    LABEL,
    Dataset,
    DatasetError,
    ReviewEvent,
    SampleView,
    check_consent,
    ensure_outside_repo,
    new_session_id,
    now_iso,
)
from vsl_features.frames import Frame, FrameError, parse_frame
from vsl_features.vocabulary import Vocabulary, load_vocabulary

logger = logging.getLogger(__name__)

# A take where fewer than half the frames are valid is a tracking failure, not data.
MIN_VALID_RATIO = 0.5


@dataclass(frozen=True)
class RecordingSession:
    session_id: str
    signer_id: str
    consent_id: str
    dominant_hand: str
    conditions: dict[str, str]
    image_width: int
    image_height: int
    extractor_version: str
    extractor_backend: str


def summary(view: SampleView) -> SampleSummary:
    r = view.record
    return SampleSummary(
        sample_id=r.sample_id,
        session_id=r.session_id,
        signer_id=r.signer_id,
        label=view.label,
        recorded_label=r.label,
        sample_kind=r.sample_kind,
        status=view.status,
        reject_reason=view.reject_reason,
        n_frames=r.n_frames,
        dropped_frames=r.dropped_frames,
        fps=r.fps,
        take_ms=r.take_ms,
        collected_at=r.collected_at,
    )


class RecorderService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.dataset: Dataset | None = None
        self.vocabulary: Vocabulary | None = None
        self.unavailable: str | None = None
        self._sessions: dict[str, RecordingSession] = {}
        if not settings.recorder_enabled:
            self.unavailable = "recorder is disabled (VSL_RECORDER_ENABLED=false)"
            return
        root = settings.resolved_data_root
        try:
            ensure_outside_repo(root)
            self.vocabulary = load_vocabulary(settings.dev_vocabulary_path)
        except DatasetError as exc:
            self.unavailable = str(exc)
            logger.warning("recorder unavailable: %s", exc)
            return
        self.dataset = Dataset(root)

    # --- helpers -------------------------------------------------------------------

    def _require(self) -> tuple[Dataset, Vocabulary]:
        if self.dataset is None or self.vocabulary is None:
            raise AppError(ErrorCode.RECORDER_DISABLED, self.unavailable or "recorder off", 403)
        return self.dataset, self.vocabulary

    def config(self) -> RecorderConfig:
        vocab = self.vocabulary
        return RecorderConfig(
            enabled=self.dataset is not None,
            reason=self.unavailable,
            third_party_allowed=self.settings.third_party_recording_enabled,
            data_root=str(self.dataset.root) if self.dataset else None,
            vocabulary_version=vocab.version if vocab else None,
            developer_only_vocabulary=vocab.developer_only if vocab else False,
            items=[
                RecorderVocabularyItem(
                    gloss_id=i.gloss_id, text_vi=i.text_vi, icon=i.icon, sample_kind=i.sample_kind
                )
                for i in (vocab.items if vocab else ())
            ],
        )

    # --- sessions ------------------------------------------------------------------

    def create_session(self, body: SessionCreate) -> RecordingSession:
        self._require()
        try:
            check_consent(
                body.signer_id, body.consent_id, self.settings.third_party_recording_enabled
            )
        except DatasetError as exc:
            raise AppError(ErrorCode.CONSENT_REQUIRED, str(exc), 403) from None
        if body.feature_spec_version != FEATURE_SPEC.version:
            raise AppError(
                ErrorCode.FEATURE_SPEC_MISMATCH, f"server spec is {FEATURE_SPEC.version}", 422
            )
        unknown = set(body.conditions) - set(CONDITION_KEYS)
        if unknown:
            raise AppError(ErrorCode.VALIDATION_ERROR, f"unknown conditions {sorted(unknown)}", 422)
        session = RecordingSession(
            session_id=new_session_id(),
            signer_id=body.signer_id,
            consent_id=body.consent_id,
            dominant_hand=body.dominant_hand,
            conditions={k: v[:32] for k, v in body.conditions.items()},
            image_width=body.image_width,
            image_height=body.image_height,
            extractor_version=body.extractor_version,
            extractor_backend=body.extractor_backend,
        )
        self._sessions[session.session_id] = session
        return session

    # --- samples -------------------------------------------------------------------

    def add_sample(self, session_id: str, body: SampleCreate) -> SampleSummary:
        dataset, vocab = self._require()
        session = self._sessions.get(session_id)
        if session is None:
            raise AppError(ErrorCode.NOT_FOUND, "unknown session (start a new one)", 404)
        item = vocab.get(body.label)
        if item is None or not LABEL.fullmatch(body.label):
            raise AppError(ErrorCode.VALIDATION_ERROR, "label is not in the vocabulary", 422)

        frames: list[Frame] = []
        dropped = 0
        last_t = -1.0
        for raw in body.frames:
            try:
                frame = parse_frame(raw)
            except FrameError:
                dropped += 1
                continue
            if frame.t_ms <= last_t:
                dropped += 1
                continue
            last_t = frame.t_ms
            frames.append(frame)
        if len(frames) < max(2, MIN_VALID_RATIO * len(body.frames)):
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "too many invalid frames in this take",
                422,
                {"valid": len(frames), "received": len(body.frames)},
            )
        try:
            record = dataset.write_sample(
                frames,
                signer_id=session.signer_id,
                session_id=session.session_id,
                label=body.label,
                sample_kind=item.sample_kind,
                consent_id=session.consent_id,
                # SELF consent covers landmarks only. Third-party scopes will come from
                # the consent register once B2 exists.
                consent_scopes=["landmarks"],
                dominant_hand="left" if session.dominant_hand == "left" else "right",
                conditions=session.conditions,
                take_ms=body.take_ms,
                image_w=session.image_width,
                image_h=session.image_height,
                extractor_version=session.extractor_version,
                extractor_backend=session.extractor_backend,
                dropped_frames=dropped,
            )
        except DatasetError as exc:
            raise AppError(ErrorCode.VALIDATION_ERROR, str(exc), 422) from None
        logger.info("recorded sample %s (%d frames)", record.sample_id, record.n_frames)
        return summary(SampleView(record=record, label=record.label))

    def list_samples(self, session_id: str | None, status: str | None) -> list[SampleSummary]:
        dataset, _ = self._require()
        views = dataset.samples()
        return [
            summary(v)
            for v in views
            if (session_id is None or v.record.session_id == session_id)
            and (status is None or v.status == status)
        ]

    def sample_view(self, sample_id: str) -> SampleView:
        dataset, _ = self._require()
        view = next((v for v in dataset.samples() if v.record.sample_id == sample_id), None)
        if view is None:
            raise AppError(ErrorCode.NOT_FOUND, "unknown or deleted sample", 404)
        return view

    def sample_path(self, view: SampleView) -> Path:
        dataset, _ = self._require()
        return dataset.path_of(view.record)

    def review(self, sample_id: str, body: ReviewCreate) -> SampleSummary:
        dataset, vocab = self._require()
        self.sample_view(sample_id)
        if body.status == "relabelled" and (
            body.relabel_to is None or not vocab.get(body.relabel_to)
        ):
            raise AppError(ErrorCode.VALIDATION_ERROR, "relabel_to must be in the vocabulary", 422)
        try:
            dataset.add_review(
                ReviewEvent(
                    sample_id=sample_id,
                    status=body.status,
                    reviewer=body.reviewer,
                    at=now_iso(),
                    reject_reason=body.reject_reason,
                    relabel_to=body.relabel_to if body.status == "relabelled" else None,
                )
            )
        except DatasetError as exc:
            raise AppError(ErrorCode.VALIDATION_ERROR, str(exc), 422) from None
        return summary(self.sample_view(sample_id))
