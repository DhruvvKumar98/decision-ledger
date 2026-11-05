from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import engine
from api.models import Base
from api.routes import analytics, decisions, reviews


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables are managed by schema.sql in production;
    # create_all here covers the test environment.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Decision Ledger API",
    description=(
        "Capture decisions at the point they are made, track outcomes, "
        "and surface patterns over time."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "https://decision-ledger-ietcgke26aemhzqq9nquvt.streamlit.app",
    ],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(decisions.router, prefix="/decisions", tags=["decisions"])
app.include_router(reviews.router, prefix="/decisions", tags=["reviews"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
