# Learning Log

A day-by-day record of what was built in this project, **why** each decision was made, and the
concepts worth being able to explain in an interview.

---

## Day 1: Setup, data quality and EDA

### What was done
1. Defined the business problem and the funnel (session → product view → add to cart → checkout → payment → purchase).
2. Built a reproducible data generator (`src/generate_data.py`), since real clickstream data is confidential.
3. Wrote a cleaning pipeline (`src/clean.py`) that logs every rule to `reports/data_quality_log.csv`.
4. Built the main analysis table, `session_funnel`: **one row per session, one 0/1 column per stage**.
5. Ran exploratory analysis and wrote down 5 hypotheses to test on Day 2.

### Key concepts to understand
- **Grain of a table:** always know what one row means. Sessions, events and orders each have a different grain,
  and joining them carelessly double-counts. That's why `session_funnel` is rolled up to one row per session first.
- **Step conversion vs overall conversion:** step = stage k ÷ stage k−1 (where the leak is); overall = stage k ÷ sessions.
  Product view → add to cart (15%) is the biggest leak by volume, but checkout users are higher-value to recover.
- **Why bots matter:** they add sessions but never buy, so they *lower* conversion and distort segments. They were
  detected by **behaviour** (24 views in 24s), not by their ID, because real bots don't label themselves.
- **Auditability:** every cleaning rule records the rows it touched, so anyone can see what changed and why.
- **Correlation is not causation:** slow pages convert worse, but slow pages are also mostly mobile and tier-3.
  EDA produces *hypotheses*; tests (segmenting, A/B tests) produce *conclusions*.
- **Honest reading of a trend:** conversion rose from 2.8% (Aug) to 3.9% (Oct). It's tempting to credit the new checkout,
  but the share of returning visitors also grew. Day 2 separates these effects.

### Interview questions you should be able to answer after Day 1
1. *How did you identify bot traffic, and how do you know the rule is safe?* (The two groups don't overlap at all.)
2. *Why did you keep sessions with a missing device instead of dropping them?* (They're real sessions; dropping them would bias CVR.)
3. *What's the difference between cart abandonment and checkout abandonment?*
4. *Why is the product-view → add-to-cart step not automatically the first thing to fix?*
