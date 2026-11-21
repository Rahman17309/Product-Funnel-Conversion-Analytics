-- 01 · Overall funnel with step conversion and drop-off
-- Technique: UNPIVOT wide 0/1 stage flags to long format, then LAG() over the stage order.
WITH stage_counts AS (
    SELECT
        SUM(reached_session)  AS s0_session,
        SUM(product_view)     AS s1_product_view,
        SUM(add_to_cart)      AS s2_add_to_cart,
        SUM(checkout_start)   AS s3_checkout_start,
        SUM(payment_attempt)  AS s4_payment_attempt,
        SUM(purchase)         AS s5_purchase
    FROM session_funnel
),
long AS (
    UNPIVOT stage_counts ON COLUMNS(*) INTO NAME stage VALUE sessions
)
SELECT
    CAST(substr(stage, 2, 1) AS INT)                        AS step,
    substr(stage, 4)                                       AS stage,
    sessions,
    LAG(sessions) OVER (ORDER BY stage)                     AS prev_stage_sessions,
    ROUND(100.0 * sessions / LAG(sessions) OVER (ORDER BY stage), 1)      AS step_conversion_pct,
    ROUND(100.0 * sessions / FIRST_VALUE(sessions) OVER (ORDER BY stage), 2) AS of_all_sessions_pct,
    LAG(sessions) OVER (ORDER BY stage) - sessions          AS lost_at_step
FROM long
ORDER BY step;
