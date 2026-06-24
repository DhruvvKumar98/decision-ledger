from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas import (
    AccuracyRow,
    ComplianceRow,
    SummaryOut,
    VelocityRow,
)

router = APIRouter()

Db = Annotated[AsyncSession, Depends(get_db)]


@router.get("/summary", response_model=SummaryOut)
async def get_summary(db: Db):
    """Overall portfolio summary. Public."""
    result = await db.execute(text("SELECT * FROM v_decision_summary"))
    row = result.mappings().one()
    return dict(row)


@router.get("/accuracy", response_model=list[AccuracyRow])
async def get_accuracy(db: Db):
    """Decision accuracy rate by category. Public."""
    result = await db.execute(text("SELECT * FROM v_decision_accuracy"))
    return [dict(r) for r in result.mappings().all()]


@router.get("/velocity", response_model=list[VelocityRow])
async def get_velocity(db: Db):
    """Decision velocity (horizon + overdue) by category and month. Public."""
    result = await db.execute(text("SELECT * FROM v_decision_velocity"))
    return [dict(r) for r in result.mappings().all()]


@router.get("/compliance", response_model=list[ComplianceRow])
async def get_compliance(db: Db):
    """Review compliance rate by category. Public."""
    result = await db.execute(text("SELECT * FROM v_review_compliance"))
    return [dict(r) for r in result.mappings().all()]


@router.get("/reversal-rate")
async def get_reversal_rate(db: Db):
    """Reversal and failure rates by category. Public."""
    result = await db.execute(text("SELECT * FROM v_reversal_rate"))
    return [dict(r) for r in result.mappings().all()]


@router.get("/outcome-ratings")
async def get_outcome_ratings(db: Db):
    """Average review outcome rating by category. Public."""
    result = await db.execute(text("SELECT * FROM v_outcome_rating_summary"))
    return [dict(r) for r in result.mappings().all()]
