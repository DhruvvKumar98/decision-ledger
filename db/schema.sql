-- Decision Ledger Database Schema
-- PostgreSQL 16

SET client_encoding = 'UTF8';

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── Enumerations as check constraints (no custom types for portability) ───────

-- ── decisions ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS decisions (
    id                  SERIAL          PRIMARY KEY,
    title               VARCHAR(200)    NOT NULL,
    category            VARCHAR(20)     NOT NULL,
    context             TEXT            NOT NULL,
    -- Array of {option, pros[], cons[]} objects
    options_considered  JSONB           NOT NULL DEFAULT '[]',
    data_consulted      TEXT[]          NOT NULL DEFAULT '{}',
    decision_made       TEXT            NOT NULL,
    rationale           TEXT            NOT NULL,
    expected_outcome    VARCHAR(2000)   NOT NULL,
    review_date         DATE            NOT NULL,
    status              VARCHAR(20)     NOT NULL DEFAULT 'active',
    actual_outcome      TEXT,
    team                VARCHAR(100),
    owner               VARCHAR(100),
    decided_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT decisions_category_check
        CHECK (category IN ('pricing','product','hiring','market_entry','operational')),
    CONSTRAINT decisions_status_check
        CHECK (status IN ('active','succeeded','failed','reversed','superseded')),
    CONSTRAINT decisions_review_date_valid
        CHECK (review_date >= decided_at::DATE)
);

-- ── reviews ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reviews (
    id              SERIAL          PRIMARY KEY,
    decision_id     INTEGER         NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    reviewer        VARCHAR(100),
    actual_outcome  TEXT            NOT NULL,
    outcome_rating  SMALLINT,
    lessons_learned TEXT,
    reviewed_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT reviews_rating_range CHECK (outcome_rating BETWEEN 1 AND 5)
);

-- ── Indexes ────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_decisions_category    ON decisions(category);
CREATE INDEX IF NOT EXISTS idx_decisions_status      ON decisions(status);
CREATE INDEX IF NOT EXISTS idx_decisions_review_date ON decisions(review_date);
CREATE INDEX IF NOT EXISTS idx_decisions_decided_at  ON decisions(decided_at DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_team        ON decisions(team);
CREATE INDEX IF NOT EXISTS idx_decisions_owner       ON decisions(owner);
CREATE INDEX IF NOT EXISTS idx_reviews_decision_id   ON reviews(decision_id);
CREATE INDEX IF NOT EXISTS idx_reviews_reviewed_at   ON reviews(reviewed_at DESC);

-- Trigram index for full-text search on title + decision_made
CREATE INDEX IF NOT EXISTS idx_decisions_title_trgm
    ON decisions USING GIN (title gin_trgm_ops);

-- ── updated_at trigger ─────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_decisions_updated_at ON decisions;
CREATE TRIGGER trg_decisions_updated_at
    BEFORE UPDATE ON decisions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── Comments ───────────────────────────────────────────────────────────────────
COMMENT ON TABLE decisions IS 'Core decision records with full structured context';
COMMENT ON TABLE reviews IS 'Outcome reviews written at or after the scheduled review_date';
COMMENT ON COLUMN decisions.options_considered IS
    'JSON array: [{option: str, pros: [str], cons: [str]}]';
COMMENT ON COLUMN decisions.data_consulted IS
    'List of data sources referenced before making the decision';
COMMENT ON COLUMN decisions.review_date IS
    'Date when actual outcome should be evaluated against expected_outcome';
