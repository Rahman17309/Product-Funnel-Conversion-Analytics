-- 05 · Weekly conversion trend with a 4-week moving average and week-over-week change
-- Technique: DATE_TRUNC + window frames (ROWS BETWEEN) + LAG.
WITH weekly AS (
    SELECT DATE_TRUNC('week', session_start)          AS week,
           COUNT(*)                                    AS sessions,
           SUM(purchase)                               AS orders,
           ROUND(100.0 * AVG(is_returning), 1)          AS returning_pct,
           SUM(revenue_inr)                            AS revenue
    FROM session_funnel
    GROUP BY 1
)
SELECT week, sessions, orders, returning_pct,
       ROUND(100.0 * orders / sessions, 2)                                    AS cvr_pct,
       ROUND(AVG(100.0 * orders / sessions) OVER (ORDER BY week
             ROWS BETWEEN 3 PRECEDING AND CURRENT ROW), 2)                    AS cvr_4wk_avg_pct,
       ROUND(100.0 * (sessions / LAG(sessions) OVER (ORDER BY week) - 1), 1)  AS sessions_wow_pct,
       ROUND(revenue)                                                         AS revenue_inr
FROM weekly
ORDER BY week;
