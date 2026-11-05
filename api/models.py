from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


VALID_CATEGORIES = ("pricing", "product", "hiring", "market_entry", "operational")
VALID_STATUSES = ("active", "succeeded", "failed", "reversed", "superseded")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = Column(Integer, primary_key=True)
    title: Mapped[str] = Column(String(200), nullable=False)
    category: Mapped[str] = Column(String(20), nullable=False)
    context: Mapped[str] = Column(Text, nullable=False)
    options_considered: Mapped[list] = Column(JSONB, nullable=False, default=list)
    data_consulted: Mapped[list] = Column(ARRAY(Text), nullable=False, default=list)
    decision_made: Mapped[str] = Column(Text, nullable=False)
    rationale: Mapped[str] = Column(Text, nullable=False)
    expected_outcome: Mapped[str] = Column(String(2000), nullable=False)
    review_date: Mapped[date] = Column(Date, nullable=False)
    status: Mapped[str] = Column(String(20), nullable=False, default="active")
    actual_outcome: Mapped[str | None] = Column(Text)
    team: Mapped[str | None] = Column(String(100))
    owner: Mapped[str | None] = Column(String(100))
    decided_at: Mapped[datetime] = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    reviews: Mapped[list["Review"]] = relationship(
        "Review", back_populates="decision", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint(
            "category IN ('pricing','product','hiring','market_entry','operational')",
            name="decisions_category_check",
        ),
        CheckConstraint(
            "status IN ('active','succeeded','failed','reversed','superseded')",
            name="decisions_status_check",
        ),
        Index("idx_decisions_category", "category"),
        Index("idx_decisions_status", "status"),
        Index("idx_decisions_review_date", "review_date"),
        Index("idx_decisions_decided_at", "decided_at"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = Column(Integer, primary_key=True)
    decision_id: Mapped[int] = Column(
        Integer, ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False
    )
    reviewer: Mapped[str | None] = Column(String(100))
    actual_outcome: Mapped[str] = Column(Text, nullable=False)
    outcome_rating: Mapped[int | None] = Column(SmallInteger)
    lessons_learned: Mapped[str | None] = Column(Text)
    reviewed_at: Mapped[datetime] = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    decision: Mapped["Decision"] = relationship("Decision", back_populates="reviews")

    __table_args__ = (
        CheckConstraint("outcome_rating BETWEEN 1 AND 5", name="reviews_rating_check"),
        Index("idx_reviews_decision_id", "decision_id"),
    )
