"""API route tests using the async test client with a real PostgreSQL database."""

import pytest
from httpx import AsyncClient

from tests.conftest import WRITE_HEADERS, make_decision_payload

pytestmark = pytest.mark.asyncio


class TestHealth:
    async def test_health_returns_ok(self, client: AsyncClient):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestCreateDecision:
    async def test_create_decision_success(self, client: AsyncClient):
        payload = make_decision_payload()
        r = await client.post("/decisions", json=payload, headers=WRITE_HEADERS)
        assert r.status_code == 201
        body = r.json()
        assert body["title"] == payload["title"]
        assert body["category"] == "pricing"
        assert body["status"] == "active"
        assert isinstance(body["id"], int)

    async def test_create_decision_requires_api_key(self, client: AsyncClient):
        r = await client.post("/decisions", json=make_decision_payload())
        assert r.status_code == 403

    async def test_create_decision_rejects_past_review_date(self, client: AsyncClient):
        payload = make_decision_payload(review_date="2020-01-01")
        r = await client.post("/decisions", json=payload, headers=WRITE_HEADERS)
        assert r.status_code == 422

    async def test_create_decision_validates_category(self, client: AsyncClient):
        payload = make_decision_payload(category="invalid_category")
        r = await client.post("/decisions", json=payload, headers=WRITE_HEADERS)
        assert r.status_code == 422

    async def test_create_decision_validates_title_length(self, client: AsyncClient):
        payload = make_decision_payload(title="x" * 201)
        r = await client.post("/decisions", json=payload, headers=WRITE_HEADERS)
        assert r.status_code == 422

    async def test_create_decision_validates_context_length(self, client: AsyncClient):
        payload = make_decision_payload(context="x" * 5001)
        r = await client.post("/decisions", json=payload, headers=WRITE_HEADERS)
        assert r.status_code == 422

    async def test_create_decision_validates_expected_outcome_length(self, client: AsyncClient):
        payload = make_decision_payload(expected_outcome="x" * 2001)
        r = await client.post("/decisions", json=payload, headers=WRITE_HEADERS)
        assert r.status_code == 422

    async def test_create_requires_at_least_one_option(self, client: AsyncClient):
        payload = make_decision_payload(options_considered=[])
        r = await client.post("/decisions", json=payload, headers=WRITE_HEADERS)
        assert r.status_code == 422


class TestListDecisions:
    async def test_list_is_public(self, client: AsyncClient):
        r = await client.get("/decisions")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_list_filter_by_category(self, client: AsyncClient):
        # Create two decisions in different categories
        await client.post(
            "/decisions",
            json=make_decision_payload(category="pricing"),
            headers=WRITE_HEADERS,
        )
        await client.post(
            "/decisions",
            json=make_decision_payload(category="product", title="Product decision test"),
            headers=WRITE_HEADERS,
        )
        r = await client.get("/decisions?category=pricing")
        assert r.status_code == 200
        for item in r.json():
            assert item["category"] == "pricing"

    async def test_list_filter_by_status(self, client: AsyncClient):
        r = await client.get("/decisions?status=active")
        assert r.status_code == 200
        for item in r.json():
            assert item["status"] == "active"

    async def test_list_pagination(self, client: AsyncClient):
        # Create 3 decisions
        for i in range(3):
            await client.post(
                "/decisions",
                json=make_decision_payload(title=f"Paginated decision {i}"),
                headers=WRITE_HEADERS,
            )
        r = await client.get("/decisions?limit=2&offset=0")
        assert r.status_code == 200
        assert len(r.json()) <= 2


class TestGetDecision:
    async def test_get_existing_decision(self, client: AsyncClient):
        create_r = await client.post(
            "/decisions", json=make_decision_payload(), headers=WRITE_HEADERS
        )
        decision_id = create_r.json()["id"]

        r = await client.get(f"/decisions/{decision_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == decision_id
        assert "reviews" in body
        assert isinstance(body["reviews"], list)

    async def test_get_nonexistent_returns_404(self, client: AsyncClient):
        r = await client.get("/decisions/999999")
        assert r.status_code == 404


class TestUpdateStatus:
    async def test_update_status_to_succeeded(self, client: AsyncClient):
        create_r = await client.post(
            "/decisions", json=make_decision_payload(), headers=WRITE_HEADERS
        )
        decision_id = create_r.json()["id"]

        r = await client.patch(
            f"/decisions/{decision_id}/status",
            json={"status": "succeeded", "actual_outcome": "Churn was 2.1%, ARR up $2M."},
            headers=WRITE_HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "succeeded"
        assert body["actual_outcome"] == "Churn was 2.1%, ARR up $2M."

    async def test_update_status_requires_api_key(self, client: AsyncClient):
        create_r = await client.post(
            "/decisions", json=make_decision_payload(), headers=WRITE_HEADERS
        )
        decision_id = create_r.json()["id"]

        r = await client.patch(
            f"/decisions/{decision_id}/status",
            json={"status": "succeeded"},
        )
        assert r.status_code == 403

    async def test_update_status_invalid_value(self, client: AsyncClient):
        create_r = await client.post(
            "/decisions", json=make_decision_payload(), headers=WRITE_HEADERS
        )
        decision_id = create_r.json()["id"]

        r = await client.patch(
            f"/decisions/{decision_id}/status",
            json={"status": "maybe"},
            headers=WRITE_HEADERS,
        )
        assert r.status_code == 422


class TestReviews:
    async def test_add_review_to_decision(self, client: AsyncClient):
        create_r = await client.post(
            "/decisions", json=make_decision_payload(), headers=WRITE_HEADERS
        )
        decision_id = create_r.json()["id"]

        r = await client.post(
            f"/decisions/{decision_id}/reviews",
            json={
                "reviewer": "Nadia Osei",
                "actual_outcome": "Churn 2.1%, ARR up $2.4M.",
                "outcome_rating": 5,
                "lessons_learned": "Price-lock offer was key.",
            },
            headers=WRITE_HEADERS,
        )
        assert r.status_code == 201
        body = r.json()
        assert body["decision_id"] == decision_id
        assert body["outcome_rating"] == 5
        assert body["reviewer"] == "Nadia Osei"

    async def test_add_review_requires_api_key(self, client: AsyncClient):
        create_r = await client.post(
            "/decisions", json=make_decision_payload(), headers=WRITE_HEADERS
        )
        decision_id = create_r.json()["id"]

        r = await client.post(
            f"/decisions/{decision_id}/reviews",
            json={"actual_outcome": "Some outcome"},
        )
        assert r.status_code == 403

    async def test_add_review_validates_rating_range(self, client: AsyncClient):
        create_r = await client.post(
            "/decisions", json=make_decision_payload(), headers=WRITE_HEADERS
        )
        decision_id = create_r.json()["id"]

        r = await client.post(
            f"/decisions/{decision_id}/reviews",
            json={"actual_outcome": "Some outcome", "outcome_rating": 6},
            headers=WRITE_HEADERS,
        )
        assert r.status_code == 422

    async def test_review_appears_in_decision_detail(self, client: AsyncClient):
        create_r = await client.post(
            "/decisions", json=make_decision_payload(), headers=WRITE_HEADERS
        )
        decision_id = create_r.json()["id"]

        await client.post(
            f"/decisions/{decision_id}/reviews",
            json={"actual_outcome": "Outcome text", "outcome_rating": 4},
            headers=WRITE_HEADERS,
        )

        detail_r = await client.get(f"/decisions/{decision_id}")
        reviews = detail_r.json()["reviews"]
        assert len(reviews) == 1
        assert reviews[0]["outcome_rating"] == 4

    async def test_list_reviews_for_decision(self, client: AsyncClient):
        create_r = await client.post(
            "/decisions", json=make_decision_payload(), headers=WRITE_HEADERS
        )
        decision_id = create_r.json()["id"]

        for i in range(2):
            await client.post(
                f"/decisions/{decision_id}/reviews",
                json={"actual_outcome": f"Outcome {i}", "outcome_rating": i + 1},
                headers=WRITE_HEADERS,
            )

        r = await client.get(f"/decisions/{decision_id}/reviews")
        assert r.status_code == 200
        assert len(r.json()) == 2


class TestAnalytics:
    async def test_summary_returns_valid_structure(self, client: AsyncClient):
        r = await client.get("/analytics/summary")
        assert r.status_code == 200
        body = r.json()
        assert "total_decisions" in body
        assert "overall_accuracy_pct" in body

    async def test_accuracy_returns_list(self, client: AsyncClient):
        r = await client.get("/analytics/accuracy")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_velocity_returns_list(self, client: AsyncClient):
        r = await client.get("/analytics/velocity")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_compliance_returns_list(self, client: AsyncClient):
        r = await client.get("/analytics/compliance")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_reversal_rate_returns_list(self, client: AsyncClient):
        r = await client.get("/analytics/reversal-rate")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_outcome_ratings_returns_list(self, client: AsyncClient):
        r = await client.get("/analytics/outcome-ratings")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_analytics_are_public(self, client: AsyncClient):
        """All analytics endpoints must be accessible without an API key."""
        for path in ["/analytics/summary", "/analytics/accuracy", "/analytics/compliance"]:
            r = await client.get(path)
            assert r.status_code == 200, f"{path} returned {r.status_code}"
