-- Review Compliance Deep-Dive
-- Identifies which past-due decisions have not been reviewed,
-- and ranks categories by compliance health.

-- ── 1. Full compliance detail: every past-due decision with review status ──────
SELECT
    d.id,
    d.title,
    d.category,
    d.owner,
    d.review_date,
    d.status,
    CASE WHEN r.first_review IS NOT NULL THEN 'reviewed' ELSE 'OVERDUE — no review' END AS review_status,
    r.first_review,
    r.first_review - d.review_date      AS review_lag_days,
    r.review_count
FROM decisions d
LEFT JOIN (
    SELECT
        decision_id,
        MIN(reviewed_at::DATE)  AS first_review,
        COUNT(*)                AS review_count
    FROM reviews
    GROUP BY decision_id
) r ON r.decision_id = d.id
WHERE d.review_date < CURRENT_DATE
ORDER BY
    CASE WHEN r.first_review IS NULL THEN 0 ELSE 1 END,  -- unreviewed first
    d.review_date;


-- ── 2. Category compliance scoreboard ─────────────────────────────────────────
WITH compliance AS (
    SELECT
        d.category,
        COUNT(*)                                                              AS past_due,
        COUNT(*) FILTER (WHERE r.decision_id IS NOT NULL)                    AS reviewed,
        ROUND(COUNT(*) FILTER (WHERE r.decision_id IS NOT NULL)::NUMERIC
              / NULLIF(COUNT(*), 0) * 100, 1)                                AS compliance_pct,
        ROUND(AVG(r.first_review - d.review_date)
              FILTER (WHERE r.first_review IS NOT NULL), 1)                  AS avg_lag_days
    FROM decisions d
    LEFT JOIN (
        SELECT decision_id, MIN(reviewed_at::DATE) AS first_review
        FROM reviews GROUP BY decision_id
    ) r ON r.decision_id = d.id
    WHERE d.review_date < CURRENT_DATE
    GROUP BY d.category
)
SELECT
    *,
    RANK() OVER (ORDER BY compliance_pct DESC) AS compliance_rank
FROM compliance
ORDER BY compliance_rank;


-- ── 3. Decisions most overdue for review (no review submitted) ────────────────
SELECT
    d.id,
    d.title,
    d.category,
    d.owner,
    d.review_date,
    CURRENT_DATE - d.review_date   AS days_overdue,
    d.status
FROM decisions d
WHERE d.review_date < CURRENT_DATE
  AND NOT EXISTS (SELECT 1 FROM reviews r WHERE r.decision_id = d.id)
ORDER BY days_overdue DESC;
