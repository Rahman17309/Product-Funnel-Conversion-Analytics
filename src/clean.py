"""
Data-quality checks and cleaning pipeline.

Reads data/raw/*.csv.gz, fixes the issues found during profiling, and writes
analysis-ready tables to data/processed/:

    sessions_clean.parquet   - human sessions only, standardised labels
    events_clean.parquet     - de-duplicated, parsed timestamps, bots removed
    orders_clean.parquet     - real orders only (test + duplicate rows removed)
    session_funnel.parquet   - one row per session with a 0/1 flag per funnel stage

Every rule is logged to reports/data_quality_log.csv so the cleaning is auditable.

Usage:
    python src/clean.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC, REPORTS = ROOT / "data" / "raw", ROOT / "data" / "processed", ROOT / "reports"

FUNNEL = ["session_start", "product_view", "add_to_cart", "checkout_start", "payment_attempt", "purchase"]
STAGE_COLS = ["reached_session"] + FUNNEL[1:]   # column names in session_funnel

# Bot rule thresholds (behavioural — we do NOT rely on user_id names)
BOT_MIN_VIEWS = 15        # product views in one session
BOT_MAX_DURATION_S = 60   # ...all within one minute


class Log:
    """Collects one row per cleaning rule: what, why, rows affected."""
    def __init__(self):
        self.rows = []

    def add(self, table, check, issue, action, rows_affected):
        self.rows.append(dict(table=table, check=check, issue=issue, action=action,
                              rows_affected=int(rows_affected)))

    def frame(self):
        return pd.DataFrame(self.rows)


def load_raw():
    return (pd.read_csv(RAW / "sessions.csv.gz"),
            pd.read_csv(RAW / "events.csv.gz"),
            pd.read_csv(RAW / "orders.csv.gz"))


def parse_mixed_timestamps(col: pd.Series) -> pd.Series:
    """Events arrive as 'YYYY-MM-DD HH:MM:SS' or 'DD/MM/YYYY HH:MM:SS'."""
    iso = pd.to_datetime(col, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    dmy = pd.to_datetime(col, format="%d/%m/%Y %H:%M:%S", errors="coerce")
    return iso.fillna(dmy)


def clean_sessions(s: pd.DataFrame, log: Log) -> pd.DataFrame:
    s = s.copy()
    s["session_start"] = pd.to_datetime(s.session_start)

    raw_labels = s.channel.nunique()
    std = s.channel.str.strip().str.lower().str.replace(" ", "_")
    log.add("sessions", "channel labels", f"{raw_labels} raw labels for 7 channels (e.g. 'Paid Social' vs 'paid_social')",
            "lower-case + underscores", (std != s.channel).sum())
    s["channel"] = std

    n_null = s.device.isna().sum()
    log.add("sessions", "missing device", "device not captured (tracking script blocked)",
            "set to 'unknown' (kept — rows are still valid sessions)", n_null)
    s["device"] = s.device.fillna("unknown")

    dup = s.duplicated("session_id").sum()
    log.add("sessions", "duplicate session_id", "primary key must be unique", "drop duplicates", dup)
    return s.drop_duplicates("session_id")


def clean_events(ev: pd.DataFrame, log: Log) -> pd.DataFrame:
    ev = ev.copy()
    n_alt = ev.event_ts.str.contains("/").sum()
    ev["event_ts"] = parse_mixed_timestamps(ev.event_ts)
    log.add("events", "timestamp format", "two string formats in the export (ISO and DD/MM/YYYY)",
            "parse both formats explicitly", n_alt)
    bad_ts = ev.event_ts.isna().sum()
    log.add("events", "unparseable timestamps", "timestamp could not be parsed", "drop", bad_ts)
    ev = ev.dropna(subset=["event_ts"])

    dups = ev.duplicated().sum()
    log.add("events", "exact duplicate events", "tracking pixel fired twice", "drop exact duplicates", dups)
    ev = ev.drop_duplicates()
    return ev.sort_values(["session_id", "event_ts"]).reset_index(drop=True)


def detect_bots(s: pd.DataFrame, ev: pd.DataFrame, log: Log) -> set:
    agg = ev.groupby("session_id").agg(
        views=("event_name", lambda x: (x == "product_view").sum()),
        first=("event_ts", "min"), last=("event_ts", "max"))
    agg["duration_s"] = (agg["last"] - agg["first"]).dt.total_seconds()
    behav = set(agg.index[(agg.views >= BOT_MIN_VIEWS) & (agg.duration_s <= BOT_MAX_DURATION_S)])
    zero_load = set(s.session_id[s.page_load_ms <= 0])
    bots = behav | zero_load
    log.add("sessions", "bot / crawler traffic",
            f">= {BOT_MIN_VIEWS} product views within {BOT_MAX_DURATION_S}s, or page_load_ms = 0",
            "exclude from all analysis", len(bots))
    return bots


def clean_orders(o: pd.DataFrame, log: Log) -> pd.DataFrame:
    o = o.copy()
    o["order_ts"] = pd.to_datetime(o.order_ts)
    dup = o.duplicated().sum()
    log.add("orders", "duplicate order rows", "same order exported twice", "drop exact duplicates", dup)
    o = o.drop_duplicates()
    test = o.order_id.str.startswith("TEST") | (o.net_value_inr <= 1)
    log.add("orders", "QA test orders", "internal test orders (order_id 'TEST*', value Rs 1)", "drop", test.sum())
    o = o[~test]
    neg = (o.net_value_inr < 0).sum()
    log.add("orders", "negative order value", "refunds mixed into orders", "drop (none expected)", neg)
    return o[o.net_value_inr >= 0].reset_index(drop=True)


def build_session_funnel(s: pd.DataFrame, ev: pd.DataFrame, o: pd.DataFrame) -> pd.DataFrame:
    """One row per session with a 0/1 flag for each funnel stage it reached."""
    flags = (ev.assign(v=1).pivot_table(index="session_id", columns="event_name", values="v",
                                          aggfunc="max", fill_value=0)
               .reindex(columns=FUNNEL, fill_value=0)
               .rename(columns={"session_start": "reached_session"}))
    views = ev[ev.event_name == "product_view"].groupby("session_id").size().rename("n_product_views")
    rev = o.groupby("session_id").net_value_inr.sum().rename("revenue_inr")
    f = (s.set_index("session_id")
           .join(flags, how="left").join(views).join(rev)
           .fillna({**{c: 0 for c in STAGE_COLS}, "n_product_views": 0, "revenue_inr": 0.0}))
    f[STAGE_COLS + ["n_product_views"]] = f[STAGE_COLS + ["n_product_views"]].astype(int)
    f["reached_session"] = 1  # every session reaches stage 0 by definition
    return f.reset_index()


def validate(f: pd.DataFrame, o: pd.DataFrame, log: Log):
    """Funnel logic: a session cannot reach stage k without stage k-1."""
    stages = ["product_view", "add_to_cart", "checkout_start", "payment_attempt", "purchase"]
    for prev, nxt in zip(stages, stages[1:]):
        bad = ((f[nxt] == 1) & (f[prev] == 0)).sum()
        log.add("session_funnel", f"{nxt} without {prev}", "stage skipped", "assert = 0", bad)
        assert bad == 0, f"{bad} sessions reached {nxt} without {prev}"
    mismatch = (f.purchase.sum() - o.session_id.nunique())
    log.add("session_funnel", "purchase events vs orders", "every purchase event should have one order",
            "assert = 0", abs(mismatch))
    assert mismatch == 0


def run():
    PROC.mkdir(parents=True, exist_ok=True); REPORTS.mkdir(parents=True, exist_ok=True)
    log = Log()
    s_raw, ev_raw, o_raw = load_raw()

    s = clean_sessions(s_raw, log)
    ev = clean_events(ev_raw, log)
    o = clean_orders(o_raw, log)

    bots = detect_bots(s, ev, log)
    s = s[~s.session_id.isin(bots)].copy()
    ev = ev[ev.session_id.isin(s.session_id)].copy()
    o = o[o.session_id.isin(s.session_id)].copy()

    f = build_session_funnel(s, ev, o)
    validate(f, o, log)

    s.to_parquet(PROC / "sessions_clean.parquet", index=False)
    ev.to_parquet(PROC / "events_clean.parquet", index=False)
    o.to_parquet(PROC / "orders_clean.parquet", index=False)
    f.to_parquet(PROC / "session_funnel.parquet", index=False)

    lg = log.frame()
    lg.to_csv(REPORTS / "data_quality_log.csv", index=False)
    summary = pd.DataFrame({
        "table": ["sessions", "events", "orders"],
        "raw_rows": [len(s_raw), len(ev_raw), len(o_raw)],
        "clean_rows": [len(s), len(ev), len(o)],
    })
    summary["removed"] = summary.raw_rows - summary.clean_rows
    summary["removed_pct"] = (100 * summary.removed / summary.raw_rows).round(2)
    return lg, summary, f


if __name__ == "__main__":
    lg, summary, f = run()
    print(lg.to_string(index=False)); print(); print(summary.to_string(index=False))
