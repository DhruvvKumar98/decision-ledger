from datetime import date, datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# ── Shared literals ────────────────────────────────────────────────────────────

Category = Literal["pricing", "product", "hiring", "market_entry", "operational"]
Status = Literal["active", "succeeded", "failed", "reversed", "superseded"]


# ── Option sub-schema ──────────────────────────────────────────────────────────

class OptionConsidered(BaseModel):
    option: str = Field(..., min_length=1, max_length=500)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)


# ── Request schemas ────────────────────────────────────────────────────────────

class DecisionCreate(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    category: Category
    context: Annotated[str, Field(min_length=10, max_length=5000)]
    options_considered: Annotated[list[OptionConsidered], Field(min_length=1)]
    data_consulted: list[str] = Field(default_factory=list)
    decision_made: Annotated[str, Field(min_length=1)]
    rationale: Annotated[str, Field(min_length=10)]
    expected_outcome: Annotated[str, Field(min_length=10, max_length=2000)]
    review_date: date
    team: Optional[str] = Field(None, max_length=100)
    owner: Optional[str] = Field(None, max_length=100)

    @field_validator("review_date")
    @classmethod
    def review_date_must_be_future(cls, v: date) -> date:
        if v <= date.today():
            raise ValueError("review_date must be a future date")
        return v


class DecisionStatusUpdate(BaseModel):
    status: Status
    actual_outcome: Optional[str] = None


class ReviewCreate(BaseModel):
    reviewer: Optional[str] = Field(None, max_length=100)
    actual_outcome: Annotated[str, Field(min_length=1)]
    outcome_rating: Optional[int] = Field(None, ge=1, le=5)
    lessons_learned: Optional[str] = None


# ── Response schemas ───────────────────────────────────────────────────────────

class ReviewOut(BaseModel):
    id: int
    decision_id: int
    reviewer: Optional[str]
    actual_outcome: str
    outcome_rating: Optional[int]
    lessons_learned: Optional[str]
    reviewed_at: datetime

    model_config = {"from_attributes": True}


class DecisionOut(BaseModel):
    id: int
    title: str
    category: str
    context: str
    options_considered: list[dict]
    data_consulted: list[str]
    decision_made: str
    rationale: str
    expected_outcome: str
    review_date: date
    status: str
    actual_outcome: Optional[str]
    team: Optional[str]
    owner: Optional[str]
    decided_at: datetime
    created_at: datetime
    updated_at: datetime
    reviews: list[ReviewOut] = []

    model_config = {"from_attributes": True}


class DecisionListOut(BaseModel):
    """Lightweight list item — omits reviews for performance."""
    id: int
    title: str
    category: str
    status: str
    review_date: date
    team: Optional[str]
    owner: Optional[str]
    decided_at: datetime

    model_config = {"from_attributes": True}


# ── Analytics response schemas ─────────────────────────────────────────────────

class AccuracyRow(BaseModel):
    category: str
    total_terminal: int
    succeeded: int
    failed: int
    reversed: int
    superseded: int
    accuracy_rate_pct: Optional[float]


class VelocityRow(BaseModel):
    category: str
    total_decisions: int
    avg_horizon_days: Optional[float]
    overdue_count: int
    month_bucket: datetime


class ComplianceRow(BaseModel):
    category: str
    past_due_decisions: int
    reviewed_count: int
    compliance_rate_pct: Optional[float]
    avg_review_lag_days: Optional[float]


class SummaryOut(BaseModel):
    total_decisions: int
    active_decisions: int
    succeeded_decisions: int
    failed_decisions: int
    reversed_decisions: int
    superseded_decisions: int
    overdue_decisions: int
    overall_accuracy_pct: Optional[float]
    overall_reversal_pct: Optional[float]
