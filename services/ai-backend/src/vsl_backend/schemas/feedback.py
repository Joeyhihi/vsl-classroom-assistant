"""Feedback contracts (Phase 6, FR-13). No free text: only IDs, a score and a verdict."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ID = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$"
GLOSS = r"^[A-Z][A-Z0-9_]{1,39}$"


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(pattern=ID)
    prediction_id: str = Field(pattern=ID)
    model_id: str = Field(pattern=ID)
    predicted_gloss_id: str | None = Field(default=None, pattern=GLOSS)
    confidence: float = Field(ge=0, le=1)
    verdict: Literal["correct", "incorrect", "unsure"]
    expected_gloss_id: str | None = Field(default=None, pattern=GLOSS)
    # no free-text comment in the MVP (privacy)


class FeedbackCreated(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    feedback_id: str
