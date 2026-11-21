-- 06 · Payment success by method and device
WITH pay AS (
    SELECT e.session_id, e.payment_method, s.device,
           MAX(CASE WHEN e.event_name = 'purchase' THEN 1 ELSE 0 END) AS succeeded
    FROM events e JOIN sessions s USING (session_id)
    WHERE e.event_name IN ('payment_attempt', 'purchase')
    GROUP BY ALL
)
SELECT payment_method,
       COUNT(*)                                       AS attempts,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_of_attempts_pct,
       SUM(succeeded)                                 AS successes,
       COUNT(*) - SUM(succeeded)                      AS failures,
       ROUND(100.0 * AVG(succeeded), 1)               AS success_rate_pct,
       ROUND(100.0 * AVG(succeeded) FILTER (WHERE device = 'mobile'), 1)  AS mobile_success_pct,
       ROUND(100.0 * AVG(succeeded) FILTER (WHERE device = 'desktop'), 1) AS desktop_success_pct
FROM pay
GROUP BY payment_method
ORDER BY attempts DESC;
