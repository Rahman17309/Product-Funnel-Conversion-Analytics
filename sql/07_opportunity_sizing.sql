-- 07 · Revenue opportunity for each hypothesis (quarterly, ₹)
-- Assumption for every lever: we close HALF of the gap to the benchmark (a realistic, not best-case, target).
-- Opportunities overlap (e.g. slow pages are mostly mobile), so they are NOT additive.
WITH aov AS (SELECT AVG(net_value_inr) AS aov FROM orders),
dev AS (
    SELECT device, COUNT(*) AS sessions, SUM(add_to_cart) AS carts,
           SUM(checkout_start) AS checkouts, SUM(payment_attempt) AS payments, SUM(purchase) AS orders
    FROM session_funnel WHERE device IN ('mobile', 'desktop') GROUP BY device
),
h1 AS (  -- H1: mobile cart->payment rate closes half the gap to desktop
    SELECT 'H1 Mobile checkout UX' AS lever,
           'mobile cart->payment rate moves halfway to desktop' AS assumption,
           m.carts * (((d.payments / d.carts) - (m.payments / m.carts)) / 2) * (m.orders / m.payments) AS extra_orders
    FROM dev m, dev d WHERE m.device = 'mobile' AND d.device = 'desktop'
),
ch AS (
    SELECT channel, COUNT(*) AS sessions, AVG(product_view) AS view_rate,
           SUM(purchase) / NULLIF(SUM(product_view), 0) AS view_to_order
    FROM session_funnel GROUP BY channel
),
h3 AS (  -- H3: paid-social product-view rate closes half the gap to the site average
    SELECT 'H3 Paid social landing pages' AS lever,
           'paid-social product-view rate moves halfway to site average' AS assumption,
           p.sessions * ((SELECT AVG(product_view) FROM session_funnel) - p.view_rate) / 2 * p.view_to_order AS extra_orders
    FROM ch p WHERE p.channel = 'paid_social'
),
spd AS (  -- H4 is measured WITHIN device to avoid the mobile confound
    SELECT device, page_load_ms > 3000 AS slow, COUNT(*) AS sessions, AVG(purchase) AS cvr
    FROM session_funnel WHERE device <> 'unknown' GROUP BY ALL
),
h4 AS (
    SELECT 'H4 Page speed (<3s)' AS lever,
           'slow sessions close half the CVR gap to fast sessions of the same device' AS assumption,
           SUM(s.sessions * (f.cvr - s.cvr) / 2) AS extra_orders
    FROM spd s JOIN spd f ON s.device = f.device AND s.slow AND NOT f.slow
),
pm AS (
    SELECT e.payment_method, COUNT(DISTINCT e.session_id) FILTER (WHERE event_name = 'payment_attempt') AS attempts,
           COUNT(DISTINCT e.session_id) FILTER (WHERE event_name = 'purchase') AS successes
    FROM events e GROUP BY 1
),
h5 AS (  -- H5: card success rate closes half the gap to UPI
    SELECT 'H5 Card payment success' AS lever,
           'card success rate moves halfway to UPI' AS assumption,
           c.attempts * ((u.successes / u.attempts) - (c.successes / c.attempts)) / 2 AS extra_orders
    FROM pm c, pm u WHERE c.payment_method = 'card' AND u.payment_method = 'upi'
),
allh AS (SELECT * FROM h1 UNION ALL SELECT * FROM h3 UNION ALL SELECT * FROM h4 UNION ALL SELECT * FROM h5)
SELECT lever, assumption,
       ROUND(extra_orders)                          AS extra_orders_per_quarter,
       ROUND(extra_orders * aov.aov / 1e5, 2)        AS extra_revenue_lakh_per_quarter,
       ROUND(extra_orders * aov.aov * 4 / 1e5, 1)    AS extra_revenue_lakh_per_year,
       RANK() OVER (ORDER BY extra_orders DESC)      AS priority
FROM allh, aov
ORDER BY priority;
