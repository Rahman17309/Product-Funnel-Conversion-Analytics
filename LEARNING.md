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

---

## Day 2: SQL deep-dive, A/B test and dashboard

### What was done
1. Wrote 7 standalone DuckDB SQL queries (`/sql`) and ran them in Notebook 03.
2. Sized the ₹ value of each hypothesis (H1, H3, H4, H5) with a consistent "close half the gap" assumption.
3. Analysed the one-page checkout experiment end to end in Notebook 04.
4. Built an interactive single-file dashboard (`dashboard/index.html`) with `src/build_dashboard.py`.

### Key concepts to understand
- **`UNPIVOT` for segment analysis:** instead of writing one query per dimension (device, channel, ...), turn the dimension
  columns into rows `(dimension, segment)` and group once. Less code, consistent definitions.
- **`QUALIFY`:** filters on a window function result (like `HAVING` for windows). Used to keep the single weakest step per segment.
- **Opportunity sizing:** always state the assumption ("close half the gap to desktop"), use a realistic benchmark, and say
  whether levers overlap. Here they do (slow pages are mostly mobile), so they're **not additive**. H4 was computed *within* device to avoid double-counting.
- **Confounding over time:** CVR rose 2.4% → 4.0%, but returning-visitor share also rose 23% → 79% (partly because the data
  starts on 1 Aug, so early visitors all look "new"). That's why before/after comparisons are unreliable and A/B tests compare groups over the *same* period.
- **A/B test checklist:**
  1. **SRM check:** is the split really 50/50? If not, the assignment is broken.
  2. **Balance check:** groups should look alike on the main drivers.
  3. **Primary metric + CI:** report the size of the effect and its uncertainty, not just a p-value.
  4. **Mechanism:** the lift appeared only at checkout → payment; earlier steps didn't move (a built-in A/A check).
  5. **Guardrails:** AOV and payment success didn't get worse.
  6. **Segments with a multiple-testing correction:** with 3 segments, use α = 0.05/3 (Bonferroni). No single device passed at
     session level; that's normal (segments are smaller), and why decisions rest on the overall result.
  7. **Regression adjustment:** a logistic regression with controls gives the same answer (odds ratio 1.19), so mix isn't driving it.
  8. **Power / MDE:** with ~21k sessions per arm the test could detect +0.52 pp; we saw +0.61 pp.
- **p-value vs confidence interval:** p ≈ 0.001 says the effect is very unlikely to be zero; the CI (+0.25 to +0.98 pp) says how
  big it plausibly is, which is what the business case needs (₹13–51 L/year range).

### Interview questions you should be able to answer after Day 2
1. *What is a sample ratio mismatch and why check it first?*
2. *Your mobile segment had p = 0.037. Why didn't you call it significant?* (Bonferroni: 0.037 > 0.0167.)
3. *Conversion went up after the launch. Why not just compare before vs after?* (Returning-visitor mix changed.)
4. *How did you estimate the value of fixing mobile checkout, and what are the weaknesses of that estimate?*
5. *Explain `QUALIFY` and when you'd use `UNPIVOT`.*
6. *Why use Welch's t-test and Mann-Whitney for order value?* (Unequal variances, skewed distribution.)
