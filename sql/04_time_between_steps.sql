-- 04 · How long do people take between steps? (converted sessions only)
-- Technique: conditional MIN() to pivot first timestamp per stage, then median/p90 with QUANTILE_CONT.
WITH firsts AS (
    SELECT session_id,
           MIN(event_ts) FILTER (WHERE event_name = 'session_start')   AS t0,
           MIN(event_ts) FILTER (WHERE event_name = 'add_to_cart')     AS t2,
           MIN(event_ts) FILTER (WHERE event_name = 'checkout_start')  AS t3,
           MIN(event_ts) FILTER (WHERE event_name = 'payment_attempt') AS t4,
           MIN(event_ts) FILTER (WHERE event_name = 'purchase')        AS t5
    FROM events
    GROUP BY session_id
    HAVING t5 IS NOT NULL
),
gaps AS (
    SELECT f.session_id, s.device,
           date_diff('second', t0, t2) AS land_to_cart_s,
           date_diff('second', t2, t3) AS cart_to_checkout_s,
           date_diff('second', t3, t4) AS checkout_to_payment_s,
           date_diff('second', t0, t5) AS land_to_purchase_s
    FROM firsts f JOIN sessions s USING (session_id)
)
SELECT device,
       COUNT(*)                                           AS orders,
       ROUND(QUANTILE_CONT(land_to_cart_s, 0.5) / 60, 1)        AS median_land_to_cart_min,
       ROUND(QUANTILE_CONT(cart_to_checkout_s, 0.5) / 60, 1)    AS median_cart_to_checkout_min,
       ROUND(QUANTILE_CONT(checkout_to_payment_s, 0.5) / 60, 1) AS median_checkout_to_payment_min,
       ROUND(QUANTILE_CONT(land_to_purchase_s, 0.5) / 60, 1)    AS median_total_min,
       ROUND(QUANTILE_CONT(land_to_purchase_s, 0.9) / 60, 1)    AS p90_total_min
FROM gaps
GROUP BY device
ORDER BY orders DESC;
