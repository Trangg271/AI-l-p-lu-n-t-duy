# backend/app/models/session.py
"""
Pydantic models for SocraticAI debate sessions and LangGraph state.

This module defines the complete domain model hierarchy:

  - **DebateConfig** — immutable session configuration (topic, language, difficulty, positions)
  - **FallacyResult** — a detected logical fallacy with bilingual metadata
  - **Claim** — an atomic factual/normative claim extracted from a turn
  - **Turn** — one turn in the debate transcript with attached analysis
  - **SessionScore** — post-session rubric grading (0-100 scale)
  - **SessionState** — LangGraph TypedDict threaded through every graph node

Session lifecycle models (Create/End request/response) are at the bottom
of the file and reference the domain models above.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, TypedDict
from uuid import UUID, uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

# ─── Core Domain Models ──────────────────────────────────────────────────────


class DebateConfig(BaseModel):
    """Immutable configuration for a debate session.

    Captures the topic, language, difficulty tier, and the assigned
    positions for both the AI and the user.  Created once when a
    session is initialised and never mutated afterwards.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    topic: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="The debate topic / motion to argue about.",
    )
    topic_description: str = Field(
        default="",
        max_length=2000,
        description="Optional longer description providing context for the topic.",
    )
    language: Literal["en", "vi", "bilingual"] = Field(
        default="vi",
        description="Primary language for the debate session.",
    )
    difficulty: Literal["beginner", "advanced", "expert"] = Field(
        default="beginner",
        description="Difficulty tier controlling AI argumentative aggressiveness.",
    )
    ai_position: str = Field(
        default="",
        description="The stance the AI will defend (auto-assigned as opposite of user).",
    )
    user_position: str = Field(
        default="",
        description="The stance the user is defending.",
    )


class FallacyResult(BaseModel):
    """A single detected logical fallacy in a user's argument.

    Includes bilingual metadata (Vietnamese fallacy name), severity
    classification, the offending excerpt, an explanation of *why* it
    is a fallacy, and a constructive suggestion for improvement.
    """

    fallacy_type: str = Field(
        ...,
        description="Canonical English name of the fallacy (e.g. 'Ad Hominem').",
    )
    fallacy_name_vi: str = Field(
        default="",
        description="Vietnamese name of the fallacy for bilingual display.",
    )
    severity: Literal["minor", "moderate", "major"] = Field(
        ...,
        description="How egregious the fallacy is in context.",
    )
    offending_excerpt: str = Field(
        ...,
        description="The exact phrase or sentence containing the fallacy.",
    )
    explanation: str = Field(
        ...,
        description="One or two sentences explaining why this is a fallacy.",
    )
    suggestion: str = Field(
        default="",
        description="Constructive suggestion for how to fix the argument.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence score for this detection (0.0–1.0).",
    )


class Claim(BaseModel):
    """An atomic factual or normative claim extracted from a debate turn.

    Claims are embedded as dense vectors and stored in Qdrant for
    cross-turn memory retrieval and contradiction detection.
    """

    claim_id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Unique identifier for this claim.",
    )
    session_id: str = Field(
        ...,
        description="The session this claim belongs to.",
    )
    turn_number: int = Field(
        ...,
        ge=0,
        description="Which turn this claim was extracted from.",
    )
    speaker: Literal["user", "ai"] = Field(
        ...,
        description="Who made this claim.",
    )
    claim_text: str = Field(
        ...,
        min_length=1,
        description="The actual text of the claim.",
    )
    claim_type: Literal["assertion", "concession", "retraction", "commitment", "question"] = Field(
        default="assertion",
        description="Rhetorical classification of the claim.",
    )
    key_entities: list[str] = Field(
        default_factory=list,
        description="Named entities referenced in this claim.",
    )
    vector_id: str = Field(
        default="",
        description="Qdrant point ID after embedding and upsert.",
    )


class Turn(BaseModel):
    """One turn in the debate — either user or AI.

    Each turn captures the raw content, timestamp, and any analysis
    results (detected fallacies and extracted claims) attached during
    graph execution.
    """

    turn_number: int = Field(
        ...,
        ge=0,
        description="Zero-indexed turn number in the session.",
    )
    speaker: Literal["user", "ai"] = Field(
        ...,
        description="Who spoke this turn.",
    )
    content: str = Field(
        ...,
        description="The spoken/typed argument text.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this turn was recorded.",
    )
    fallacies_detected: list[FallacyResult] = Field(
        default_factory=list,
        description="Fallacies detected in this turn (user turns only).",
    )
    claims_extracted: list[Claim] = Field(
        default_factory=list,
        description="Atomic claims extracted from this turn.",
    )


class SessionScore(BaseModel):
    """Post-session rubric score generated by the configured complex AI model.

    Four sub-dimensions (0-25 each) sum to a total (0-100) which maps
    to a letter grade.  Bilingual strengths/improvements/verdict fields
    support EN and VI output.
    """

    argument_depth: int = Field(
        ...,
        ge=0,
        le=25,
        description="Score for depth and sophistication of arguments (0-25).",
    )
    logical_consistency: int = Field(
        ...,
        ge=0,
        le=25,
        description="Score for internal logical consistency (0-25).",
    )
    evidence_quality: int = Field(
        ...,
        ge=0,
        le=25,
        description="Score for quality and relevance of evidence cited (0-25).",
    )
    rebuttal_effectiveness: int = Field(
        ...,
        ge=0,
        le=25,
        description="Score for effectiveness of rebuttals to AI arguments (0-25).",
    )
    total: int = Field(
        ...,
        ge=0,
        le=100,
        description="Sum of all four sub-scores (0-100).",
    )
    grade: Literal["A", "B", "C", "D", "F"] = Field(
        ...,
        description="Letter grade derived from total score.",
    )
    fallacies_committed: int = Field(
        default=0,
        ge=0,
        description="Total number of fallacies committed across all turns.",
    )
    contradictions_caught: int = Field(
        default=0,
        ge=0,
        description="Number of self-contradictions detected across the session.",
    )
    strengths_en: list[str] = Field(
        default_factory=list,
        description="Key strengths of the user's argumentation (English).",
    )
    strengths_vi: list[str] = Field(
        default_factory=list,
        description="Key strengths of the user's argumentation (Vietnamese).",
    )
    improvements_en: list[str] = Field(
        default_factory=list,
        description="Areas for improvement (English).",
    )
    improvements_vi: list[str] = Field(
        default_factory=list,
        description="Areas for improvement (Vietnamese).",
    )
    verdict_en: str = Field(
        default="",
        description="One-paragraph overall verdict (English).",
    )
    verdict_vi: str = Field(
        default="",
        description="One-paragraph overall verdict (Vietnamese).",
    )

    @model_validator(mode="after")
    def calculate_total(self) -> "SessionScore":
        self.total = (
            self.argument_depth
            + self.logical_consistency
            + self.evidence_quality
            + self.rebuttal_effectiveness
        )
        self.grade = (
            "A"
            if self.total >= 85
            else "B"
            if self.total >= 70
            else "C"
            if self.total >= 55
            else "D"
            if self.total >= 40
            else "F"
        )
        return self


# ─── LangGraph State (TypedDict) ─────────────────────────────────────────────


class SessionState(TypedDict, total=False):
    """LangGraph state schema threaded through every graph node.

    Uses ``TypedDict`` (not Pydantic BaseModel) so that LangGraph can
    merge partial dicts returned by each node via its built-in reducer
    semantics.  All fields are optional (``total=False``) because nodes
    return only the keys they modify.
    """

    session_id: str
    config: DebateConfig
    turns: list[Turn]
    extracted_claims: list[Claim]
    contradiction_alerts: list[str]
    current_user_message: str
    ai_response: str
    fallacy_analysis: list[FallacyResult] | None
    session_score: SessionScore | None
    is_ended: bool


# ─── Session Lifecycle (Request / Response) ───────────────────────────────────


class SessionStatus(str):
    """Session lifecycle status values."""

    PENDING = "pending"
    ACTIVE = "active"
    ENDED = "ended"
    GRADED = "graded"


class CreateSessionRequest(BaseModel):
    """Request body for POST /session/create.

    Creates a new debate session with the specified topic, language,
    and difficulty.  The AI position is auto-assigned as the opposite
    of the user's stated position.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    topic: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Debate topic / motion.",
    )
    topic_description: str = Field(
        default="",
        max_length=2000,
        description="Optional longer description of the topic.",
    )
    language: Literal["en", "vi", "bilingual"] = Field(
        default="vi",
        description="Session language.",
    )
    difficulty: Literal["beginner", "advanced", "expert"] = Field(
        default="beginner",
        description="Difficulty tier.",
    )
    user_position: Literal["pro", "con"] = Field(
        default="pro",
        validation_alias=AliasChoices("user_position", "user_stance"),
        description="The stance the user defends (e.g. 'pro', 'con', or a custom position).",
    )
    max_turns: int | None = Field(
        default=None,
        ge=2,
        le=40,
        description="Override the global max_debate_turns setting.",
    )


class SessionMetadata(BaseModel):
    """Persisted session metadata stored in Redis.

    Contains the full ``DebateConfig`` plus lifecycle fields
    (status, turn count, timestamps, grade).
    """

    session_id: UUID = Field(default_factory=uuid4)
    config: DebateConfig
    status: str = Field(default="pending")
    turn_count: int = Field(default=0)
    max_turns: int = Field(default=20)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    grade: SessionScore | None = None
    turns: list[Turn] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    contradiction_alerts: list[str] = Field(default_factory=list)

    model_config = {"use_enum_values": True}


class SessionHistoryEntry(BaseModel):
    """Compact session details for the browser's practice-history dashboard."""

    session_id: UUID
    topic: str
    user_position: str
    status: str
    turn_count: int
    created_at: datetime
    ended_at: datetime | None
    grade: SessionScore | None


class SessionHistoryRequest(BaseModel):
    """Request for loading a bounded set of sessions recorded by one browser."""

    session_ids: list[UUID] = Field(..., min_length=1, max_length=100)


class SessionHistoryResponse(BaseModel):
    """Found session summaries and IDs that have expired or been removed."""

    sessions: list[SessionHistoryEntry]
    missing_session_ids: list[UUID]


class EndSessionRequest(BaseModel):
    """Request body for POST /session/{session_id}/end."""

    reason: str | None = Field(
        default=None,
        description="Optional reason for ending (user quit, time limit, etc.).",
    )


class EndSessionResponse(BaseModel):
    """Response for POST /session/{session_id}/end."""

    session_id: UUID
    status: str
    message: str
