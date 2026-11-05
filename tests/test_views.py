"""SQL view correctness tests.

Inserts known data into the test database and asserts that each analytical
view returns the expected results. This is the most important test suite
because it validates the SQL logic that drives the analytics layer.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Decision, Review

pytestmark = pytest.mark.asyncio

# ── Helpers ────────────────────────────────────────────────────────────────────

def _decision(
    title: str,
    category: str,
    status: str = "active",
    review_days: int = 90,
    actual_outcome: str | None = None,
    decided_days_ago: int = 0,
    owner: str = "Test Owner",
) -> Decision:
    decided_at = date.today() - timedelta(days=decided_days_ago)
    review_date = decided_at + timedelta(days=review_days)
    decided_ts = datetime.combine(decided_at, datetime.min.time(), tzinfo=timezone.utc)
    return Decision(
        title=title,
        category=category,
        context="Test context for this decision. " * 3,
        options_considered=[{"option": "A", "pros": ["x"], "cons": ["y"]}],
        data_consulted=["Source A"],
        decision_made="We chose option A.",
        rationale="Because it is the best option available.",
        expected_outcome="Outcome metric improves by 10% in 90 days.",
        review_date=review_date,
        decided_at=decided_ts,
        status=status,
        actual_outcome=actual_outcome,
        owner=owner,
    )


# ── Fixtures: insert known decisions + reviews ─────────────────────────────────

@pytest_asyncio.fixture
async def seeded_db(db_session: AsyncSession):
    """Insert a deterministic set of decisions for view testing."""
    decisions = [
        # ── pricing: 3 total, 2 succeeded, 1 failed ───────────────────────────
        _decision("P1", "pricing", "succeeded", review_days=60, decided_days_ago=90),
        _decision("P2", "pricing", "succeeded", review_days=60, decided_days_ago=90),
        _decision("P3", "pricing", "failed",    review_days=60, decided_days_ago=90),
        # ── product: 2 total, 1 succeeded, 1 reversed ─────────────────────────
        _decision("Pr1", "product", "succeeded", review_days=60, decided_days_ago=90),
        _decision("Pr2", "product", "reversed",  review_days=60, decided_days_ago=90),
        # ── hiring: 1 active (overdue) ────────────────────────────────────────
        _decision("H1", "hiring", "active", review_days=30, decided_days_ago=90),
        # ── market_entry: 1 succeeded ─────────────────────────────────────────
        _decision("ME1", "market_entry", "succeeded", review_days=60, decided_days_ago=90),
        # ── operational: 1 superseded ─────────────────────────────────────────
        _decision("Op1", "operational", "superseded", review_days=60, decided_days_ago=90),
    ]
    db_session.add_all(decisions)
    await db_session.flush()

    # Retrieve IDs after flush
    pricing_ids = [d.id for d in decisions if d.category == "pricing"]
    product_ids  = [d.id for d in decisions if d.category == "product"]

    # Reviews for reviewed decisions (those with non-active status)
    reviews = [
        # Two reviews for P1 (succeeded)
        Review(decision_id=pricing_ids[0], actual_outcome="Metric improved 12%.", outcome_rating=5),
        Review(decision_id=pricing_ids[1], actual_outcome="Metric improved 8%.",  outcome_rating=4),
        # Review for P3 (failed)
        Review(decision_id=pricing_ids[2], actual_outcome="Metric declined 5%.",  outcome_rating=2),
        # Review for Pr1 (succeeded)
        Review(decision_id=product_ids[0], actual_outcome="Feature shipped.", outcome_rating=5),
        # No review for Pr2 (reversed) — tests compliance gap
    ]
    db_session.add_all(reviews)
    await db_session.commit()

    return {
        "pricing_ids": pricing_ids,
        "product_ids": product_ids,
        "decisions": decisions,
    }


# ── View tests ─────────────────────────────────────────────────────────────────

class TestViewDecisionAccuracy:
    async def test_pricing_accuracy_rate(self, db_session: AsyncSession, seeded_db):
        result = await db_session.execute(
            text("SELECT * FROM v_decision_accuracy WHERE category = 'pricing'")
        )
        row = result.mappings().one()
        assert row["succeeded"] == 2
        assert row["failed"] == 1
        assert row["total_terminal"] == 3
        # 2 of 3 = 66.7%
        assert abs(row["accuracy_rate_pct"] - 66.7) < 0.5

    async def test_product_reversal_counted_correctly(self, db_session: AsyncSession, seeded_db):
        result = await db_session.execute(
            text("SELECT * FROM v_decision_accuracy WHERE category = 'product'")
        )
        row = result.mappings().one()
        assert row["reversed"] == 1
        assert row["succeeded"] == 1
        assert row["total_terminal"] == 2
        # 1 of 2 = 50%
        assert row["accuracy_rate_pct"] == 50.0

    async def test_active_decisions_excluded(self, db_session: AsyncSession, seeded_db):
        """Active decisions must not appear in accuracy view."""
        result = await db_session.execute(
            text("SELECT * FROM v_decision_accuracy WHERE category = 'hiring'")
        )
        rows = result.mappings().all()
        # Hiring only has one active decision — should not appear in accuracy view
        assert len(rows) == 0


class TestViewReversalRate:
    async def test_reversal_rate_computed_per_category(self, db_session: AsyncSession, seeded_db):
        result = await db_session.execute(
            text("SELECT * FROM v_reversal_rate WHERE category = 'product'")
        )
        row = result.mappings().one()
        assert row["reversed_count"] == 1
        # 1 adverse (reversed) out of 2 total = 50%
        assert row["adverse_rate_pct"] == 50.0

    async def test_pricing_no_reversals(self, db_session: AsyncSession, seeded_db):
        result = await db_session.execute(
            text("SELECT * FROM v_reversal_rate WHERE category = 'pricing'")
        )
        row = result.mappings().one()
        assert row["reversed_count"] == 0
        assert row["reversal_rate_pct"] == 0.0


class TestViewReviewCompliance:
    async def test_compliance_below_100_when_review_missing(
        self, db_session: AsyncSession, seeded_db
    ):
        result = await db_session.execute(
            text("SELECT * FROM v_review_compliance WHERE category = 'product'")
        )
        row = result.mappings().one()
        # product has 2 past-due decisions: 1 reviewed (Pr1), 1 not (Pr2)
        assert row["past_due_decisions"] == 2
        assert row["reviewed_count"] == 1
        assert row["compliance_rate_pct"] == 50.0

    async def test_pricing_full_compliance(self, db_session: AsyncSession, seeded_db):
        result = await db_session.execute(
            text("SELECT * FROM v_review_compliance WHERE category = 'pricing'")
        )
        row = result.mappings().one()
        assert row["past_due_decisions"] == 3
        assert row["reviewed_count"] == 3
        assert row["compliance_rate_pct"] == 100.0

    async def test_active_overdue_has_zero_compliance(self, db_session: AsyncSession, seeded_db):
        """Hiring has 1 past-due active decision with no review."""
        result = await db_session.execute(
            text("SELECT * FROM v_review_compliance WHERE category = 'hiring'")
        )
        row = result.mappings().one()
        assert row["past_due_decisions"] == 1
        assert row["reviewed_count"] == 0
        assert row["compliance_rate_pct"] == 0.0


class TestViewDecisionSummary:
    async def test_summary_totals(self, db_session: AsyncSession, seeded_db):
        result = await db_session.execute(text("SELECT * FROM v_decision_summary"))
        row = result.mappings().one()
        # We inserted 8 decisions
        assert row["total_decisions"] >= 8
        # At least 1 active
        assert row["active_decisions"] >= 1
        # At least 2 succeeded
        assert row["succeeded_decisions"] >= 2

    async def test_overall_accuracy_positive(self, db_session: AsyncSession, seeded_db):
        result = await db_session.execute(text("SELECT * FROM v_decision_summary"))
        row = result.mappings().one()
        # We have 4 succeeded, 1 failed, 1 reversed, 1 superseded = 4/7 ≈ 57%
        assert row["overall_accuracy_pct"] is not None
        assert row["overall_accuracy_pct"] > 0

    async def test_overdue_count_includes_active_past_review(
        self, db_session: AsyncSession, seeded_db
    ):
        result = await db_session.execute(text("SELECT * FROM v_decision_summary"))
        row = result.mappings().one()
        # H1 is active with review_date 60 days ago → overdue
        assert row["overdue_decisions"] >= 1


class TestViewOutcomeRatingSummary:
    async def test_rating_summary_for_pricing(self, db_session: AsyncSession, seeded_db):
        result = await db_session.execute(
            text("SELECT * FROM v_outcome_rating_summary WHERE category = 'pricing'")
        )
        row = result.mappings().one()
        assert row["total_reviews"] == 3  # P1, P1 second review, P2, P3 = wait, we have 3 reviews
        # avg of ratings 5, 4, 2 = 3.67
        assert abs(row["avg_rating"] - 3.67) < 0.1
