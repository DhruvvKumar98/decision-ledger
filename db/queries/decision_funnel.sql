-- Decision Funnel Analysis
-- Shows the lifecycle flow of decisions through each status,
-- stratified by category, using window functions for percentages.

WITH status_counts AS (
    SELECT
        category,
        status,
        COUNT(*)                          AS cnt,
        SUM(COUNT(*)) OVER (PARTITION BY category) AS category_total
    FROM decisions
    GROUP BY category, status
),
active_overdue AS (
    SELECT category, COUNT(*) AS overdue_count
    FROM decisions
    WHERE status = 'active' AND review_date < CURRENT_DATE
    GROUP BY category
)
SELECT
    sc.category,
    sc.status,
    sc.cnt                                                         AS decision_count,
    ROUND(sc.cnt::NUMERIC / sc.category_total * 100, 1)          AS pct_of_category,
    COALESCE(ao.overdue_count, 0)                                 AS overdue_in_active,
    sc.category_total                                             AS total_in_category,
    -- Running cumulative within each category ordered by count
    SUM(sc.cnt) OVER (
        PARTITION BY sc.category
        ORDER BY sc.cnt DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                                             AS cumulative_count
FROM status_counts sc
LEFT JOIN active_overdue ao ON sc.category = ao.category AND sc.status = 'active'
ORDER BY sc.category, sc.cnt DESC;
