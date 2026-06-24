# Decision Ledger

Organizations make hundreds of consequential decisions each year and rarely know which ones actually worked. **Decision Ledger** captures decisions at the moment they are made — with full structured context, data sources, and measurable expected outcomes — then closes the loop by tracking actual results and surfacing patterns over time.

Built for product and strategy teams that want to turn decision-making into a measurable practice, not just a process.

[![CI](https://github.com/11Fawkes/decision-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/11Fawkes/decision-ledger/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.41-FF4B4B?logo=streamlit&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

---

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
| Database | PostgreSQL 16 (Alpine) |
| ORM | SQLAlchemy 2.0 (async with asyncpg) |
| API | FastAPI + Uvicorn (multi-worker) |
| Validation | Pydantic v2 + DB-level constraints |
| Dashboard | Streamlit 1.41 |
| Charts | Plotly 5 |
| Orchestration | Docker Compose v3.9 |
| Testing | pytest + pytest-asyncio + httpx |
| Linting | ruff |
| CI | GitHub Actions |

---

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (must be running)
- [Git](https://git-scm.com/downloads)

### 1. Clone the repository

```bash
git clone https://github.com/11Fawkes/decision-ledger.git
cd decision-ledger
```

### 2. Configure environment

```bash
# Copy the example env file
cp .env.example .env
```

Open `.env` in any text editor and set your own values for `DB_PASSWORD` and `API_KEY`:

```
DB_PASSWORD=your_secure_password_here
API_KEY=your_secret_api_key_here
```

> **Note:** These are local development credentials only. The `.env` file is git-ignored and never committed.

### 3. Start the application

```bash
docker compose up --build
```

First run takes 2-3 minutes to pull images and install dependencies. Wait for both of these lines:

```
api-1        | Uvicorn running on http://0.0.0.0:8000
dashboard-1  | You can now view your Streamlit app in your browser.
```

### 4. Open in your browser

| Service | URL |
|---|---|
| Dashboard | [http://localhost:8501](http://localhost:8501) |
| API Docs (Swagger) | [http://localhost:8000/docs](http://localhost:8000/docs) |
| API Docs (ReDoc) | [http://localhost:8000/redoc](http://localhost:8000/redoc) |
| Health Check | [http://localhost:8000/health](http://localhost:8000/health) |

The database comes pre-seeded with **50 decisions** from a fictional company so you can explore immediately.

---

## Stopping & Restarting

### Stop the application

Press `Ctrl+C` in the terminal where `docker compose up` is running, then:

```bash
docker compose down
```

### Restart (preserves data)

```bash
docker compose up
```

No `--build` needed unless you changed code.

### Full reset (wipes database)

```bash
docker compose down -v
docker compose up --build
```

The `-v` flag removes the PostgreSQL data volume, so the database re-initializes with fresh seed data on the next start.

### View logs for a specific service

```bash
docker compose logs api         # API logs only
docker compose logs dashboard   # Dashboard logs only
docker compose logs db          # Database logs only
docker compose logs -f          # Follow all logs in real-time
```

### Run in background (detached mode)

```bash
docker compose up -d --build
```

This runs containers in the background. Use `docker compose logs -f` to view output, and `docker compose down` to stop.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `db` | PostgreSQL hostname (Docker service name) |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `decision_ledger` | Database name |
| `DB_USER` | `ledger_user` | PostgreSQL user |
| `DB_PASSWORD` | *(none)* | **Required.** Set in `.env` |
| `API_KEY` | *(none)* | **Required.** Used to authorize write operations (POST, PATCH, DELETE) |
| `API_PORT` | `8000` | API server port |
| `API_BASE_URL` | `http://api:8000` | Internal URL the dashboard uses to reach the API |

---

## API Reference

All `GET` endpoints are **public**. Write operations require an `X-API-Key` header.

### Decisions

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/decisions` | No | List decisions with optional filters (`category`, `status`, `owner`, `team`, `review_before`, `review_after`, `limit`, `offset`) |
| `POST` | `/decisions` | Yes | Create a new decision record |
| `GET` | `/decisions/{id}` | No | Get a single decision with all its reviews |
| `PATCH` | `/decisions/{id}/status` | Yes | Update decision status and optional actual outcome |
| `DELETE` | `/decisions/{id}` | Yes | Hard-delete a decision (cascades to reviews) |

### Reviews

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/decisions/{id}/reviews` | Yes | Log an outcome review for a decision |
| `GET` | `/decisions/{id}/reviews` | No | List all reviews for a decision |

### Analytics

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/analytics/summary` | Portfolio-level KPIs (total, active, success rate, overdue) |
| `GET` | `/analytics/accuracy` | Success rate by category for terminal decisions |
| `GET` | `/analytics/velocity` | Decision volume and horizon over time by category |
| `GET` | `/analytics/compliance` | Review compliance rate by category |
| `GET` | `/analytics/reversal-rate` | Reversal and failure rates by category |
| `GET` | `/analytics/outcome-ratings` | Average reviewer rating (1-5) by category |

### Example: Create a decision

```bash
curl -X POST http://localhost:8000/decisions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{
    "title": "Switch payment processor from Braintree to Stripe",
    "category": "operational",
    "context": "Payment failure rate is 3.2% vs 1.0% industry benchmark.",
    "options_considered": [
      {"option": "Stay with Braintree", "pros": ["no migration risk"], "cons": ["high failure rate continues"]},
      {"option": "Migrate to Stripe", "pros": ["lower failure rate", "better API"], "cons": ["migration effort"]}
    ],
    "decision_made": "Migrate to Stripe over 6-week phased rollout.",
    "rationale": "Failure rate reduction pays for migration cost within 2 months.",
    "expected_outcome": "Payment failure rate below 1.1% within 30 days of full cutover.",
    "review_date": "2026-10-01",
    "team": "Engineering",
    "owner": "Alex Chen"
  }'
```

---

## Dashboard Pages

### Portfolio Overview
Executive summary with KPI cards (total decisions, active count, success rate, overdue reviews), status donut chart, success rate by category, review compliance bars, and adverse rate trend.

### Decision Explorer
Filterable table of all decisions with drill-down detail panel. Includes full context, options considered with pros/cons, rationale, expected vs actual outcomes, and inline forms to update status or add reviews.

### Analytics
Four tabbed views: **Accuracy** (outcomes by category), **Velocity & Horizon** (decision volume over time, average days to review), **Compliance** (review follow-through rates), and **Reversal Rate** (failure and reversal rates with data tables).

### New Decision
Structured form to log a new decision with full context, up to 3 options with pros/cons, rationale, expected outcome, review date, and team assignment.

---

## Analytical SQL Layer

Six PostgreSQL views power the analytics, all defined in `db/views.sql`:

| View | What it measures |
|---|---|
| `v_decision_accuracy` | Success rate (%) by category for terminal decisions |
| `v_decision_velocity` | Avg decision horizon (decided -> review date), monthly trend |
| `v_reversal_rate` | Reversal and adverse-outcome rate by category |
| `v_review_compliance` | % of past-due decisions with a formal review logged |
| `v_outcome_rating_summary` | Avg reviewer rating (1-5) by category |
| `v_decision_summary` | Single-row executive summary across all KPIs |
| `v_decisions_with_review_count` | Denormalized view with review count and avg rating |

Showcase queries in `db/queries/` demonstrate window functions, CTEs, lateral joins, and compliance gap detection.

---

## Project Structure

```
decision-ledger/
├── api/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, lifespan, route mounting
│   ├── config.py             # Pydantic settings (reads .env)
│   ├── database.py           # Async SQLAlchemy engine & session
│   ├── models.py             # ORM models (Decision, Review)
│   ├── schemas.py            # Pydantic request/response schemas
│   ├── auth.py               # API key middleware
│   ├── Dockerfile
│   ├── requirements.txt
│   └── routes/
│       ├── __init__.py
│       ├── decisions.py      # CRUD endpoints for decisions
│       ├── reviews.py        # Review endpoints
│       └── analytics.py      # Analytics endpoints (SQL views)
├── dashboard/
│   ├── app.py                # Streamlit app (4 pages)
│   ├── charts.py             # Plotly chart builders
│   ├── Dockerfile
│   └── requirements.txt
├── db/
│   ├── schema.sql            # Tables, indexes, triggers, constraints
│   ├── views.sql             # 7 analytical views
│   ├── seed_data.sql         # 50 decisions + 26 reviews
│   └── queries/              # Showcase SQL queries
│       ├── decision_funnel.sql
│       ├── outcome_analysis.sql
│       └── review_compliance.sql
├── tests/
│   ├── conftest.py           # Fixtures: async client, DB session, test data
│   ├── test_api.py           # 30+ API route tests
│   ├── test_views.py         # SQL view correctness tests
│   └── requirements.txt
├── .github/
│   └── workflows/
│       └── ci.yml            # GitHub Actions: lint + test with PostgreSQL
├── docker-compose.yml
├── pyproject.toml            # pytest + ruff config
├── .env.example              # Template (no secrets)
├── .gitignore
└── README.md
```

---

## Running Tests

Tests run against a real PostgreSQL database (not mocks).

### Via Docker (easiest)

```bash
# Start only the database
docker compose up db -d

# Install test dependencies in a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r api/requirements.txt -r tests/requirements.txt

# Set test environment variables
set DB_PASSWORD=your_password
set API_KEY=test-secret-key
set TEST_DATABASE_URL=postgresql+asyncpg://ledger_user:your_password@localhost:5432/decision_ledger_test

# Run tests
pytest tests/ -v
```

### Via CI (automatic)

Every push triggers GitHub Actions (`.github/workflows/ci.yml`), which:
1. Spins up a PostgreSQL 16 service container
2. Installs dependencies
3. Lints with ruff
4. Applies the schema to a test database
5. Runs the full test suite

---

## Security

| Concern | How it's handled |
|---|---|
| Secrets | `.env` is git-ignored. Only `.env.example` (with placeholders) is committed |
| API authentication | Write endpoints require `X-API-Key` header, validated in `api/auth.py` |
| Network isolation | PostgreSQL is on an internal Docker network — not exposed to the host |
| Container user | API runs as non-root `appuser` inside Docker |
| Input validation | Pydantic enforces field lengths, category/status allowlists, future review dates |
| DB constraints | Category and status enums enforced at the PostgreSQL constraint level |
| SQL injection | SQLAlchemy ORM uses parameterized queries throughout |
| CORS | Configured in `api/main.py` (currently allows all origins for development) |

---

## Seed Data

The 50-decision dataset tells the story of **Nexura Commerce**, a US subscription wellness and beauty box company, through 6 months of growth (Jan-Jun 2026):

| Category | Decisions | Story Arc |
|---|---|---|
| Pricing (10) | Price increases, annual billing, tiered pricing, gift pricing, loyalty discounts | Revenue optimization and packaging strategy |
| Product (12) | Mobile app, personalization AI, review system, community forum | Digital product expansion |
| Hiring (10) | CFO, VP Engineering, data team, international ops | Scaling the organization |
| Market Entry (7) | UK, Canada, France, Spain, Nordics, Netherlands launches | European expansion |
| Operational (10) | Payment processor migration, ERP replacement, 3PL tracking, data warehouse | Infrastructure modernization |

Decision mix: ~38% succeeded, 8% failed, 8% reversed, 2% superseded, 44% active. Every completed decision has a detailed actual outcome and review with lessons learned.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `docker daemon is not running` | Open Docker Desktop and wait for the whale icon to turn steady |
| `port 8000 already in use` | Change `API_PORT` in `.env` or stop the conflicting process |
| `port 8501 already in use` | Change the dashboard port mapping in `docker-compose.yml` |
| API crash loop (ModuleNotFoundError) | Run `docker compose down -v && docker compose up --build` |
| Dashboard shows no data | Check that the API container is running (`docker compose logs api`) |
| Database init errors | Run `docker compose down -v` to wipe the volume and start fresh |
| `0.0.0.0:8501` doesn't load | Use `localhost:8501` instead (0.0.0.0 is the container bind address, not a browser URL) |
| Changes not reflected | Rebuild with `docker compose up --build` |

---

## License

This project is open source and available for educational and portfolio purposes.

---

Built by **Dhruv Kumar Boothu**
