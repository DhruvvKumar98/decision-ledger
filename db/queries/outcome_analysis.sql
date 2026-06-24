-- Outcome Pattern Analysis
-- Demonstrates CTEs, window functions, and cross-category insight generation.

-- ── 1. Month-over-month decision volume with 3-month rolling average ───────────
WITH monthly_volume AS (
    SELECT
        DATE_TRUNC('month', decided_at)        AS month,
        category,
        COUNT(*)                               AS decisions_made,
        COUNT(*) FILTER (WHERE status != 'active') AS decisions_resolved
    FROM decisions
    GROUP BY 1, 2
),
rolling AS (
    SELECT
        month,
        category,
        decisions_made,
        decisions_resolved,
        ROUND(AVG(decisions_made) OVER (
            PARTITION BY category
            ORDER BY month
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ), 1)                                AS rolling_3mo_avg
    FROM monthly_volume
)
SELECT * FROM rolling ORDER BY category, month;


-- ── 2. Decision quality score by owner (min 3 decisions to qualify) ───────────
WITH owner_stats AS (
    SELECT
        owner,
        COUNT(*)                                                          AS total_decisions,
        COUNT(*) FILTER (WHERE status = 'succeeded')                     AS succeeded,
        COUNT(*) FILTER (WHERE status IN ('failed', 'reversed'))         AS adverse,
        ROUND(AVG(r.outcome_rating) FILTER (WHERE r.outcome_rating IS NOT NULL), 2)
                                                                          AS avg_review_rating
    FROM decisions d
    LEFT JOIN reviews r ON r.decision_id = d.id
    WHERE d.status != 'active'
    GROUP BY owner
    HAVING COUNT(*) >= 2
)
SELECT
    owner,
    total_decisions,
    succeeded,
    adverse,
    ROUND(succeeded::NUMERIC / NULLIF(total_decisions, 0) * 100, 1)     AS success_rate_pct,
    avg_review_rating,
    RANK() OVER (ORDER BY succeeded::NUMERIC / NULLIF(total_decisions, 0) DESC) AS success_rank
FROM owner_stats
ORDER BY success_rank;


-- ── 3. Decisions that were reviewed late (review lag > 7 days) ────────────────
SELECT
    d.id,
    d.title,
    d.category,
    d.review_date,
    MIN(r.reviewed_at::DATE)                               AS first_reviewed_on,
    MIN(r.reviewed_at::DATE) - d.review_date              AS lag_days,
    d.status
FROM decisions d
JOIN reviews r ON r.decision_id = d.id
WHERE d.review_date < CURRENT_DATE
GROUP BY d.id, d.title, d.category, d.review_date, d.status
HAVING MIN(r.reviewed_at::DATE) - d.review_date > 0
ORDER BY lag_days DESC;


-- ── 4. Lessons learned extracted from all reviews ────────────────────────────
SELECT
    d.category,
    d.title,
    d.status,
    r.reviewer,
    r.outcome_rating,
    r.lessons_learned
FROM reviews r
JOIN decisions d ON d.id = r.decision_id
WHERE r.lessons_learned IS NOT NULL
ORDER BY r.outcome_rating ASC NULLS LAST, d.category;
