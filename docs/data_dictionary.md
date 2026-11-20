# Data Dictionary

**Business context:** *ShopNest* is a fictional Indian direct-to-consumer e-commerce brand selling fashion, electronics,
home & kitchen, beauty and sports products on web and mobile web.
**Period:** 1 Aug 2026 – 30 Oct 2026 (91 days).
**Source:** synthetic data from `src/generate_data.py` (seed 42), calibrated to public e-commerce benchmarks.
No real customer data is used.

**Grain:** `sessions` = one row per visit · `events` = one row per tracked action · `orders` = one row per order.
**Keys:** `session_id` links all three tables; `user_id` links sessions of the same visitor.

---

## `data/raw/sessions.csv.gz` (82,000 rows → 80,000 after cleaning)

| Column | Type | Description | Example | Notes |
|---|---|---|---|---|
| `session_id` | string | Unique visit ID (primary key) | `S1000123` | Bot sessions use `S9xxxxxx` |
| `user_id` | string | Visitor ID (cookie/login based) | `U104512` | |
| `session_start` | datetime | Visit start time (IST) | `2026-09-18 21:14:03` | |
| `device` | string | `mobile`, `desktop`, `tablet` | `mobile` | ~1.2% null → cleaned to `unknown` |
| `channel` | string | Marketing channel that brought the visit | `paid_social` | Raw has mixed labels (`Paid Social`); standardised in cleaning |
| `city_tier` | string | `tier_1` (metros), `tier_2`, `tier_3` | `tier_2` | |
| `landing_page` | string | First page type: `home`, `category`, `product`, `offer` | `product` | |
| `is_returning` | int (0/1) | 1 if the user had an earlier session | `1` | |
| `page_load_ms` | int | Load time of the landing page in milliseconds | `2380` | `0` = no real browser render (bot signal) |
| `ab_group` | string | Checkout experiment arm: `control`, `variant`, `not_in_test` | `variant` | Test launched 15 Sep 2026; 50/50 split |

## `data/raw/events.csv.gz` (285,621 rows → 233,235 after cleaning)

| Column | Type | Description | Example | Notes |
|---|---|---|---|---|
| `session_id` | string | Session the event belongs to | `S1000123` | |
| `user_id` | string | Visitor | `U104512` | |
| `event_name` | string | Funnel step (see below) | `add_to_cart` | |
| `event_ts` | string → datetime | When the event happened | `2026-09-18 21:16:40` | Two formats in raw: ISO and `DD/MM/YYYY HH:MM:SS` |
| `product_category` | string | Category involved | `fashion` | Null on `session_start` |
| `payment_method` | string | `upi`, `card`, `cod`, `wallet` | `upi` | Only on `payment_attempt` / `purchase` |

### Funnel definition (in order)

| # | `event_name` | Meaning |
|---|---|---|
| 0 | `session_start` | Visitor lands on the site |
| 1 | `product_view` | Opens at least one product page (can repeat) |
| 2 | `add_to_cart` | Adds an item to the cart |
| 3 | `checkout_start` | Opens checkout (address/delivery step) |
| 4 | `payment_attempt` | Submits payment |
| 5 | `purchase` | Payment succeeded / COD order confirmed |

A session "reaches" a stage if it has at least one event of that type. Cleaning verifies no session skips a stage.

## `data/raw/orders.csv.gz` (2,789 rows → 2,734 after cleaning)

| Column | Type | Description | Example | Notes |
|---|---|---|---|---|
| `order_id` | string | Unique order ID | `O501234` | `TEST*` = QA test orders (removed) |
| `session_id` | string | Session in which the order was placed | `S1000123` | |
| `user_id` | string | Customer | `U104512` | |
| `order_ts` | datetime | Order time | `2026-09-18 21:19:02` | |
| `product_category` | string | Main category of the order | `electronics` | |
| `payment_method` | string | `upi`, `card`, `cod`, `wallet` | `card` | |
| `gross_value_inr` | float | Order value before discount (₹) | `2499.00` | |
| `discount_inr` | float | Discount applied (₹) | `250.00` | Higher on `offer` landing pages |
| `net_value_inr` | float | `gross − discount` (₹), used as revenue | `2249.00` | |

## Processed tables (`data/processed/`, created by `src/clean.py`)

| Table | Grain | Purpose |
|---|---|---|
| `sessions_clean` | session | Human sessions, standardised labels |
| `events_clean` | event | Parsed timestamps, no duplicates, no bots |
| `orders_clean` | order | Real orders only |
| `session_funnel` | session | Session attributes + 0/1 flag per funnel stage (`reached_session`, `product_view`, `add_to_cart`, `checkout_start`, `payment_attempt`, `purchase`) + `n_product_views` + `revenue_inr`. **Main analysis table.** |

## Metric definitions

| Metric | Formula |
|---|---|
| Conversion rate (CVR) | sessions with `purchase` ÷ all sessions |
| Step conversion | sessions reaching stage *k* ÷ sessions reaching stage *k−1* |
| Cart abandonment rate | 1 − (sessions with `purchase` ÷ sessions with `add_to_cart`) |
| Average order value (AOV) | sum of `net_value_inr` ÷ number of orders |
| Revenue per session (RPS) | sum of `net_value_inr` ÷ all sessions |
| Payment success rate | sessions with `purchase` ÷ sessions with `payment_attempt` |
