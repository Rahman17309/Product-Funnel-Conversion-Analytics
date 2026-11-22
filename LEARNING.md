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

---

## Day 3: Recommendations, risks and the final write-up

### What was done
1. Wrote [`reports/recommendations.md`](reports/recommendations.md): executive summary, 5 prioritised recommendations with ₹ value,
   confidence and effort, a risk register, and next experiments with sample sizes.
2. Reconciled the two value estimates for the checkout (₹26 L "close half the mobile gap" vs ₹32 L from the A/B test) so they're not double-counted.
3. Ran power analyses for the next three tests and flagged the ones that would take too long at current traffic.
4. Finalised the README (status, recommendations, limitations), published the dashboard and a case-study page on the portfolio,
   and re-ran the whole pipeline from a fresh clone.

### Key concepts to understand
- **Lead with the decision, not the analysis.** An executive summary answers "what should we do, what's it worth, how sure are we" in the first lines.
- **Rank by value × confidence × effort.** A proven ₹32 L change that's already built beats a bigger but untested idea.
- **Label evidence strength.** "Randomised test" (causal) and "slow pages convert worse" (observational) are not the same kind of claim; say which is which.
- **Don't double-count overlapping levers.** The one-page checkout *is* the mobile-checkout fix, and slow pages are mostly mobile. Adding the numbers overstates the prize.
- **Plan the test before you run it.** A power analysis turns "let's test it" into "we need ~3,600 sessions per arm, about five weeks". When the answer is five months, change the design instead of running an inconclusive test.
- **Make it reproducible.** One command per step, raw data committed, every cleaning rule logged, and a fresh-clone check before calling it done.

### Interview Q&A (model answers)

**1. Walk me through this project in two minutes.**
> An e-commerce brand converted 3.4% of 80,000 sessions. I cleaned the clickstream (bots, duplicate events, mixed timestamps,
> test orders), built a one-row-per-session funnel table, and used SQL to find where each segment leaks. Mobile converted 41%
> worse than desktop, with the gap opening after the cart. I sized each fix in rupees, then analysed the one-page checkout A/B test:
> +17% conversion, p = 0.001, driven by mobile checkout → payment, with flat guardrails. I recommended rolling it out
> (~₹32 L a year), fixing page speed next (~₹11 L, to be confirmed by a test), and smaller wins on paid social and card payments.

**2. How did you detect bots, and how do you know you didn't remove real users?**
> By behaviour, not by ID: 15 or more product views in 60 seconds, or a 0 ms page load. Real users never came close to those
> thresholds, so the two groups didn't overlap. Every removal is logged with a row count so it can be audited.

**3. What is the grain of your main table, and why does it matter?**
> One row per session with a 0/1 flag per stage. Sessions, events and orders have different grains; joining events to orders
> without rolling up first double-counts. Fixing the grain first makes every rate simple and correct.

**4. Conversion rose from 2.4% to 4.0% after the launch. Why not credit the new checkout?**
> Because the mix changed at the same time: returning visitors went from 23% to 79% of traffic, and they convert much better.
> A before/after comparison mixes the two effects. The A/B test compares both versions over the same period with the same mix.

**5. What do you check before reading an A/B test result?**
> Sample ratio (is it really 50/50? p = 0.43 here), balance on the main drivers, then the primary metric with a confidence
> interval, the mechanism (did the targeted step move?), guardrails (order value, payment success), segments with a
> multiple-testing correction, and power.

**6. Mobile had p = 0.037. Why didn't you call it significant?**
> I tested three device segments, so with a Bonferroni correction the threshold is 0.05 / 3 ≈ 0.017. 0.037 doesn't pass.
> The decision rests on the overall result, which is significant, and on the mechanism: mobile checkout → payment +8.4 pp, p < 0.001.

**7. p-value or confidence interval: which matters more to the business?**
> Both, for different questions. The p-value says the effect is unlikely to be zero; the interval (+0.25 to +0.98 pp) says how big
> it plausibly is, which is what turns into the ₹13–51 L range for the business case.

**8. How did you put a rupee value on each fix, and what are the weaknesses?**
> Close half the gap to a realistic benchmark, convert to extra orders, multiply by AOV. Weaknesses: the "half" is an assumption,
> AOV and traffic change with season, and the levers overlap, so I said they're not additive and gave a combined range instead.

**9. Why do the ₹26 L and ₹32 L checkout numbers differ?**
> ₹26 L assumes mobile closes half its gap to desktop. ₹32 L is measured: the test lifted every device a little, including desktop,
> and it's applied to all sessions. They describe the same opportunity, so only one is counted.

**10. Why recommend a desktop holdout instead of a full rollout?**
> Desktop's lift was positive but didn't pass the corrected threshold and has a wide interval. A 10% holdout costs little and tells
> us the real desktop effect after four weeks.

**11. Slow pages convert at half the rate. Isn't that enough to act on?**
> It's enough to prioritise, not to promise a number. Slow pages are mostly mobile and lower-tier cities, so part of the gap is the
> audience, not the speed. I sized it within device to reduce that bias and recommended an A/B test to confirm.

**12. How did you decide whether a test is worth running?**
> Power analysis. To detect 1.9% → 2.9% on slow sessions needs about 3,600 sessions per arm, roughly five weeks: worth it.
> Paid social needs about 14,000 per arm, roughly five months: I'd test a bolder change or accept a bigger minimum effect.

**13. Explain `QUALIFY` and `UNPIVOT` from your SQL.**
> `UNPIVOT` turns the device and channel columns into rows, so one `GROUP BY` covers every dimension with the same definitions.
> `QUALIFY` filters on a window function, like `HAVING` for windows: I ranked steps within each segment and kept rank 1, the weakest step.

**14. Why Welch's t-test and Mann-Whitney for order value?**
> Order values are right-skewed and the groups' variances differ. Welch's t-test doesn't assume equal variances, and Mann-Whitney
> doesn't assume normality. Both agreed: no change in AOV.

**15. What would you do differently with real data?**
> Randomise by user rather than session, run tests outside the festive season or for longer, add cost data so the
> recommendations show profit rather than revenue, and automate the quarterly re-run of the sizing query.

**16. The data is synthetic. Why should I trust your skills from it?**
> The messiness is realistic (bots, duplicates, mixed formats, test orders) and every method is the one I'd use on a real export.
> The project shows the reasoning, the checks and the communication, which are what transfer.
