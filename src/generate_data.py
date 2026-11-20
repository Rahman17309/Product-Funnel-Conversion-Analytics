"""
Synthetic clickstream generator for "ShopNest" — a fictional Indian D2C e-commerce brand.

Why synthetic?
    Real clickstream data is confidential. This generator produces realistic, reproducible
    data whose conversion rates are calibrated to public e-commerce benchmarks
    (overall CVR ~2-3%, mobile converting below desktop, cart abandonment ~70%).
    Realistic data-quality problems are injected on purpose so the cleaning step
    mirrors real-world work.

Outputs (data/raw/):
    sessions.csv  - one row per website session
    events.csv    - one row per funnel event (clickstream)
    orders.csv    - one row per order placed

Usage:
    python src/generate_data.py            # default 80,000 sessions, seed 42
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

START = pd.Timestamp("2026-08-01")
END = pd.Timestamp("2026-10-31")          # exclusive
AB_TEST_START = pd.Timestamp("2026-09-15")  # one-page checkout experiment launch

DEVICES = (["mobile", "desktop", "tablet"], [0.68, 0.26, 0.06])
CHANNELS = (
    ["organic_search", "paid_search", "paid_social", "email", "direct", "referral", "affiliate"],
    [0.27, 0.18, 0.22, 0.08, 0.15, 0.05, 0.05],
)
CITY_TIERS = (["tier_1", "tier_2", "tier_3"], [0.48, 0.32, 0.20])
LANDING = (["home", "category", "product", "offer"], [0.35, 0.25, 0.28, 0.12])
CATEGORIES = (["fashion", "electronics", "home_kitchen", "beauty", "sports"],
              [0.34, 0.18, 0.20, 0.18, 0.10])
PAYMENT = (["upi", "card", "cod", "wallet"], [0.55, 0.25, 0.15, 0.05])
PAY_SUCCESS = {"upi": 0.90, "card": 0.80, "cod": 0.97, "wallet": 0.88}

# Channel effect on product-view rate (intent of the traffic)
CH_VIEW = {"organic_search": 0.66, "paid_search": 0.70, "paid_social": 0.47, "email": 0.78,
           "direct": 0.68, "referral": 0.60, "affiliate": 0.55}
CH_CART = {"organic_search": 1.00, "paid_search": 1.05, "paid_social": 0.75, "email": 1.25,
           "direct": 1.10, "referral": 0.95, "affiliate": 0.90}


def _choice(rng, spec, n):
    vals, p = spec
    return rng.choice(vals, size=n, p=p)


def generate(n_sessions: int = 80_000, seed: int = 42) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)

    # ---------------- users & sessions ----------------
    n_users = int(n_sessions * 0.62)
    user_ids = np.array([f"U{100000 + i}" for i in range(n_users)])
    # Heavy-tailed visit frequency: a few loyal users, many one-timers
    weights = rng.pareto(1.6, n_users) + 1
    sess_user = rng.choice(user_ids, size=n_sessions, p=weights / weights.sum())

    # Session timestamps: weekly seasonality + evening peak + festive ramp in October
    days = (END - START).days
    day_w = np.array([
        (1.15 if (START + pd.Timedelta(days=d)).dayofweek >= 5 else 1.0)
        * (1 + 0.45 * max(0, d - 60) / 30)       # festive season build-up in Oct
        for d in range(days)
    ])
    day_idx = rng.choice(days, size=n_sessions, p=day_w / day_w.sum())
    hour_w = np.array([1, .6, .4, .3, .3, .4, .8, 1.3, 1.7, 2, 2.1, 2.2, 2.4, 2.3, 2.1, 2.1,
                       2.2, 2.4, 2.8, 3.3, 3.7, 3.6, 2.8, 1.8])
    hours = rng.choice(24, size=n_sessions, p=hour_w / hour_w.sum())
    secs = rng.integers(0, 3600, n_sessions)
    start_ts = START + pd.to_timedelta(day_idx, "D") + pd.to_timedelta(hours, "h") + pd.to_timedelta(secs, "s")

    order = np.argsort(start_ts.values)
    start_ts = start_ts[order]
    sess_user = sess_user[order]

    s = pd.DataFrame({
        "session_id": [f"S{1000000 + i}" for i in range(n_sessions)],
        "user_id": sess_user,
        "session_start": start_ts,
        "device": _choice(rng, DEVICES, n_sessions),
        "channel": _choice(rng, CHANNELS, n_sessions),
        "city_tier": _choice(rng, CITY_TIERS, n_sessions),
        "landing_page": _choice(rng, LANDING, n_sessions),
    })
    # new vs returning: first session of a user is "new"
    s["is_returning"] = s.duplicated("user_id").astype(int)

    # Page load time (ms): mobile & tier_3 slower; lognormal
    base = np.where(s.device == "mobile", 2300, np.where(s.device == "tablet", 2000, 1500))
    base = base * np.where(s.city_tier == "tier_3", 1.35, np.where(s.city_tier == "tier_2", 1.12, 1.0))
    s["page_load_ms"] = (base * rng.lognormal(0, 0.38, n_sessions)).round().astype(int)

    # A/B test: 50/50 split of sessions after launch
    in_test = s.session_start >= AB_TEST_START
    s["ab_group"] = np.where(in_test, rng.choice(["control", "variant"], n_sessions), "not_in_test")

    # ---------------- funnel simulation ----------------
    n = n_sessions
    returning = s.is_returning.values == 1
    dev = s.device.values
    ch = s.channel.values
    slow = s.page_load_ms.values > 3000

    p_view = np.vectorize(CH_VIEW.get)(ch) + 0.07 * returning
    p_view = np.where(s.landing_page.values == "product", np.minimum(p_view + 0.25, 0.97), p_view)
    p_view = p_view * np.where(slow, 0.82, 1.0)

    p_cart = 0.14 * np.vectorize(CH_CART.get)(ch) * np.where(returning, 1.3, 1.0)
    p_cart = p_cart * np.where(slow, 0.72, 1.0) * np.where(s.city_tier.values == "tier_3", 0.9, 1.0)

    p_checkout = np.where(dev == "mobile", 0.46, np.where(dev == "tablet", 0.55, 0.64))
    p_checkout = p_checkout + 0.06 * returning

    # Experiment: one-page checkout lifts checkout->payment, mostly on mobile
    p_pay = np.where(dev == "mobile", 0.60, np.where(dev == "tablet", 0.68, 0.74))
    variant = s.ab_group.values == "variant"
    p_pay = p_pay + variant * np.where(dev == "mobile", 0.085, 0.02)

    reached_view = rng.random(n) < p_view
    reached_cart = reached_view & (rng.random(n) < p_cart)
    reached_chk = reached_cart & (rng.random(n) < p_checkout)
    reached_pay = reached_chk & (rng.random(n) < p_pay)
    pay_method = _choice(rng, PAYMENT, n)
    pay_ok = rng.random(n) < np.vectorize(PAY_SUCCESS.get)(pay_method)
    purchased = reached_pay & pay_ok

    # ---------------- events ----------------
    stage_flags = [
        ("session_start", np.ones(n, bool)),
        ("product_view", reached_view),
        ("add_to_cart", reached_cart),
        ("checkout_start", reached_chk),
        ("payment_attempt", reached_pay),
        ("purchase", purchased),
    ]
    gaps_mean = {"product_view": 25, "add_to_cart": 140, "checkout_start": 90,
                 "payment_attempt": 70, "purchase": 25}
    category = _choice(rng, CATEGORIES, n)

    ev_frames = []
    cur = s.session_start.values.copy()
    for name, flag in stage_flags:
        if name != "session_start":
            gap = rng.exponential(gaps_mean[name], n).astype("int64") + 3
            cur = cur + gap.astype("timedelta64[s]")
        idx = np.where(flag)[0]
        ev_frames.append(pd.DataFrame({
            "session_id": s.session_id.values[idx],
            "user_id": s.user_id.values[idx],
            "event_name": name,
            "event_ts": cur[idx],
            "product_category": np.where(name == "session_start", None, category[idx]),
            "payment_method": np.where(name in ("payment_attempt", "purchase"), pay_method[idx], None),
        }))
    # Extra browsing: multiple product views for engaged sessions
    extra_idx = np.where(reached_view)[0]
    extra_n = rng.poisson(1.4, extra_idx.size)
    rep = np.repeat(extra_idx, extra_n)
    ev_frames.append(pd.DataFrame({
        "session_id": s.session_id.values[rep],
        "user_id": s.user_id.values[rep],
        "event_name": "product_view",
        "event_ts": s.session_start.values[rep] + rng.integers(10, 240, rep.size).astype("timedelta64[s]"),
        "product_category": _choice(rng, CATEGORIES, rep.size),
        "payment_method": None,
    }))
    ev = pd.concat(ev_frames, ignore_index=True).sort_values(["event_ts", "session_id"]).reset_index(drop=True)

    # ---------------- orders ----------------
    pidx = np.where(purchased)[0]
    cat_mult = {"fashion": 1.0, "electronics": 2.6, "home_kitchen": 1.3, "beauty": 0.7, "sports": 1.4}
    gross = 1150 * rng.lognormal(0, 0.55, pidx.size) * np.vectorize(cat_mult.get)(category[pidx])
    disc_rate = np.where(s.landing_page.values[pidx] == "offer", rng.uniform(0.15, 0.35, pidx.size),
                         rng.choice([0, 0, 0.05, 0.10, 0.15], pidx.size))
    purchase_ts = ev[ev.event_name == "purchase"].set_index("session_id").event_ts
    o = pd.DataFrame({
        "order_id": [f"O{500000 + i}" for i in range(pidx.size)],
        "session_id": s.session_id.values[pidx],
        "user_id": s.user_id.values[pidx],
        "order_ts": purchase_ts.reindex(s.session_id.values[pidx]).values,
        "product_category": category[pidx],
        "payment_method": pay_method[pidx],
        "gross_value_inr": gross.round(2),
        "discount_inr": (gross * disc_rate).round(2),
    })
    o["net_value_inr"] = (o.gross_value_inr - o.discount_inr).round(2)

    s_out = s.drop(columns=[]).copy()
    return inject_quality_issues(s_out, ev, o, rng)


def inject_quality_issues(s, ev, o, rng):
    """Inject the messy problems analysts meet in real exports."""
    s = s.copy(); ev = ev.copy(); o = o.copy()

    # 1) Inconsistent channel labels from different tracking tools
    mask = rng.random(len(s)) < 0.06
    s.loc[mask, "channel"] = s.loc[mask, "channel"].str.replace("_", " ").str.title()

    # 2) Missing device (tracking script blocked)
    s.loc[rng.random(len(s)) < 0.012, "device"] = np.nan

    # 3) Bot / crawler sessions: many rapid product views, zero load time, never convert
    n_bots = int(len(s) * 0.025)
    bots = pd.DataFrame({
        "session_id": [f"S{9000000 + i}" for i in range(n_bots)],
        "user_id": [f"BOT{i % 40}" for i in range(n_bots)],
        "session_start": s.session_start.sample(n_bots, random_state=7).values,
        "device": "desktop", "channel": "direct", "city_tier": "tier_1",
        "landing_page": "category", "is_returning": 1, "page_load_ms": 0, "ab_group": "not_in_test",
    })
    bots.loc[bots.session_start >= AB_TEST_START, "ab_group"] = rng.choice(
        ["control", "variant"], (bots.session_start >= AB_TEST_START).sum())
    bot_ev = bots.loc[bots.index.repeat(25), ["session_id", "user_id", "session_start"]].copy()
    bot_ev["event_ts"] = bot_ev.session_start + pd.to_timedelta(np.tile(np.arange(25), n_bots), "s")
    bot_ev["event_name"] = np.where(np.tile(np.arange(25), n_bots) == 0, "session_start", "product_view")
    bot_ev["product_category"] = np.where(bot_ev.event_name == "product_view", "electronics", None)
    bot_ev["payment_method"] = None
    s = pd.concat([s, bots], ignore_index=True)
    ev = pd.concat([ev, bot_ev.drop(columns="session_start")], ignore_index=True)

    # 4) Duplicate events (double-fired tracking pixels)
    dups = ev.sample(frac=0.008, random_state=11)
    ev = pd.concat([ev, dups], ignore_index=True)

    # 5) Test orders from the QA team (net value of Rs 1) and a few duplicated order rows
    test = o.sample(35, random_state=3).copy()
    test["order_id"] = [f"TEST{i}" for i in range(len(test))]
    test[["gross_value_inr", "discount_inr", "net_value_inr"]] = [1.0, 0.0, 1.0]
    o = pd.concat([o, test, o.sample(20, random_state=5)], ignore_index=True)

    # 6) Timestamps exported as strings in two formats
    ev["event_ts"] = pd.to_datetime(ev.event_ts)
    alt = rng.random(len(ev)) < 0.04
    ev["event_ts"] = ev.event_ts.dt.strftime("%Y-%m-%d %H:%M:%S")
    ev.loc[alt, "event_ts"] = pd.to_datetime(ev.loc[alt, "event_ts"]).dt.strftime("%d/%m/%Y %H:%M:%S")

    ev = ev.sample(frac=1, random_state=1).reset_index(drop=True)  # exports are unordered
    return {"sessions": s, "events": ev, "orders": o}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=80_000)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    data = generate(a.sessions, a.seed)
    for name, df in data.items():
        df.to_csv(RAW / f"{name}.csv.gz", index=False, compression="gzip")
        print(f"{name:9s} {len(df):>8,} rows -> data/raw/{name}.csv.gz")


if __name__ == "__main__":
    main()
