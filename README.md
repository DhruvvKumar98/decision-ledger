# Decision Ledger

Organizations make hundreds of consequential decisions each year and rarely know which ones actually worked. Decision Ledger captures decisions at the moment they are made — with full structured context, data sources, and measurable expected outcomes — then closes the loop by tracking actual results and surfacing patterns over time. It is designed for product and strategy teams that want to turn decision-making into a measurable practice, not just a process.

## Architecture

```mermaid
graph TD
    User["User / Browser"] --> Dashboard["Streamlit Dashboard :8501"]
    Dashboard --> API["FastAPI :8000"]
    API --> DB[(PostgreSQL :5432)]
    DB --> Views["Analytical Views\n(v_decision_accuracy\nv_reversal_rate\nv_review_compliance\nv_decision_velocity)"]
    API -->|"X-API-Key\n(write ops)"| Auth["API Key Middleware"]
    subgraph Docker Compose
        DB
        API
        Dashboard
    end
```

## Tech Stack

| Layer | Technology |
|---|---|
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 (async) |
| API | FastAPI + uvicorn |
| Validation | Pydantic v2 |
| Dashboard | Streamlit 1.41 |
| Charts | Plotly 5 |
| Orchestration | Docker Compose |
| Testing | pytest + pytest-asyncio + httpx |
| Linting | ruff |
| CI | GitHub Actions |

## Setup (< 10 minutes)

### Prerequisites

- Docker Desktop
- Git

### Steps

```bash
# 1. Clone
git clone https://github.com/your-username/decision-ledger.git
cd decision-ledger

# 2. Configure
cp .env.example .env
# Edit .env — change DB_PASSWORD and API_KEY to real secrets

# 3. Start everything
docker compose up --build

# 4. Open the dashboard
open http://localhost:8501

# 5. Browse the API docs
open http://localhost:8000/docs
```

The database is auto-seeded with **50 decisions** from a fictional subscription e-commerce company (Nexura Commerce) across 6 months of operation, including full context, options considered, outcomes, and reviews.

### Environment Variables

| Variable | Description |
|---|---|
| `DB_HOST` | PostgreSQL host (default: `db`) |
| `DB_PORT` | PostgreSQL port (default: `5432`) |
| `DB_NAME` | Database name |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | **Set this. No default.** |
| `API_KEY` | **Set this. No default.** Used for write operations. |
| `API_BASE_URL` | URL the dashboard uses to reach the API |

## API Quick Reference

All `GET` and analytics endpoints are **public**. Write operations require `X-API-Key` header.

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/decisions` | — | List decisions (filterable by category, status, owner, team) |
| `POST` | `/decisions` | ✅ | Create a new decision |
| `GET` | `/decisions/{id}` | — | Decision detail + reviews |
| `PATCH` | `/decisions/{id}/status` | ✅ | Update status + actual outcome |
| `POST` | `/decisions/{id}/reviews` | ✅ | Log an outcome review |
| `GET` | `/decisions/{id}/reviews` | — | List reviews for a decision |
| `DELETE` | `/decisions/{id}` | ✅ | Delete a decision |
| `GET` | `/analytics/summary` | — | Portfolio-level KPIs |
| `GET` | `/analytics/accuracy` | — | Accuracy rate by category |
| `GET` | `/analytics/velocity` | — | Decision velocity over time |
| `GET` | `/analytics/compliance` | — | Review compliance by category |
| `GET` | `/analytics/reversal-rate` | — | Reversal & failure rates |
| `GET` | `/analytics/outcome-ratings` | — | Avg outcome rating by category |
| `GET` | `/health` | — | Health check |

## Analytical SQL Layer

Five PostgreSQL views power the analytics:

| View | What it measures |
|---|---|
| `v_decision_accuracy` | Success rate (%) by category for terminal decisions |
| `v_decision_velocity` | Avg decision horizon (decided → review date) by category and month |
| `v_reversal_rate` | Reversal and adverse-outcome rate by category |
| `v_review_compliance` | % of past-due decisions with a formal review logged |
| `v_outcome_rating_summary` | Avg reviewer rating (1–5) by category |
| `v_decision_summary` | Single-row executive summary across all KPIs |

Showcase queries in `db/queries/` demonstrate window functions, CTEs, lateral joins, and compliance gap detection.

## Running Tests Locally

Tests require a running PostgreSQL instance:

```bash
# Start only the database
docker compose up db -d

# Install deps (in a venv)
pip install -r api/requirements.txt -r tests/requirements.txt

# Set test env vars
export TEST_DATABASE_URL="postgresql+asyncpg://ledger_user:your_password@localhost:5432/decision_ledger_test"
export API_KEY="test-secret-key"
export DB_PASSWORD="your_password"

# Apply schema to test DB
PGPASSWORD=your_password psql -h localhost -U ledger_user -d decision_ledger_test -f db/schema.sql
PGPASSWORD=your_password psql -h localhost -U ledger_user -d decision_ledger_test -f db/views.sql

# Run all tests
pytest tests/ -v
```

CI runs automatically on every push via `.github/workflows/ci.yml` with a PostgreSQL 16 service container.

## Security Notes

- **Secrets**: `.env` is git-ignored. Only `.env.example` (with placeholders) is committed.
- **API key**: All write endpoints require `X-API-Key` header, validated in `api/auth.py`. Key is read from `.env` — never hardcoded.
- **Network**: The PostgreSQL container is on an internal Docker network only — not exposed to the host.
- **Non-root container**: The API runs as `appuser` (non-root) inside Docker.
- **Input validation**: Pydantic enforces field lengths (title ≤200, context ≤5000, expected_outcome ≤2000), category allowlist, and future review dates.
- **DB constraints**: Category and status enums are enforced at the PostgreSQL constraint level, not just the API layer.

## Seed Data Story

The 50-decision seed dataset follows **Nexura Commerce**, a US subscription wellness and beauty box company, through 6 months of growth:

- **Jan–Mar 2026**: Price increases, mobile app launch, EU market entry (UK, Canada), infrastructure migrations
- **Apr–Jun 2026**: Personalization AI, hiring scale-up, France/Spain/Netherlands launches, data platform build-out

Decision mix: ~60% succeeded · 15% failed · 11% reversed · 4% superseded · 20% active (future review dates). Every past decision has a detailed actual outcome and a review entry with lessons learned.

## Why This Project

Portfolio projects in data and product typically demonstrate either SQL *or* API design *or* a dashboard — rarely all three integrated, and almost never with the analytical SQL depth that separates a junior from a senior practitioner. This project was designed to close that gap: it shows schema design with constraints and triggers, five analytical views using window functions and CTEs, a production-grade async FastAPI with proper auth middleware, a Streamlit dashboard that integrates with the API, and a full test suite that validates the SQL view logic directly.

---

Built by **Dhruv Kumar Boothu** · Berlin BA + MSc Data Science
