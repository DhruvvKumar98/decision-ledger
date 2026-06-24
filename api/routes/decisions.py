from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import verify_api_key
from api.database import get_db
from api.models import Decision
from api.schemas import (
    DecisionCreate,
    DecisionListOut,
    DecisionOut,
    DecisionStatusUpdate,
)

router = APIRouter()

Db = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=list[DecisionListOut])
async def list_decisions(
    db: Db,
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    team: Optional[str] = Query(None, description="Filter by team"),
    owner: Optional[str] = Query(None, description="Filter by owner"),
    review_before: Optional[date] = Query(None, description="Review date before (inclusive)"),
    review_after: Optional[date] = Query(None, description="Review date after (inclusive)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List decisions with optional filters. Public — no API key required."""
    stmt = select(Decision).order_by(Decision.decided_at.desc())

    if category:
        stmt = stmt.where(Decision.category == category)
    if status:
        stmt = stmt.where(Decision.status == status)
    if team:
        stmt = stmt.where(Decision.team == team)
    if owner:
        stmt = stmt.where(Decision.owner == owner)
    if review_before:
        stmt = stmt.where(Decision.review_date <= review_before)
    if review_after:
        stmt = stmt.where(Decision.review_date >= review_after)

    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=DecisionOut, status_code=status.HTTP_201_CREATED)
async def create_decision(
    payload: DecisionCreate,
    db: Db,
    _: str = Depends(verify_api_key),
):
    """Create a new decision record. Requires X-API-Key header."""
    decision = Decision(**payload.model_dump())
    db.add(decision)
    await db.commit()
    await db.refresh(decision)
    return decision


@router.get("/{decision_id}", response_model=DecisionOut)
async def get_decision(decision_id: int, db: Db):
    """Fetch a single decision with all its reviews."""
    decision = await db.get(Decision, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision


@router.patch("/{decision_id}/status", response_model=DecisionOut)
async def update_status(
    decision_id: int,
    payload: DecisionStatusUpdate,
    db: Db,
    _: str = Depends(verify_api_key),
):
    """Update the status (and optional actual_outcome) of a decision. Requires X-API-Key."""
    decision = await db.get(Decision, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    decision.status = payload.status
    if payload.actual_outcome is not None:
        decision.actual_outcome = payload.actual_outcome

    await db.commit()
    await db.refresh(decision)
    return decision


@router.delete("/{decision_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_decision(
    decision_id: int,
    db: Db,
    _: str = Depends(verify_api_key),
):
    """Hard-delete a decision (cascades to reviews). Requires X-API-Key."""
    decision = await db.get(Decision, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    await db.delete(decision)
    await db.commit()
