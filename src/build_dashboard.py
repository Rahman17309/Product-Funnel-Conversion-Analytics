"""
Build the interactive funnel dashboard: dashboard/index.html (a single file, opens in any browser).

Sections: KPI cards · funnel with segment filter · device & channel comparison ·
weekly trend · A/B test result · revenue opportunity sizing.

Usage:
    python src/clean.py              # if data/processed/ is missing
    python src/build_dashboard.py
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from statsmodels.stats.proportion import confint_proportions_2indep, proportions_ztest

ROOT = Path(__file__).resolve().parents[1]
PROC, OUT = ROOT / "data" / "processed", ROOT / "dashboard"
BLUE, LIGHT, GREY, RED, GREEN = "#2563eb", "#93c5fd", "#9ca3af", "#dc2626", "#16a34a"
STAGES = ["reached_session", "product_view", "add_to_cart", "checkout_start", "payment_attempt", "purchase"]
LABELS = ["Session", "Product view", "Add to cart", "Checkout start", "Payment attempt", "Purchase"]
LAYOUT = dict(template="plotly_white", font=dict(family="Inter, Segoe UI, sans-serif", size=13),
              margin=dict(l=10, r=10, t=50, b=10), title_x=0.01)


def load():
    f = pd.read_parquet(PROC / "session_funnel.parquet")
    o = pd.read_parquet(PROC / "orders_clean.parquet")
    return f, o


def kpis(f, o):
    return [
        ("Sessions", f"{len(f):,}", "Aug–Oct 2026, bots removed"),
        ("Orders", f"{int(f.purchase.sum()):,}", ""),
        ("Conversion rate", f"{100 * f.purchase.mean():.2f}%", "orders ÷ sessions"),
        ("Revenue", f"₹{o.net_value_inr.sum() / 1e5:.1f} L", "net of discounts"),
        ("Avg order value", f"₹{o.net_value_inr.mean():,.0f}", ""),
        ("Cart abandonment", f"{100 * (1 - f.purchase.sum() / f.add_to_cart.sum()):.1f}%", "carts that never buy"),
    ]


def funnel_fig(f):
    fig = go.Figure()
    segments = {"All sessions": f, "Mobile": f[f.device == "mobile"], "Desktop": f[f.device == "desktop"],
                "Tablet": f[f.device == "tablet"], "New visitors": f[f.is_returning == 0],
                "Returning visitors": f[f.is_returning == 1], "Paid social": f[f.channel == "paid_social"],
                "Slow pages (>3s)": f[f.page_load_ms > 3000]}
    for i, (name, d) in enumerate(segments.items()):
        fig.add_trace(go.Funnel(y=LABELS, x=d[STAGES].sum().values, name=name, visible=(i == 0),
                                texttemplate="%{value:,}<br>%{percentPrevious:.0%} of previous",
                                marker=dict(color=[BLUE, BLUE, RED, BLUE, BLUE, GREEN])))
    buttons = [dict(label=n, method="update",
                    args=[{"visible": [j == i for j in range(len(segments))]}, {"title": f"Conversion funnel: {n}"}])
               for i, n in enumerate(segments)]
    fig.update_layout(**LAYOUT, height=430, title="Conversion funnel: All sessions",
                      updatemenus=[dict(buttons=buttons, x=1, xanchor="right", y=1.15, yanchor="top")])
    return fig


def device_channel_fig(f):
    dev = f[f.device != "unknown"].groupby("device").agg(s=("session_id", "count"), c=("add_to_cart", "sum"),
                                                          k=("checkout_start", "sum"), p=("payment_attempt", "sum"),
                                                          o=("purchase", "sum")).reindex(["mobile", "desktop", "tablet"])
    ch = f.groupby("channel").agg(s=("session_id", "count"), o=("purchase", "sum"), r=("revenue_inr", "sum"))
    ch = ch.assign(cvr=100 * ch.o / ch.s, rps=ch.r / ch.s).sort_values("rps")
    fig = make_subplots(rows=1, cols=2, column_widths=[0.45, 0.55], horizontal_spacing=0.12,
                        subplot_titles=("Checkout steps by device (%)", "Revenue per session by channel (₹)"))
    for col, step, name in [(LIGHT, 100 * dev.k / dev.c, "Cart → checkout"), (BLUE, 100 * dev.p / dev.k, "Checkout → payment")]:
        fig.add_trace(go.Bar(x=dev.index.str.title(), y=step.round(1), name=name, marker_color=col,
                             text=step.round(1), textposition="outside"), 1, 1)
    fig.add_trace(go.Bar(y=ch.index.str.replace("_", " ").str.title(), x=ch.rps.round(1), orientation="h",
                         marker_color=[RED if c == "paid_social" else BLUE for c in ch.index], showlegend=False,
                         text=[f"₹{v:.0f} · CVR {c:.1f}%" for v, c in zip(ch.rps, ch.cvr)], textposition="outside",
                         hovertemplate="%{y}: ₹%{x:.1f} per session<extra></extra>"), 1, 2)
    fig.update_layout(**LAYOUT, height=400, barmode="group", legend=dict(orientation="h", y=-0.12))
    fig.update_yaxes(range=[0, 90], row=1, col=1); fig.update_xaxes(range=[0, ch.rps.max() * 1.6], row=1, col=2)
    return fig


def trend_fig(f):
    w = (f.assign(week=pd.to_datetime(f.session_start).dt.to_period("W-SUN").dt.start_time)
           .groupby("week").agg(s=("session_id", "count"), o=("purchase", "sum"), ret=("is_returning", "mean")))
    w = w.iloc[1:-1]  # drop partial first/last weeks
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=w.index, y=w.s, name="Sessions", marker_color="#e5e7eb"), secondary_y=False)
    fig.add_trace(go.Scatter(x=w.index, y=(100 * w.o / w.s).round(2), name="Conversion rate %", mode="lines+markers",
                             line=dict(color=BLUE, width=3)), secondary_y=True)
    fig.add_vline(x=pd.Timestamp("2026-09-15").timestamp() * 1000, line_dash="dash", line_color=RED,
                  annotation_text="A/B test starts", annotation_font_color=RED)
    fig.update_layout(**LAYOUT, height=380, title="Weekly sessions & conversion rate (part of the rise is more returning visitors, see notebook 03)",
                      legend=dict(orientation="h", y=-0.15))
    fig.update_yaxes(title_text="Sessions", secondary_y=False); fig.update_yaxes(title_text="CVR %", secondary_y=True, range=[0, 5], showgrid=False)
    return fig


def ab_fig(f):
    t = f[f.ab_group.isin(["control", "variant"])]
    rows = []
    for seg_name, d, metric in [("All sessions · conversion", t, "purchase"),
                                ("Mobile · checkout→payment", t[(t.device == "mobile") & (t.checkout_start == 1)], "payment_attempt"),
                                ("Desktop · checkout→payment", t[(t.device == "desktop") & (t.checkout_start == 1)], "payment_attempt")]:
        g = d.groupby("ab_group")[metric].agg(["sum", "count"])
        _, p = proportions_ztest(g["sum"][["variant", "control"]], g["count"][["variant", "control"]])
        lo, hi = confint_proportions_2indep(g["sum"]["variant"], g["count"]["variant"],
                                            g["sum"]["control"], g["count"]["control"], method="wald")
        rows.append(dict(seg=seg_name, control=100 * g["sum"]["control"] / g["count"]["control"],
                         variant=100 * g["sum"]["variant"] / g["count"]["variant"], lo=100 * lo, hi=100 * hi, p=p))
    r = pd.DataFrame(rows)
    r["diff"] = r.variant - r.control
    fig = go.Figure(go.Scatter(
        x=r["diff"], y=r.seg, mode="markers+text", marker=dict(size=14, color=[GREEN if p < 0.05 / 3 else GREY for p in r.p]),
        error_x=dict(type="data", symmetric=False, array=r.hi - r["diff"], arrayminus=r["diff"] - r.lo, thickness=2),
        text=[f"{c:.1f}% → {v:.1f}%  ({'p<0.001' if p < 0.001 else f'p={p:.3f}'})" for c, v, p in zip(r.control, r.variant, r.p)],
        textposition="top center", hovertemplate="%{y}<br>+%{x:.2f} pp<extra></extra>"))
    fig.add_vline(x=0, line_color="#111827")
    fig.update_layout(**LAYOUT, height=330, title="A/B test: one-page checkout lift (percentage points, 95% CI)",
                      xaxis_title="Variant − control (pp)", yaxis=dict(range=[2.5, -0.8]))
    return fig


def opportunity_fig():
    con = duckdb.connect()
    import os
    cwd = os.getcwd(); os.chdir(ROOT)
    try:
        con.execute((ROOT / "sql" / "00_setup_views.sql").read_text())
        opp = con.sql((ROOT / "sql" / "07_opportunity_sizing.sql").read_text()).df()
    finally:
        os.chdir(cwd)
    opp = opp.sort_values("extra_revenue_lakh_per_year")
    fig = go.Figure(go.Bar(x=opp.extra_revenue_lakh_per_year, y=opp.lever, orientation="h",
                           marker_color=[GREY, GREY, BLUE, RED][-len(opp):],
                           text=[f"₹{v:.1f} L / yr · {int(o)} orders/qtr" for v, o in
                                 zip(opp.extra_revenue_lakh_per_year, opp.extra_orders_per_quarter)],
                           textposition="outside", customdata=opp.assumption,
                           hovertemplate="%{y}<br>Assumption: %{customdata}<extra></extra>"))
    fig.update_layout(**LAYOUT, height=320, title="Revenue opportunity if we close half the gap (not additive)",
                      xaxis=dict(range=[0, opp.extra_revenue_lakh_per_year.max() * 1.5], title="₹ lakh per year"))
    return fig


def build():
    f, o = load()
    cards = "".join(f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div><div class="s">{s}</div></div>'
                    for k, v, s in kpis(f, o))
    figs = [funnel_fig(f), device_channel_fig(f), ab_fig(f), opportunity_fig(), trend_fig(f)]
    blocks = "".join(f'<section>{fig.to_html(full_html=False, include_plotlyjs=False, config={"displaylogo": False})}</section>'
                     for fig in figs)
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ShopNest · Funnel & Conversion Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
 body{{margin:0;background:#f8fafc;font-family:Inter,Segoe UI,Arial,sans-serif;color:#111827}}
 header{{padding:28px 32px 8px}} h1{{margin:0;font-size:26px}} header p{{margin:6px 0 0;color:#4b5563}}
 .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;padding:16px 32px}}
 .card{{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:14px 16px}}
 .k{{font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:.04em}} .v{{font-size:26px;font-weight:700;margin-top:4px}}
 .s{{font-size:12px;color:#9ca3af;min-height:14px}}
 main{{display:grid;grid-template-columns:1fr;gap:16px;padding:0 32px 24px}}
 section{{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:8px}}
 .insights{{background:#eff6ff;border:1px solid #bfdbfe;border-radius:12px;padding:14px 20px;margin:0 32px 16px}}
 .insights li{{margin:4px 0}} footer{{padding:8px 32px 28px;color:#6b7280;font-size:12px}}
</style></head><body>
<header><h1>🛒 ShopNest: Funnel & Conversion Dashboard</h1>
<p>1 Aug – 30 Oct 2026 · 80,000 human sessions · synthetic data for a portfolio project</p></header>
<div class="cards">{cards}</div>
<div class="insights"><b>Key takeaways</b><ul>
<li><b>Mobile checkout is the biggest fixable leak:</b> mobile cart→checkout 50% vs 65% on desktop; worth ~₹26 L/year if we close half the gap.</li>
<li><b>The one-page checkout works:</b> +0.61 pp conversion (+17%, p = 0.001); mobile checkout→payment +8.4 pp. Recommendation: roll out.</li>
<li><b>Slow pages (&gt;3s) halve conversion</b> on mobile and desktop alike; a third of mobile sessions are slow.</li>
<li><b>Paid social</b> brings 22% of traffic but the lowest revenue per session; fix landing pages / targeting.</li>
</ul></div>
<main>{blocks}</main>
<footer>Built with Python, DuckDB SQL and Plotly · github.com/Rahman17309/product-funnel-conversion-analytics</footer>
</body></html>"""
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print(f"Dashboard written to {OUT / 'index.html'} ({(OUT / 'index.html').stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    build()
