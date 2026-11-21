-- 03 · For each segment, which step under-performs the site average the most?
-- Technique: compare every segment-step rate to the site-wide rate, then RANK() within the segment
-- and keep the worst step (QUALIFY).
WITH base AS (
    SELECT device, channel,
           product_view, add_to_cart, checkout_start, payment_attempt, purchase
    FROM session_funnel WHERE device <> 'unknown'
),
long AS (
    UNPIVOT base ON device, channel INTO NAME dimension VALUE segment
),
seg AS (
    SELECT dimension, segment, COUNT(*) AS sessions,
           AVG(product_view)                                     AS r1_session_to_view,
           SUM(add_to_cart)     / NULLIF(SUM(product_view), 0)    AS r2_view_to_cart,
           SUM(checkout_start)  / NULLIF(SUM(add_to_cart), 0)     AS r3_cart_to_checkout,
           SUM(payment_attempt) / NULLIF(SUM(checkout_start), 0)  AS r4_checkout_to_payment,
           SUM(purchase)        / NULLIF(SUM(payment_attempt), 0) AS r5_payment_success
    FROM long GROUP BY ALL
),
site AS (
    SELECT AVG(product_view)                       AS r1_session_to_view,
           SUM(add_to_cart) / SUM(product_view)     AS r2_view_to_cart,
           SUM(checkout_start) / SUM(add_to_cart)   AS r3_cart_to_checkout,
           SUM(payment_attempt) / SUM(checkout_start) AS r4_checkout_to_payment,
           SUM(purchase) / SUM(payment_attempt)     AS r5_payment_success
    FROM session_funnel
),
seg_long AS (
    UNPIVOT seg ON COLUMNS('^r[0-9]') INTO NAME step VALUE seg_rate
),
site_long AS (
    UNPIVOT site ON COLUMNS(*) INTO NAME step VALUE site_rate
)
SELECT s.dimension, s.segment, s.sessions,
       substr(s.step, 4)                                     AS weakest_step,
       ROUND(100 * s.seg_rate, 1)                            AS segment_rate_pct,
       ROUND(100 * t.site_rate, 1)                           AS site_rate_pct,
       ROUND(100 * (s.seg_rate / t.site_rate - 1), 1)        AS vs_site_pct
FROM seg_long s JOIN site_long t USING (step)
QUALIFY RANK() OVER (PARTITION BY s.dimension, s.segment ORDER BY s.seg_rate / t.site_rate) = 1
ORDER BY vs_site_pct;
