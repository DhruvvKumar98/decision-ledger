-- Decision Ledger Analytical Views
-- All views are CREATE OR REPLACE for idempotent deployment

-- ── v_decision_accuracy ────────────────────────────────────────────────────────
-- Success rate by category, for decisions that have reached a terminal status
CREATE OR REPLACE VIEW v_decision_accuracy AS
WITH terminal AS (
    SELECT
        category,
        status,
        COUNT(*) AS cnt
    FROM decisions
    WHERE status IN ('succeeded', 'failed', 'reversed', 'superseded')
    GROUP BY category, status
),
totals AS (
    SELECT category, SUM(cnt) AS total_terminal FROM terminal GROUP BY category
)
SELECT
    t.category,
    tot.total_terminal,
    COALESCE(MAX(t.cnt) FILTER (WHERE t.status = 'succeeded'),  0) AS succeeded,
    COALESCE(MAX(t.cnt) FILTER (WHERE t.status = 'failed'),     0) AS failed,
    COALESCE(MAX(t.cnt) FILTER (WHERE t.status = 'reversed'),   0) AS reversed,
    COALESCE(MAX(t.cnt) FILTER (WHERE t.status = 'superseded'), 0) AS superseded,
    ROUND(
        COALESCE(MAX(t.cnt) FILTER (WHERE t.status = 'succeeded'), 0)::NUMERIC
        / NULLIF(tot.total_terminal, 0) * 100,
        1
    ) AS accuracy_rate_pct
FROM terminal t
JOIN totals tot ON t.category = tot.category
GROUP BY t.category, tot.total_terminal
ORDER BY accuracy_rate_pct DESC NULLS LAST;


-- ── v_decision_velocity ────────────────────────────────────────────────────────
-- Average horizon (decided_at → review_date) and how many are overdue
CREATE OR REPLACE VIEW v_decision_velocity AS
SELECT
    category,
    COUNT(*)                                                            AS total_decisions,
    ROUND(AVG(review_date - decided_at::DATE))                         AS avg_horizon_days,
    MIN(review_date - decided_at::DATE)                                 AS min_horizon_days,
    MAX(review_date - decided_at::DATE)                                 AS max_horizon_days,
    COUNT(*) FILTER (WHERE review_date < CURRENT_DATE AND status = 'active') AS overdue_count,
    -- Monthly decision count for trend analysis
    DATE_TRUNC('month', decided_at)                                     AS month_bucket
FROM decisions
GROUP BY category, DATE_TRUNC('month', decided_at)
ORDER BY category, month_bucket;


-- ── v_reversal_rate ────────────────────────────────────────────────────────────
-- Reversal and failure rates by category
CREATE OR REPLACE VIEW v_reversal_rate AS
SELECT
    category,
    COUNT(*)                                                      AS total_decisions,
    COUNT(*) FILTER (WHERE status = 'reversed')                   AS reversed_count,
    COUNT(*) FILTER (WHERE status = 'failed')                     AS failed_count,
    COUNT(*) FILTER (WHERE status IN ('reversed','failed'))       AS adverse_count,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'reversed')::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 1
    )                                                             AS reversal_rate_pct,
    ROUND(
        COUNT(*) FILTER (WHERE status IN ('reversed','failed'))::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 1
    )                                                             AS adverse_rate_pct
FROM decisions
GROUP BY category
ORDER BY adverse_rate_pct DESC;


-- ── v_review_compliance ────────────────────────────────────────────────────────
-- % of past-due decisions that have at least one review logged
CREATE OR REPLACE VIEW v_review_compliance AS
WITH past_due AS (
    SELECT
        d.id,
        d.category,
        d.review_date,
        d.status,
        -- Has a review been submitted?
        EXISTS (SELECT 1 FROM reviews r WHERE r.decision_id = d.id) AS is_reviewed,
        -- First review latency in days (positive = late, negative = early)
        (SELECT MIN(r.reviewed_at::DATE) - d.review_date
         FROM reviews r WHERE r.decision_id = d.id)                  AS review_lag_days
    FROM decisions d
    WHERE d.review_date < CURRENT_DATE
)
SELECT
    category,
    COUNT(*)                                                         AS past_due_decisions,
    COUNT(*) FILTER (WHERE is_reviewed)                              AS reviewed_count,
    ROUND(
        COUNT(*) FILTER (WHERE is_reviewed)::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 1
    )                                                                AS compliance_rate_pct,
    ROUND(AVG(review_lag_days) FILTER (WHERE review_lag_days IS NOT NULL), 1)
                                                                     AS avg_review_lag_days
FROM past_due
GROUP BY category
ORDER BY compliance_rate_pct ASC;


-- ── v_outcome_rating_summary ──────────────────────────────────────────────────
-- Average outcome rating per category (from review records)
CREATE OR REPLACE VIEW v_outcome_rating_summary AS
SELECT
    d.category,
    COUNT(DISTINCT d.id)                            AS reviewed_decisions,
    COUNT(r.id)                                     AS total_reviews,
    ROUND(AVG(r.outcome_rating), 2)                 AS avg_rating,
    MIN(r.outcome_rating)                           AS min_rating,
    MAX(r.outcome_rating)                           AS max_rating
FROM decisions d
JOIN reviews r ON r.decision_id = d.id
WHERE r.outcome_rating IS NOT NULL
GROUP BY d.category
ORDER BY avg_rating DESC;


-- ── v_decision_summary ─────────────────────────────────────────────────────────
-- Single-row executive dashboard summary
CREATE OR REPLACE VIEW v_decision_summary AS
SELECT
    COUNT(*)                                                          AS total_decisions,
    COUNT(*) FILTER (WHERE status = 'active')                        AS active_decisions,
    COUNT(*) FILTER (WHERE status = 'succeeded')                     AS succeeded_decisions,
    COUNT(*) FILTER (WHERE status = 'failed')                        AS failed_decisions,
    COUNT(*) FILTER (WHERE status = 'reversed')                      AS reversed_decisions,
    COUNT(*) FILTER (WHERE status = 'superseded')                    AS superseded_decisions,
    COUNT(*) FILTER (WHERE review_date < CURRENT_DATE AND status = 'active')
                                                                     AS overdue_decisions,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'succeeded')::NUMERIC
        / NULLIF(COUNT(*) FILTER (WHERE status IN ('succeeded','failed','reversed','superseded')), 0)
        * 100, 1
    )                                                                AS overall_accuracy_pct,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'reversed')::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 1
    )                                                                AS overall_reversal_pct
FROM decisions;


-- ── v_decisions_with_review_count ─────────────────────────────────────────────
-- Denormalised view used by the API analytics endpoint
CREATE OR REPLACE VIEW v_decisions_with_review_count AS
SELECT
    d.*,
    COUNT(r.id) AS review_count,
    MAX(r.reviewed_at) AS last_reviewed_at,
    ROUND(AVG(r.outcome_rating), 1) AS avg_rating
FROM decisions d
LEFT JOIN reviews r ON r.decision_id = d.id
GROUP BY d.id;
