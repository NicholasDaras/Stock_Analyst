"""
FRED (Federal Reserve Economic Data) integration.
Fetches macro indicators for market conditions dashboard.

Requires: fredapi (pip install fredapi)
API key: https://fred.stlouisfed.org/docs/api/api_key.html
Store key in .streamlit/secrets.toml as: fred_api_key = "YOUR_KEY"
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

SERIES = {
    "fed_funds":         {"id": "FEDFUNDS",  "label": "Fed Funds Rate",      "fmt": "pct"},
    "treasury_10y":      {"id": "DGS10",     "label": "10-Year Treasury",    "fmt": "pct"},
    "treasury_2y":       {"id": "DGS2",      "label": "2-Year Treasury",     "fmt": "pct"},
    "yield_spread":      {"id": "T10Y2Y",    "label": "Yield Spread (10Y-2Y)", "fmt": "pct"},
    "cpi":               {"id": "CPIAUCSL",  "label": "CPI (All Urban)",     "fmt": "num"},
    "cpi_yoy":           {"id": "CPIAUCNS",  "label": "CPI YoY",            "fmt": "pct"},
    "unemployment":      {"id": "UNRATE",    "label": "Unemployment Rate",   "fmt": "pct"},
    "consumer_sentiment": {"id": "UMCSENT",  "label": "Consumer Sentiment",  "fmt": "num"},
    "gdp":               {"id": "GDP",       "label": "GDP (Billions)",      "fmt": "dollar"},
    "m2":                {"id": "M2SL",      "label": "M2 Money Supply",     "fmt": "num"},
}


def get_fred(api_key: str | None = None):
    """Get a Fred client instance."""
    from fredapi import Fred

    if api_key is None:
        api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise ValueError("FRED API key required. Set FRED_API_KEY env var or pass api_key.")
    return Fred(api_key=api_key)


def fetch_macro_snapshot(api_key: str | None = None) -> dict:
    """
    Fetch latest values for all macro indicators.
    Returns dict keyed by series name with value, date, label, history.
    """
    fred = get_fred(api_key)
    snapshot = {}

    for name, meta in SERIES.items():
        try:
            # Get last 2 years of data for sparkline/history
            end = datetime.now()
            start = end - timedelta(days=730)
            series = fred.get_series(meta["id"], observation_start=start, observation_end=end)
            series = series.dropna()

            if series.empty:
                snapshot[name] = {
                    "value": None,
                    "date": None,
                    "label": meta["label"],
                    "fmt": meta["fmt"],
                    "history": [],
                }
                continue

            latest_val = float(series.iloc[-1])
            latest_date = series.index[-1].strftime("%Y-%m-%d")

            # Previous value for delta
            prev_val = float(series.iloc[-2]) if len(series) > 1 else None

            # History as list of (date_str, value) for charts
            history = [
                (idx.strftime("%Y-%m-%d"), float(val))
                for idx, val in series.items()
            ]

            snapshot[name] = {
                "value": latest_val,
                "prev_value": prev_val,
                "date": latest_date,
                "label": meta["label"],
                "fmt": meta["fmt"],
                "history": history,
            }
        except Exception:
            snapshot[name] = {
                "value": None,
                "date": None,
                "label": meta["label"],
                "fmt": meta["fmt"],
                "history": [],
            }

    return snapshot


def compute_fear_greed(snapshot: dict) -> dict:
    """
    Simple market conditions gauge based on FRED data.
    Returns score 0-100 (0 = extreme fear, 100 = extreme greed) and signals.
    """
    signals = []
    score_parts = []

    # Yield curve: negative spread = recession signal = fear
    spread = snapshot.get("yield_spread", {})
    if spread.get("value") is not None:
        val = spread["value"]
        if val < 0:
            signals.append(("Yield Curve", "INVERTED", "Recession signal — historically precedes downturns"))
            score_parts.append(15)
        elif val < 0.5:
            signals.append(("Yield Curve", "FLAT", "Caution — curve is nearly flat"))
            score_parts.append(35)
        elif val < 1.5:
            signals.append(("Yield Curve", "NORMAL", "Healthy spread"))
            score_parts.append(55)
        else:
            signals.append(("Yield Curve", "STEEP", "Expansionary — markets expect growth"))
            score_parts.append(75)

    # Unemployment: rising = fear, low = greed
    unemp = snapshot.get("unemployment", {})
    if unemp.get("value") is not None:
        val = unemp["value"]
        if val > 6:
            signals.append(("Unemployment", "HIGH", "Weak labor market — potential buying opportunities"))
            score_parts.append(20)
        elif val > 5:
            signals.append(("Unemployment", "ELEVATED", "Softening labor market"))
            score_parts.append(35)
        elif val > 4:
            signals.append(("Unemployment", "MODERATE", "Stable employment"))
            score_parts.append(55)
        else:
            signals.append(("Unemployment", "LOW", "Strong labor market — late cycle"))
            score_parts.append(70)

    # Fed Funds Rate: high rates = tighter conditions
    ffr = snapshot.get("fed_funds", {})
    if ffr.get("value") is not None:
        val = ffr["value"]
        if val > 5:
            signals.append(("Fed Rate", "RESTRICTIVE", "Tight money — valuations pressured"))
            score_parts.append(25)
        elif val > 3:
            signals.append(("Fed Rate", "ELEVATED", "Above neutral — headwind for stocks"))
            score_parts.append(40)
        elif val > 1:
            signals.append(("Fed Rate", "MODERATE", "Neutral monetary policy"))
            score_parts.append(55)
        else:
            signals.append(("Fed Rate", "ACCOMMODATIVE", "Easy money — tailwind for stocks"))
            score_parts.append(75)

    # Consumer Sentiment: low = fear
    sent = snapshot.get("consumer_sentiment", {})
    if sent.get("value") is not None:
        val = sent["value"]
        if val < 60:
            signals.append(("Sentiment", "PESSIMISTIC", "Consumers are fearful — contrarian buy signal"))
            score_parts.append(25)
        elif val < 75:
            signals.append(("Sentiment", "CAUTIOUS", "Below-average confidence"))
            score_parts.append(40)
        elif val < 90:
            signals.append(("Sentiment", "NEUTRAL", "Average consumer confidence"))
            score_parts.append(55)
        else:
            signals.append(("Sentiment", "OPTIMISTIC", "High confidence — possible late-cycle euphoria"))
            score_parts.append(75)

    overall = sum(score_parts) / len(score_parts) if score_parts else 50

    if overall < 30:
        label = "FEAR"
        desc = "Conditions favor Rule #1 buyers — look for deals"
    elif overall < 45:
        label = "CAUTIOUS"
        desc = "Mixed signals — be selective, stick to quality"
    elif overall < 60:
        label = "NEUTRAL"
        desc = "Normal conditions — focus on individual stock quality"
    elif overall < 75:
        label = "OPTIMISTIC"
        desc = "Markets are confident — be patient on price"
    else:
        label = "GREED"
        desc = "Elevated risk — raise your margin of safety"

    return {
        "score": round(overall),
        "label": label,
        "description": desc,
        "signals": signals,
    }


def suggest_marr(snapshot: dict) -> float:
    """
    Suggest a MARR adjustment based on current interest rates.
    Rule #1 default is 15%, but higher rates warrant higher MARR.
    """
    treasury = snapshot.get("treasury_10y", {})
    if treasury.get("value") is None:
        return 0.15  # default

    t10 = treasury["value"] / 100  # convert from percentage

    # MARR should be at least 15% or the 10-year + risk premium (7%)
    return max(0.15, t10 + 0.07)
