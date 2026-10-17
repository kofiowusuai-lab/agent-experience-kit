"""Strict allowlisted wire metadata: never accept raw task contents."""

from datetime import datetime, timezone
from typing import Literal, Annotated
from uuid import UUID
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    StrictBool,
    StrictInt,
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


Name = Annotated[str, Field(min_length=1, max_length=200)]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Count = Annotated[StrictInt, Field(ge=0, le=1000000)]


class Step(Strict):
    id: str = Field(min_length=1, max_length=200)
    state: Literal["pending", "running", "failed", "completed", "done"]
    attempts: StrictInt = Field(ge=0, le=1000000)
    approved: StrictBool
    checks: dict[Name, StrictBool] = Field(default_factory=dict, max_length=100)
    artifact_hashes: list[Hash] = Field(default_factory=list, max_length=1000)


class QA(Strict):
    passed: StrictBool
    checks: dict[Name, StrictBool] = Field(default_factory=dict, max_length=100)
    defect_counts: dict[Literal["critical", "major", "minor"], Count] = Field(
        default_factory=dict
    )


class Payload(Strict):
    status: Literal["pending", "running", "failed", "completed"]
    steps: list[Step] = Field(max_length=1000)
    failure_code: str | None = Field(
        default=None, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$"
    )
    qa: QA | None = None

    @field_validator("steps")
    @classmethod
    def unique_steps(cls, value):
        if len({s.id for s in value}) != len(value):
            raise ValueError("Duplicate step IDs")
        return value


class Event(Strict):
    id: UUID
    producer_id: UUID
    sequence: StrictInt = Field(gt=0, le=2147483647)
    run_id: str = Field(min_length=1, max_length=200)
    kind: Literal[
        "run_started",
        "step_completed",
        "step_failed",
        "step_approved",
        "evidence_invalidated",
        "gate_rejected",
        "snapshot_imported",
        "qa_reviewed",
    ]
    occurred_at: datetime
    payload: Payload

    @field_validator("occurred_at")
    @classmethod
    def utc(cls, value):
        if value.tzinfo is None:
            raise ValueError("UTC timezone required")
        return value.astimezone(timezone.utc)


class Batch(Strict):
    events: list[Event] = Field(min_length=1, max_length=100)


class Login(Strict):
    key: str = Field(min_length=1, max_length=200)


class Review(Strict):
    outcome: Literal["accepted", "needs_changes", "escalated"]
    note: str = Field(min_length=1, max_length=2000)
