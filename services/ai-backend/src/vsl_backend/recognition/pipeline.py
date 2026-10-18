"""Frames → utterance → features → classifier → decision → cooldown."""

from __future__ import annotations

import time
from dataclasses import dataclass

from vsl_backend.recognition.classifiers import Classifier
from vsl_backend.schemas.recognition import (
    PredictionMessage,
    PredictionTimings,
    ScoredLabelWire,
    ServerState,
    UtteranceSpan,
)
from vsl_features.decoding import CooldownFilter
from vsl_features.frames import Frame
from vsl_features.normalize import sequence_features
from vsl_features.segmentation import SegmenterConfig, UtteranceSegmenter


@dataclass(frozen=True)
class PipelineOutput:
    state: ServerState
    prediction: PredictionMessage | None = None


class RecognitionPipeline:
    def __init__(
        self,
        classifier: Classifier,
        aspect: float,
        cooldown_ms: float = 1500.0,
        segmenter_config: SegmenterConfig | None = None,
    ) -> None:
        self._classifier = classifier
        self._aspect = aspect
        self._segmenter = UtteranceSegmenter(aspect, segmenter_config)
        self._cooldown = CooldownFilter(cooldown_ms)
        self._count = 0
        self.suppressed = 0

    def push(self, frame: Frame) -> PipelineOutput:
        utterance = self._segmenter.push(frame)
        if utterance is None:
            return PipelineOutput(self._segmenter.state)

        started = time.perf_counter()
        features = sequence_features(utterance.frames, self._aspect)
        decision = self._classifier.classify(features)
        inference_ms = (time.perf_counter() - started) * 1000

        if (
            decision.status != "rejected"
            and decision.top
            and not self._cooldown.allow(decision.top[0].gloss_id, utterance.end_ms)
        ):
            self.suppressed += 1
            return PipelineOutput(self._segmenter.state)

        self._count += 1
        prediction = PredictionMessage(
            prediction_id=f"p_{self._count:04d}",
            model_id=self._classifier.model_id,
            status=decision.status,
            utterance=UtteranceSpan(
                start_ms=utterance.start_ms,
                end_ms=utterance.end_ms,
                n_frames=len(utterance.frames),
                close_reason=utterance.reason,
            ),
            top=[
                ScoredLabelWire(gloss_id=s.gloss_id, text_vi=s.text_vi, icon=s.icon, score=s.score)
                for s in decision.top
            ],
            timings=PredictionTimings(
                hysteresis_ms=round(utterance.hysteresis_ms, 1),
                inference_ms=round(inference_ms, 2),
            ),
        )
        return PipelineOutput(self._segmenter.state, prediction)
