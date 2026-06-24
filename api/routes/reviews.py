from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import verify_api_key
from api.database import get_db
from api.models import Decision, Review
from api.schemas import ReviewCreate, ReviewOut

router = APIRouter()

Db = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/{decision_id}/reviews",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_review(
    decision_id: int,
    payload: ReviewCreate,
    db: Db,
    _: str = Depends(verify_api_key),
):
    """Add an outcome review to a decision. Requires X-API-Key."""
    decision = await db.get(Decision, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    review = Review(decision_id=decision_id, **payload.model_dump())
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return review


@router.get(
    "/{decision_id}/reviews",
    response_model=list[ReviewOut],
)
async def list_reviews(decision_id: int, db: Db):
    """List all reviews for a decision. Public."""
    decision = await db.get(Decision, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision.reviews
