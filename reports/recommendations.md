# ShopNest Funnel Review: Recommendations

**Prepared for:** Head of Product, Growth and Finance · **Period analysed:** 1 Aug – 30 Oct 2026 (80,000 human sessions)
**Author:** M A Rahman, Data Analyst

---

## 1. Executive summary

ShopNest converts **3.42%** of sessions into orders (2,734 orders, ₹44.8 L revenue, AOV ₹1,640) and loses **67.9%** of
carts before purchase. The leaks are concentrated, measurable and fixable:

1. **Ship the one-page checkout.** It is the only change here that has been *proven* in a randomised test:
   conversion **3.55% → 4.16% (+17%, p = 0.001)**, driven by mobile checkout → payment (**+8.4 pp, p < 0.001**), with no harm
   to order value or payment success. Expected value at today's traffic: **~₹32 L / year** (95% range ₹13–51 L).
2. **Fix page speed next.** One in four sessions loads in more than 3 seconds, and those sessions convert at **1.9% vs 3.9%**.
   Closing half that gap is worth **~₹11 L / year**. This is observational, so it should be confirmed with an A/B test (§4).
3. **Smaller, cheaper wins:** paid-social landing pages (~₹3 L / year) and card-payment reliability (~₹2.6 L / year).

Recommendation 1 can go live this sprint. Recommendations 2–3 should each start with a test, not a full build.

## 2. Prioritised recommendations

| # | Recommendation | Evidence | Est. annual value | Confidence | Effort |
|---|---|---|---|---|---|
| 1 | **Roll out one-page checkout:** 100% of mobile now; desktop at 90% with a 10% holdout for 4 weeks | Randomised A/B test, 42,914 sessions | **~₹32 L** (₹13–51 L) | **High**: causal | Low (already built) |
| 2 | **Get mobile pages under 3s:** compress/resize images, lazy-load below the fold, defer third-party scripts on product and checkout pages | Slow sessions convert at half the rate *within the same device* | **~₹11 L** | Medium: observational | Medium |
| 3 | **Rework paid-social landing pages:** land on the product advertised (not the home page), match ad creative to page | Paid social is 22% of traffic but 2.0% CVR and ₹31 revenue/session vs ₹69 for paid search; the gap is at product view (55.8% vs 70.0% site average) | **~₹3 L** | Medium | Low–medium |
| 4 | **Improve card payment success:** automatic retry on soft declines, offer UPI as fallback on failure, review gateway routing | Card success 79.9% vs UPI 89.5%; same on mobile and desktop, so it's the gateway, not the device | **~₹2.6 L** | Medium | Low |
| 5 | **Grow returning visitors:** post-purchase email/WhatsApp flows and saved carts | Returning visitors convert 4.07% vs 2.45%; email is the best channel (4.95% CVR, ₹78 revenue/session) | Not sized | Low–medium | Medium |

**How the values were estimated.** Each lever closes **half** the gap to a realistic internal benchmark (desktop for mobile
checkout, fast sessions of the same device for speed, the site average for paid social, UPI for cards), converted to orders
and multiplied by AOV. Half, not all, because a full close is rarely achieved.

**The values are not additive.** The one-page checkout *is* the mobile-checkout fix (the earlier "close half the mobile gap"
estimate of ~₹26 L is the same opportunity, so it is not counted twice). Slow pages are mostly mobile too, so recommendation 2
will overlap partly with 1. A rough combined target for 1 + 2 is **₹35–40 L / year**, not the ₹43 L you get by simply adding them.

## 3. Risks and how to manage them

| Risk | Why it matters | Mitigation |
|---|---|---|
| **Festive-season test window** (15 Sep – 30 Oct) | Lift may be smaller in a normal month | Keep the 10% desktop holdout and compare monthly; re-check mobile in January |
| **Novelty effect** | Users may react to anything new | Track checkout → payment weekly for 6 weeks after rollout |
| **Session-level randomisation** | A returning user could have seen both versions | Use user-level assignment for future tests |
| **Opportunity sizes depend on AOV and traffic** | Both move with season and marketing spend | Re-run `sql/07_opportunity_sizing.sql` each quarter; it takes seconds |
| **Synthetic data** | This is a portfolio dataset | The method, SQL and checks transfer directly to a real export |

## 4. Next experiments

| Test | Hypothesis | Primary metric | Sample needed (80% power, α = 0.05) | Duration at current traffic |
|---|---|---|---|---|
| **Mobile page-speed** (optimised vs current pages, slow-connection users) | Faster pages lift conversion | Session CVR among sessions that would load > 3s | ~3,600 per arm to detect 1.9% → 2.9% | ~5 weeks |
| **Paid-social landing pages** | Product-specific landing raises product views and CVR | Session CVR (paid social) | ~14,000 per arm to detect 2.0% → 2.5% | ~5 months: too long, so test a bolder change or accept a larger minimum effect |
| **Card retry + UPI fallback** | Fewer lost orders on card failure | Payment success per attempt | ~870 per arm to detect 79.9% → 85.0% | Long at 9 card attempts/day: run as a gateway-level before/after with a control period instead |

## 5. Appendix: where each number comes from

| Number | Source |
|---|---|
| Headline KPIs, segment funnels | `sql/01_overall_funnel.sql`, `sql/02_segment_funnel.sql` |
| Weakest step per segment | `sql/03_weakest_step_by_segment.sql` |
| Payment success by method | `sql/06_payment_failures.sql` |
| Opportunity sizing (₹) | `sql/07_opportunity_sizing.sql` |
| A/B test, rollout value, segment results | `notebooks/04_ab_test_one_page_checkout.ipynb` |
| Sample sizes in §4 | `statsmodels` power analysis (two-sided, α = 0.05, power 0.8) |
