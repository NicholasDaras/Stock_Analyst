#!/usr/bin/env python3
from __future__ import annotations

"""
Rule #1 Investing Dashboard
Run with: streamlit run dashboard.py
"""

import json
import os
import streamlit as st

st.set_page_config(page_title="Rule #1", page_icon="$", layout="wide")

import pandas as pd
import altair as alt
from rule1 import full_analysis, get_news, pass_fail
from portfolio import (
    get_portfolio, add_holding, remove_holding,
    add_to_watchlist, remove_from_watchlist,
)

# Optional integrations — degrade gracefully if missing
_fred_available = False
_edgar_available = False

try:
    from fred_data import fetch_macro_snapshot, compute_fear_greed, suggest_marr
    _fred_available = True
except ImportError:
    pass

try:
    from edgar_data import get_insider_trading
    _edgar_available = True
except ImportError:
    pass


# ── Authentication ────────────────────────────────────────────────────────────

def check_password() -> bool:
    """Simple password gate using Streamlit secrets."""
    if "password" not in st.secrets:
        return True  # No password configured, skip auth

    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        '<div style="max-width:400px; margin:8rem auto; text-align:center;">'
        '<h2 style="color:#e6edf3;">Rule #1 Dashboard</h2>'
        '<p style="color:#7d8590;">Enter password to continue</p></div>',
        unsafe_allow_html=True,
    )
    with st.container():
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            pwd = st.text_input("Password", type="password", label_visibility="collapsed")
            if st.button("Login", type="primary", width="stretch"):
                if pwd == st.secrets["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Incorrect password")
    return False


if not check_password():
    st.stop()


# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* ── Global ── */
    .stApp { background-color: #0e1117; }
    section[data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #21262d; }

    /* ── Header bar ── */
    .dash-header {
        background: linear-gradient(135deg, #161b22 0%, #0e1117 100%);
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1.5rem;
    }
    .dash-header h1 {
        color: #e6edf3;
        font-size: 1.5rem;
        font-weight: 600;
        margin: 0;
        letter-spacing: -0.02em;
    }
    .dash-header .subtitle {
        color: #7d8590;
        font-size: 0.85rem;
        margin-top: 0.2rem;
    }

    /* ── Metric cards ── */
    .metric-row { display: flex; gap: 0.75rem; margin-bottom: 1rem; }
    .metric-card {
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        flex: 1;
        min-width: 0;
    }
    .metric-card .label { color: #7d8590; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.3rem; }
    .metric-card .value { color: #e6edf3; font-size: 1.4rem; font-weight: 600; }
    .metric-card .delta-pos { color: #3fb950; font-size: 0.85rem; }
    .metric-card .delta-neg { color: #f85149; font-size: 0.85rem; }

    /* ── Verdict badges ── */
    .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.03em; }
    .badge-buy { background: #0d2818; color: #3fb950; border: 1px solid #238636; }
    .badge-watch { background: #2a1e00; color: #d29922; border: 1px solid #9e6a03; }
    .badge-over { background: #2d0a0a; color: #f85149; border: 1px solid #da3633; }
    .badge-unknown { background: #1c1c1c; color: #7d8590; border: 1px solid #30363d; }

    /* ── Section dividers ── */
    .section-title {
        color: #e6edf3;
        font-size: 1rem;
        font-weight: 600;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #21262d;
        margin: 1.5rem 0 1rem 0;
    }

    /* ── Tables ── */
    .stDataFrame { border-radius: 8px; overflow: hidden; }

    /* ── News cards ── */
    .news-item {
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 6px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
    }
    .news-item a { color: #58a6ff; text-decoration: none; font-weight: 500; }
    .news-item a:hover { text-decoration: underline; }
    .news-item .news-meta { color: #7d8590; font-size: 0.75rem; margin-top: 0.2rem; }

    /* ── Sidebar tweaks ── */
    section[data-testid="stSidebar"] .stMarkdown h1 { font-size: 1.1rem; }
    section[data-testid="stSidebar"] .stButton > button {
        background: #21262d; color: #e6edf3; border: 1px solid #30363d;
        font-size: 0.75rem; padding: 0.2rem 0.5rem;
    }
    section[data-testid="stSidebar"] .stButton > button:hover { background: #30363d; }

    /* ── Gauge ── */
    .gauge-container { text-align: center; padding: 1rem; }
    .gauge-score { font-size: 3rem; font-weight: 700; color: #e6edf3; }
    .gauge-label { font-size: 1.1rem; font-weight: 600; margin-top: 0.2rem; }
    .gauge-desc { color: #7d8590; font-size: 0.85rem; margin-top: 0.3rem; }
    .gauge-fear { color: #3fb950; }
    .gauge-cautious { color: #d29922; }
    .gauge-neutral { color: #7d8590; }
    .gauge-optimistic { color: #58a6ff; }
    .gauge-greed { color: #f85149; }

    /* ── Signal rows ── */
    .signal-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 0.6rem 0; border-bottom: 1px solid #21262d;
    }
    .signal-name { color: #e6edf3; font-weight: 500; }
    .signal-status { font-weight: 600; font-size: 0.85rem; }
    .signal-desc { color: #7d8590; font-size: 0.75rem; }

    /* ── Insider cards ── */
    .insider-buy { color: #3fb950; }
    .insider-sell { color: #f85149; }
    .insider-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 0.5rem 0; border-bottom: 1px solid #161b22;
        font-size: 0.85rem;
    }
    .insider-row .name { color: #e6edf3; font-weight: 500; }
    .insider-row .title { color: #7d8590; font-size: 0.75rem; }
    .insider-row .date { color: #7d8590; }

    /* ── Hide streamlit defaults ── */
    #MainMenu { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent; }
    footer { visibility: hidden; }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] { gap: 0; border-bottom: 1px solid #21262d; }
    .stTabs [data-baseweb="tab"] {
        background: transparent; color: #7d8590; border: none;
        padding: 0.6rem 1.2rem; font-weight: 500;
    }
    .stTabs [aria-selected="true"] { color: #e6edf3; border-bottom: 2px solid #58a6ff; }
</style>
""", unsafe_allow_html=True)


# ── Caching ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def cached_analysis(ticker: str) -> dict | None:
    return full_analysis(ticker)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_news(ticker: str) -> list[dict]:
    return get_news(ticker, count=5)


@st.cache_data(ttl=7200, show_spinner=False)
def cached_macro() -> dict | None:
    if not _fred_available:
        return None
    try:
        key = st.secrets.get("fred_api_key")
        if not key:
            return None
        return fetch_macro_snapshot(api_key=key)
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def cached_insider(ticker: str) -> dict | None:
    if not _edgar_available:
        return None
    try:
        return get_insider_trading(ticker)
    except Exception:
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def pct(val):
    if val is None:
        return "N/A"
    return f"{val * 100:.1f}%"


def dollar(val):
    if val is None:
        return "N/A"
    return f"${val:,.2f}"


def verdict_badge(v: str) -> str:
    cls = {"BUY": "badge-buy", "WATCHLIST": "badge-watch",
           "OVERPRICED": "badge-over"}.get(v, "badge-unknown")
    return f'<span class="badge {cls}">{v}</span>'


def metric_card(label: str, value: str, delta: str = None, delta_pos: bool = True) -> str:
    delta_html = ""
    if delta:
        cls = "delta-pos" if delta_pos else "delta-neg"
        delta_html = f'<div class="{cls}">{delta}</div>'
    return (f'<div class="metric-card">'
            f'<div class="label">{label}</div>'
            f'<div class="value">{value}</div>'
            f'{delta_html}</div>')


def metric_row(cards: list[str]) -> str:
    return f'<div class="metric-row">{"".join(cards)}</div>'


def best_rate(rates: dict) -> float | None:
    for p in ["10yr", "5yr", "3yr", "1yr"]:
        if rates.get(p) is not None:
            return rates[p]
    return None


def big5_row(analysis: dict) -> dict:
    big5 = analysis["big5"]
    sticker = analysis["sticker"]
    return {
        "Ticker": analysis["ticker"],
        "Name": analysis["name"],
        "Price": analysis["price"],
        "ROIC": big5["ROIC"]["latest"],
        "Sales Gr.": best_rate(big5["Sales"]["rates"]),
        "EPS Gr.": best_rate(big5["EPS"]["rates"]),
        "BVPS Gr.": best_rate(big5["Equity (BVPS)"]["rates"]),
        "FCF Gr.": best_rate(big5["Free Cash Flow"]["rates"]),
        "Big 5": analysis["big5_score"],
        "Sticker": sticker["sticker_price"],
        "MOS": sticker["mos_price"],
        "Verdict": analysis["verdict"],
    }


def render_big5_table(rows: list[dict]):
    df = pd.DataFrame(rows)
    if df.empty:
        return
    fmt_cols = {
        "Price": dollar, "ROIC": pct, "Sales Gr.": pct,
        "EPS Gr.": pct, "BVPS Gr.": pct, "FCF Gr.": pct,
        "Sticker": dollar, "MOS": dollar,
    }
    for col, fn in fmt_cols.items():
        if col in df.columns:
            df[col] = df[col].apply(fn)
    st.dataframe(df, width="stretch", hide_index=True)


def render_price_vs_value_chart(analysis: dict):
    """Bar chart: current price vs sticker vs MOS."""
    sticker = analysis["sticker"]
    price = analysis["price"]
    if not price or not sticker["sticker_price"]:
        return

    data = pd.DataFrame([
        {"Metric": "MOS Price", "Value": sticker["mos_price"] or 0, "order": 0},
        {"Metric": "Sticker Price", "Value": sticker["sticker_price"] or 0, "order": 1},
        {"Metric": "Current Price", "Value": price, "order": 2},
    ])

    color_scale = alt.Scale(
        domain=["MOS Price", "Sticker Price", "Current Price"],
        range=["#3fb950", "#58a6ff", "#f0f6fc"]
    )

    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Metric:N", sort=alt.EncodingSortField(field="order"), axis=alt.Axis(
                labelColor="#7d8590", titleColor="#7d8590", gridColor="#21262d")),
            y=alt.Y("Value:Q", axis=alt.Axis(
                labelColor="#7d8590", titleColor="#7d8590", gridColor="#21262d",
                format="$,.0f")),
            color=alt.Color("Metric:N", scale=color_scale, legend=None),
            tooltip=[alt.Tooltip("Metric:N"), alt.Tooltip("Value:Q", format="$,.2f")],
        )
        .properties(height=220)
        .configure(background="transparent")
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(chart, width="stretch")


def render_big5_chart(analysis: dict):
    """Horizontal bar chart of Big 5 rates vs 10% threshold."""
    big5 = analysis["big5"]

    rows = []
    roic = big5["ROIC"]["latest"]
    if roic is not None:
        rows.append({"Metric": "ROIC", "Rate": roic * 100})
    for label in ["Sales", "EPS", "Equity (BVPS)", "Free Cash Flow"]:
        rate = best_rate(big5[label]["rates"])
        if rate is not None:
            rows.append({"Metric": label, "Rate": rate * 100})

    if not rows:
        return

    data = pd.DataFrame(rows)

    bars = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
        .encode(
            y=alt.Y("Metric:N", sort=[r["Metric"] for r in rows], axis=alt.Axis(
                labelColor="#e6edf3", titleColor="#7d8590")),
            x=alt.X("Rate:Q", axis=alt.Axis(
                labelColor="#7d8590", titleColor="#7d8590", gridColor="#21262d",
                format=".0f"), title="Rate (%)"),
            color=alt.condition(
                alt.datum.Rate >= 10,
                alt.value("#3fb950"),
                alt.value("#f85149"),
            ),
            tooltip=[alt.Tooltip("Metric:N"), alt.Tooltip("Rate:Q", format=".1f")],
        )
    )

    rule = (
        alt.Chart(pd.DataFrame([{"threshold": 10}]))
        .mark_rule(color="#d29922", strokeDash=[4, 4], strokeWidth=1.5)
        .encode(x="threshold:Q")
    )

    chart = (
        (bars + rule)
        .properties(height=180)
        .configure(background="transparent")
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(chart, width="stretch")


def render_detail(analysis: dict):
    """Render detailed Rule #1 analysis for a single stock."""
    big5 = analysis["big5"]
    sticker = analysis["sticker"]

    # Header with verdict
    st.markdown(
        f'<div style="display:flex; align-items:center; gap:0.8rem; margin-bottom:1rem;">'
        f'<span style="color:#e6edf3; font-size:1.3rem; font-weight:600;">'
        f'{analysis["name"]} ({analysis["ticker"]})</span>'
        f'{verdict_badge(analysis["verdict"])}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Key metrics
    price = analysis["price"]
    cards = [
        metric_card("Price", dollar(price)),
        metric_card("Sticker Price", dollar(sticker["sticker_price"])),
        metric_card("MOS Price", dollar(sticker["mos_price"])),
        metric_card("Big 5 Score", analysis["big5_score"]),
    ]
    debt = analysis["debt_payoff"]
    if debt is not None:
        status = "PASS" if debt <= 3 else ("OK" if debt <= 5 else "FAIL")
        cards.append(metric_card("Debt Payoff", f"{debt:.1f}yr", status))
    st.markdown(metric_row(cards), unsafe_allow_html=True)

    # Charts side by side
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.markdown('<div class="section-title">Price vs Value</div>', unsafe_allow_html=True)
        render_price_vs_value_chart(analysis)
    with col_chart2:
        st.markdown('<div class="section-title">Big 5 Rates (10% target)</div>', unsafe_allow_html=True)
        render_big5_chart(analysis)

    # Big 5 detail table
    st.markdown('<div class="section-title">Big 5 Numbers</div>', unsafe_allow_html=True)
    periods = ["10yr", "5yr", "3yr", "1yr"]
    rows = []
    roic_rates = big5["ROIC"]["rates"]
    rows.append({"Metric": "ROIC (avg)", **{p: pct(roic_rates.get(p)) for p in periods},
                 "Pass?": pass_fail(big5["ROIC"]["latest"])})
    for label in ["Sales", "EPS", "Equity (BVPS)", "Free Cash Flow"]:
        rates = big5[label]["rates"]
        b = best_rate(rates)
        rows.append({"Metric": label, **{p: pct(rates.get(p)) for p in periods},
                     "Pass?": pass_fail(b)})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    # Sticker price details
    with st.expander("Sticker Price Breakdown"):
        c1, c2 = st.columns(2)
        c1.markdown(f"""
- **Current EPS:** {dollar(sticker['current_eps'])}
- **Growth Rate Used:** {pct(sticker['growth_rate'])}
- **Analyst Estimate:** {pct(sticker['analyst_growth'])}
- **Hist. Equity Growth:** {pct(sticker['hist_equity_growth'])}
- **Hist. EPS Growth:** {pct(sticker['hist_eps_growth'])}
""")
        current_pe_str = f"{sticker['current_pe']:.1f}" if sticker['current_pe'] else "N/A"
        future_pe_str = f"{sticker['future_pe']:.1f}" if sticker['future_pe'] else "N/A"
        c2.markdown(f"""
- **Current PE:** {current_pe_str}
- **Future PE:** {future_pe_str}
- **MARR:** {pct(sticker['marr'])}
- **Future EPS (10yr):** {dollar(sticker['future_eps'])}
- **Future Price:** {dollar(sticker['future_price'])}
""")

    # Insider trading (SEC EDGAR) — skip for ETFs/funds (no Form 4 data)
    if _edgar_available and analysis.get("sector", "N/A") != "N/A":
        with st.expander("Insider Trading (SEC Form 4)"):
            render_insider_data(analysis["ticker"])


def render_news_card(art: dict):
    pub = f" &middot; {art['publisher']}" if art.get("publisher") else ""
    date = ""
    if art.get("published"):
        date = f" &middot; {art['published'][:10]}"
    link = art.get("link", "")
    title = art.get("title", "No title")
    if link:
        title_html = f'<a href="{link}" target="_blank">{title}</a>'
    else:
        title_html = title
    st.markdown(
        f'<div class="news-item">{title_html}<div class="news-meta">{pub}{date}</div></div>',
        unsafe_allow_html=True,
    )


def render_insider_data(ticker: str):
    """Render insider trading data from SEC EDGAR Form 4 filings."""
    insider = cached_insider(ticker)

    if not insider or not insider.get("summary"):
        st.markdown('<div style="color:#7d8590;">No insider trading data available.</div>',
                    unsafe_allow_html=True)
        return

    s = insider["summary"]
    if s["total_buys"] + s["total_sells"] == 0:
        st.markdown('<div style="color:#7d8590;">No insider buys or sells in the last '
                    f'{s["period_months"]} months.</div>', unsafe_allow_html=True)
        return

    sentiment_cls = {"BULLISH": "insider-buy", "BEARISH": "insider-sell"}.get(s["sentiment"], "")
    st.markdown(f'<div class="section-title">Insider Trading ({s["period_months"]}mo) '
                f'<span style="font-size:0.75rem; color:#7d8590;">via SEC EDGAR Form 4</span></div>',
                unsafe_allow_html=True)

    cards = [
        metric_card("Insider Sentiment", f'<span class="{sentiment_cls}">{s["sentiment"]}</span>'),
        metric_card("Buys", str(s["total_buys"]), f"${s['buy_value']:,.0f}" if s["buy_value"] else None),
        metric_card("Sells", str(s["total_sells"]), f"${s['sell_value']:,.0f}" if s["sell_value"] else None, delta_pos=False),
        metric_card("Net Value", f"${s['net_value']:,.0f}", delta_pos=s["net_value"] >= 0),
    ]
    st.markdown(metric_row(cards), unsafe_allow_html=True)

    if insider.get("transactions"):
        rows = []
        for t in insider["transactions"][:10]:
            rows.append({
                "Date": t["date"],
                "Name": t["name"],
                "Title": t["title"],
                "Type": t["type"],
                "Shares": f"{t['shares']:,.0f}" if t["shares"] else "",
                "Price": f"${t['price']:,.2f}" if t["price"] else "",
                "Value": f"${t['value']:,.0f}" if t["value"] else "",
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_macro_tab():
    """Render the Market Conditions tab with FRED data."""
    if not _fred_available:
        st.markdown(
            '<div style="color:#7d8590; text-align:center; padding:3rem;">'
            'FRED integration not available. Install fredapi: <code>pip install fredapi</code><br>'
            'Then add <code>fred_api_key = "YOUR_KEY"</code> to .streamlit/secrets.toml</div>',
            unsafe_allow_html=True)
        return

    macro = cached_macro()
    if macro is None:
        st.markdown(
            '<div style="color:#7d8590; text-align:center; padding:3rem;">'
            'Add <code>fred_api_key = "YOUR_KEY"</code> to .streamlit/secrets.toml<br>'
            'Get a free key at <a href="https://fred.stlouisfed.org/docs/api/api_key.html" '
            'style="color:#58a6ff;">fred.stlouisfed.org</a></div>',
            unsafe_allow_html=True)
        return

    # Fear/Greed gauge
    fg = compute_fear_greed(macro)
    gauge_cls = f"gauge-{fg['label'].lower()}"

    st.markdown(
        f'<div class="gauge-container">'
        f'<div class="gauge-score">{fg["score"]}</div>'
        f'<div class="gauge-label {gauge_cls}">{fg["label"]}</div>'
        f'<div class="gauge-desc">{fg["description"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Suggested MARR
    suggested = suggest_marr(macro)
    if suggested != 0.15:
        st.markdown(
            f'<div style="background:#161b22; border:1px solid #21262d; border-radius:6px; '
            f'padding:0.8rem 1rem; margin:0.5rem 0 1rem 0; color:#58a6ff; text-align:center;">'
            f'Suggested MARR based on current rates: <strong>{suggested*100:.1f}%</strong> '
            f'(default 15%)</div>',
            unsafe_allow_html=True,
        )

    # Signals detail
    st.markdown('<div class="section-title">Market Signals</div>', unsafe_allow_html=True)
    for name, status, desc in fg["signals"]:
        status_color = {"INVERTED": "#f85149", "HIGH": "#f85149", "RESTRICTIVE": "#f85149",
                        "PESSIMISTIC": "#3fb950",  # contrarian
                        "FLAT": "#d29922", "ELEVATED": "#d29922", "CAUTIOUS": "#d29922",
                        "NORMAL": "#7d8590", "NEUTRAL": "#7d8590", "MODERATE": "#7d8590",
                        "STEEP": "#58a6ff", "LOW": "#58a6ff", "ACCOMMODATIVE": "#3fb950",
                        "OPTIMISTIC": "#58a6ff"}.get(status, "#7d8590")
        st.markdown(
            f'<div class="signal-row">'
            f'<div><div class="signal-name">{name}</div><div class="signal-desc">{desc}</div></div>'
            f'<div class="signal-status" style="color:{status_color};">{status}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Key indicators table
    st.markdown('<div class="section-title">Key Indicators</div>', unsafe_allow_html=True)

    indicators = [
        ("fed_funds", "pct"), ("treasury_10y", "pct"), ("treasury_2y", "pct"),
        ("yield_spread", "pct"), ("unemployment", "pct"), ("consumer_sentiment", "num"),
    ]

    cards = []
    for key, _ in indicators:
        data = macro.get(key, {})
        if data.get("value") is not None:
            val = data["value"]
            prev = data.get("prev_value")
            if data["fmt"] == "pct":
                val_str = f"{val:.2f}%"
            elif data["fmt"] == "dollar":
                val_str = f"${val:,.0f}B"
            else:
                val_str = f"{val:,.1f}"

            delta = None
            delta_pos = True
            if prev is not None:
                diff = val - prev
                delta = f"{diff:+.2f}" if data["fmt"] == "pct" else f"{diff:+,.1f}"
                delta_pos = diff >= 0

            cards.append(metric_card(data["label"], val_str, delta, delta_pos))

    if cards:
        # Render in rows of 3
        for i in range(0, len(cards), 3):
            st.markdown(metric_row(cards[i:i+3]), unsafe_allow_html=True)

    # Sparkline charts for key series
    st.markdown('<div class="section-title">Trends (2 Years)</div>', unsafe_allow_html=True)

    chart_keys = ["treasury_10y", "yield_spread", "unemployment", "consumer_sentiment"]
    cols = st.columns(2)
    for i, key in enumerate(chart_keys):
        data = macro.get(key, {})
        history = data.get("history", [])
        if not history:
            continue

        chart_df = pd.DataFrame(history, columns=["Date", "Value"])
        chart_df["Date"] = pd.to_datetime(chart_df["Date"])

        chart = (
            alt.Chart(chart_df)
            .mark_area(
                line={"color": "#58a6ff", "strokeWidth": 1.5},
                color=alt.Gradient(
                    gradient="linear",
                    stops=[
                        alt.GradientStop(color="rgba(88,166,255,0.3)", offset=0),
                        alt.GradientStop(color="rgba(88,166,255,0.01)", offset=1),
                    ],
                    x1=1, x2=1, y1=1, y2=0,
                ),
            )
            .encode(
                x=alt.X("Date:T", axis=alt.Axis(labelColor="#7d8590", gridColor="#21262d",
                         format="%b '%y"), title=None),
                y=alt.Y("Value:Q", axis=alt.Axis(labelColor="#7d8590", gridColor="#21262d"),
                         title=data.get("label", key)),
                tooltip=[alt.Tooltip("Date:T", format="%Y-%m-%d"), alt.Tooltip("Value:Q", format=".2f")],
            )
            .properties(height=160)
            .configure(background="transparent")
            .configure_view(strokeWidth=0)
        )

        with cols[i % 2]:
            st.altair_chart(chart, width="stretch")


# ── Sidebar: Portfolio Management ─────────────────────────────────────────────

st.sidebar.markdown(
    '<div style="color:#e6edf3; font-size:1.1rem; font-weight:600; margin-bottom:0.8rem;">'
    'Portfolio Manager</div>',
    unsafe_allow_html=True,
)

with st.sidebar.expander("Add Holding", expanded=False):
    with st.form("add_holding"):
        t = st.text_input("Ticker", placeholder="AAPL")
        c1, c2 = st.columns(2)
        s = c1.number_input("Shares", min_value=0.0, step=1.0, value=0.0)
        c_cost = c2.number_input("Avg Cost ($)", min_value=0.0, step=0.01, value=0.0)
        if st.form_submit_button("Add") and t:
            add_holding(t.strip(), s, c_cost)
            st.cache_data.clear()
            st.rerun()

with st.sidebar.expander("Add to Watchlist", expanded=False):
    with st.form("add_watch"):
        wt = st.text_input("Ticker", placeholder="MSFT", key="watch_ticker")
        if st.form_submit_button("Add") and wt:
            add_to_watchlist(wt.strip())
            st.cache_data.clear()
            st.rerun()

portfolio = get_portfolio()

if portfolio["holdings"]:
    st.sidebar.markdown('<div style="color:#7d8590; font-size:0.75rem; text-transform:uppercase; '
                        'letter-spacing:0.05em; margin-top:1rem;">Holdings</div>',
                        unsafe_allow_html=True)
    for tk, info in portfolio["holdings"].items():
        col1, col2 = st.sidebar.columns([3, 1])
        col1.markdown(f"**{tk}** <span style='color:#7d8590'>{info['shares']:.0f} @ ${info['avg_cost']:.2f}</span>",
                      unsafe_allow_html=True)
        if col2.button("X", key=f"rm_{tk}"):
            remove_holding(tk)
            st.cache_data.clear()
            st.rerun()

if portfolio["watchlist"]:
    st.sidebar.markdown('<div style="color:#7d8590; font-size:0.75rem; text-transform:uppercase; '
                        'letter-spacing:0.05em; margin-top:1rem;">Watchlist</div>',
                        unsafe_allow_html=True)
    for tk in portfolio["watchlist"]:
        col1, col2 = st.sidebar.columns([3, 1])
        col1.write(tk)
        if col2.button("X", key=f"rmw_{tk}"):
            remove_from_watchlist(tk)
            st.cache_data.clear()
            st.rerun()


# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="dash-header">
    <h1>Rule #1 Dashboard</h1>
    <div class="subtitle">Phil Town's investing methodology &mdash; find wonderful companies at attractive prices</div>
</div>
""", unsafe_allow_html=True)


# ── Main Content ──────────────────────────────────────────────────────────────

tab_portfolio, tab_screener, tab_macro, tab_news, tab_lookup = st.tabs(
    ["PORTFOLIO", "SCREENER", "MARKET", "NEWS", "LOOKUP"]
)


# ── Tab 1: Portfolio ──────────────────────────────────────────────────────────

with tab_portfolio:
  try:
    if not portfolio["holdings"]:
        st.markdown(
            '<div style="color:#7d8590; text-align:center; padding:3rem;">'
            'No holdings yet. Add stocks using the sidebar.</div>',
            unsafe_allow_html=True,
        )
    else:
        tickers = list(portfolio["holdings"].keys())
        analyses = {}
        progress = st.progress(0, text="Analyzing portfolio...")
        for i, tk in enumerate(tickers):
            progress.progress((i + 1) / len(tickers), text=f"Analyzing {tk}...")
            result = cached_analysis(tk)
            if result:
                analyses[tk] = result
        progress.empty()

        if analyses:
            # Portfolio totals
            total_value = 0
            total_cost = 0
            for tk, a in analyses.items():
                h = portfolio["holdings"].get(tk, {})
                if a["price"] and h.get("shares"):
                    total_value += a["price"] * h["shares"]
                    total_cost += h["avg_cost"] * h["shares"]

            if total_cost > 0:
                total_gain = (total_value - total_cost) / total_cost * 100
                cards = [
                    metric_card("Total Value", dollar(total_value)),
                    metric_card("Total Cost Basis", dollar(total_cost)),
                    metric_card("Total Return", f"{total_gain:+.1f}%",
                                delta=f"{dollar(total_value - total_cost)}",
                                delta_pos=total_gain >= 0),
                    metric_card("Positions", str(len(analyses))),
                ]
                st.markdown(metric_row(cards), unsafe_allow_html=True)

            # Summary table
            st.markdown('<div class="section-title">Holdings Overview</div>', unsafe_allow_html=True)
            rows = []
            for tk, a in analyses.items():
                row = big5_row(a)
                holding = portfolio["holdings"].get(tk, {})
                row["Shares"] = holding.get("shares", 0)
                row["Avg Cost"] = dollar(holding.get("avg_cost", 0))
                if a["price"] and holding.get("shares"):
                    row["Value"] = dollar(a["price"] * holding["shares"])
                    gain = (a["price"] - holding["avg_cost"]) / holding["avg_cost"] * 100 if holding["avg_cost"] else 0
                    row["Gain"] = f"{gain:+.1f}%"
                else:
                    row["Value"] = "N/A"
                    row["Gain"] = "N/A"
                rows.append(row)

            df = pd.DataFrame(rows)
            fmt_cols = {
                "Price": dollar, "ROIC": pct, "Sales Gr.": pct,
                "EPS Gr.": pct, "BVPS Gr.": pct, "FCF Gr.": pct,
                "Sticker": dollar, "MOS": dollar,
            }
            for col, fn in fmt_cols.items():
                if col in df.columns:
                    df[col] = df[col].apply(fn)
            cols = ["Ticker", "Name", "Shares", "Avg Cost", "Price", "Value", "Gain",
                    "Big 5", "Verdict", "ROIC", "Sales Gr.", "EPS Gr.", "BVPS Gr.", "FCF Gr.",
                    "Sticker", "MOS"]
            cols = [c for c in cols if c in df.columns]
            st.dataframe(df[cols], width="stretch", hide_index=True)

            # Detail per stock
            st.markdown('<div class="section-title">Detailed Analysis</div>', unsafe_allow_html=True)
            selected = st.selectbox("Select stock", list(analyses.keys()),
                                    label_visibility="collapsed")
            if selected:
                render_detail(analyses[selected])
  except Exception as e:
    st.error(f"Portfolio tab error: {e}")


# ── Tab 2: Screener ───────────────────────────────────────────────────────────

with tab_screener:
  try:
    # ── Load cached scan results ──
    scan_data = None
    scan_file = os.path.join(os.path.dirname(__file__), "scan_results.json")
    if os.path.exists(scan_file):
        with open(scan_file, "r") as f:
            scan_data = json.load(f)

    if scan_data and scan_data.get("results"):
        scan_date = scan_data.get("scan_date", "Unknown")[:16].replace("T", " ")
        total_scanned = len(scan_data["results"])
        all_results = list(scan_data["results"].values())

        # Sort by verdict
        order = {"BUY": 0, "WATCHLIST": 1, "OVERPRICED": 2, "UNKNOWN": 3}
        all_results.sort(key=lambda r: (order.get(r["verdict"], 3), r.get("ticker", "")))

        buys = [r for r in all_results if r["verdict"] == "BUY"]
        watches = [r for r in all_results if r["verdict"] == "WATCHLIST"]

        # Scan info header
        cards = [
            metric_card("Last Scan", scan_date),
            metric_card("Stocks Scanned", str(total_scanned)),
            metric_card("Buy Signals", str(len(buys))),
            metric_card("Watchlist", str(len(watches))),
        ]
        st.markdown(metric_row(cards), unsafe_allow_html=True)

        if buys:
            st.markdown(
                f'<div style="background:#0d2818; border:1px solid #238636; border-radius:6px; '
                f'padding:0.8rem 1rem; margin:1rem 0 0.5rem 0; color:#3fb950; font-weight:500;">'
                f'Potential Buys: {", ".join(r["ticker"] for r in buys)}</div>',
                unsafe_allow_html=True,
            )
        if watches:
            st.markdown(
                f'<div style="background:#2a1e00; border:1px solid #9e6a03; border-radius:6px; '
                f'padding:0.8rem 1rem; margin-bottom:0.5rem; color:#d29922; font-weight:500;">'
                f'Near Buy Zone: {", ".join(r["ticker"] for r in watches)}</div>',
                unsafe_allow_html=True,
            )

        # Filter controls
        filter_col1, filter_col2 = st.columns([1, 2])
        verdict_filter = filter_col1.multiselect(
            "Filter by verdict",
            options=["BUY", "WATCHLIST", "OVERPRICED", "UNKNOWN"],
            default=["BUY", "WATCHLIST"],
        )
        search = filter_col2.text_input("Search ticker or name", placeholder="e.g. AAPL or Apple")

        filtered = [r for r in all_results if r["verdict"] in verdict_filter]
        if search:
            search_lower = search.lower()
            filtered = [r for r in filtered
                        if search_lower in r["ticker"].lower() or search_lower in r.get("name", "").lower()]

        if filtered:
            render_big5_table([big5_row(a) for a in filtered])

            for a in filtered:
                with st.expander(f"{a['ticker']} — {a.get('name', '')} ({a['verdict']})"):
                    render_detail(a)
        else:
            st.markdown('<div style="color:#7d8590; padding:2rem; text-align:center;">'
                        'No stocks match your filters.</div>', unsafe_allow_html=True)

    else:
        # No cached results — fallback to manual screener
        st.markdown(
            '<div style="color:#7d8590; margin-bottom:1rem;">'
            'No scan results yet. Run the nightly scanner first:<br>'
            '<code>python3 scanner.py</code><br><br>'
            'Or screen individual tickers below.</div>',
            unsafe_allow_html=True,
        )

        DEFAULT_SCREEN = [
            "MSFT", "GOOG", "AMZN", "NVDA", "META", "BRK-B", "JNJ", "V", "MA",
            "PG", "HD", "COST", "KO", "PEP", "MRK", "ABBV", "TMO", "ACN",
            "LLY", "UNH", "CRM", "ADBE", "ORCL", "NFLX", "INTC", "AMD",
        ]
        watchlist = portfolio.get("watchlist", [])
        screen_tickers = list(dict.fromkeys(watchlist + DEFAULT_SCREEN))

        selected_tickers = st.multiselect(
            "Tickers to screen",
            options=screen_tickers,
            default=watchlist if watchlist else screen_tickers[:10],
        )

        if st.button("Run Screener", type="primary") and selected_tickers:
            results = []
            progress = st.progress(0, text="Screening...")
            for i, tk in enumerate(selected_tickers):
                progress.progress((i + 1) / len(selected_tickers), text=f"Analyzing {tk}...")
                a = cached_analysis(tk)
                if a:
                    results.append(a)
            progress.empty()

            if results:
                order = {"BUY": 0, "WATCHLIST": 1, "OVERPRICED": 2, "UNKNOWN": 3}
                results.sort(key=lambda r: order.get(r["verdict"], 3))
                render_big5_table([big5_row(a) for a in results])

                for a in results:
                    with st.expander(f"{a['ticker']} — {a['name']} ({a['verdict']})"):
                        render_detail(a)
  except Exception as e:
    st.error(f"Screener tab error: {e}")


# ── Tab 3: Market Conditions ──────────────────────────────────────────────────

with tab_macro:
    try:
        st.header("Market Conditions")
        render_macro_tab()
    except Exception as e:
        st.error(f"Market tab error: {e}")


# ── Tab 4: News ───────────────────────────────────────────────────────────────

with tab_news:
    try:
        st.header("News Feed")
        news_tickers = list(portfolio["holdings"].keys()) + portfolio.get("watchlist", [])
        news_tickers = list(dict.fromkeys(news_tickers))

        if not news_tickers:
            st.info("Add holdings or watchlist stocks to see relevant news.")
        else:
            for tk in news_tickers:
                articles = cached_news(tk)
                if articles:
                    st.subheader(tk)
                    for art in articles:
                        render_news_card(art)
    except Exception as e:
        st.error(f"News tab error: {e}")


# ── Tab 5: Single Lookup ─────────────────────────────────────────────────────

with tab_lookup:
    try:
        st.header("Stock Lookup")
        col_input, col_marr = st.columns([2, 1])
        ticker_input = col_input.text_input("Ticker", placeholder="AAPL", label_visibility="collapsed")
        marr_input = col_marr.slider("MARR %", min_value=5, max_value=30, value=15, step=1)

        if st.button("Analyze", type="primary") and ticker_input:
            with st.spinner(f"Analyzing {ticker_input.upper()}..."):
                result = full_analysis(ticker_input.strip(), marr=marr_input / 100)
            if result:
                render_detail(result)

                st.markdown("### Recent News")
                articles = get_news(ticker_input.strip(), count=8)
                if articles:
                    for art in articles:
                        render_news_card(art)
                else:
                    st.info("No news found.")
            else:
                st.error(f"Could not find data for '{ticker_input}'. Check the ticker symbol.")
    except Exception as e:
        st.error(f"Lookup tab error: {e}")
