-- 02 · Funnel by every segment in ONE query
-- Technique: UNPIVOT the segment columns so device / channel / city tier / speed / visitor type
-- become rows (dimension, segment). One GROUP BY then produces every segment funnel.
WITH base AS (
    SELECT
        device,
        channel,
        city_tier,
        CASE WHEN page_load_ms > 3000 THEN 'slow (>3s)' ELSE 'fast (<=3s)' END AS page_speed,
        CASE WHEN is_returning = 1 THEN 'returning' ELSE 'new' END            AS visitor_type,
        product_view, add_to_cart, checkout_start, payment_attempt, purchase, revenue_inr
    FROM session_funnel
    WHERE device <> 'unknown'
),
long AS (
    UNPIVOT base
    ON device, channel, city_tier, page_speed, visitor_type
    INTO NAME dimension VALUE segment
)
SELECT
    dimension,
    segment,
    COUNT(*)                                                         AS sessions,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY dimension), 1) AS share_pct,
    ROUND(100.0 * AVG(product_view), 1)                              AS view_rate_pct,
    ROUND(100.0 * SUM(add_to_cart)     / NULLIF(SUM(product_view), 0), 1)    AS view_to_cart_pct,
    ROUND(100.0 * SUM(checkout_start)  / NULLIF(SUM(add_to_cart), 0), 1)     AS cart_to_checkout_pct,
    ROUND(100.0 * SUM(payment_attempt) / NULLIF(SUM(checkout_start), 0), 1)  AS checkout_to_payment_pct,
    ROUND(100.0 * SUM(purchase)        / NULLIF(SUM(payment_attempt), 0), 1) AS payment_success_pct,
    ROUND(100.0 * AVG(purchase), 2)                                  AS cvr_pct,
    ROUND(SUM(revenue_inr) / COUNT(*), 1)                            AS revenue_per_session
FROM long
GROUP BY dimension, segment
ORDER BY dimension, sessions DESC;
