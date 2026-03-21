#!/usr/bin/env python3
from __future__ import annotations

"""
Rule #1 Stock Analyzer
Based on Phil Town's Rule #1 investing methodology.

Analyzes a stock's:
- Big 5 Numbers (10yr, 5yr, 3yr, 1yr growth rates):
    ROIC, Sales/Revenue, EPS, Equity/BVPS, Free Cash Flow
- Debt Payoff Time (long-term debt / free cash flow)
- Sticker Price & Margin of Safety Price
"""

import sys
import argparse
import yfinance as yf
import numpy as np


# ── Data Fetching ─────────────────────────────────────────────────────────────

def fetch_data(ticker: str) -> dict:
    """Fetch all needed financial data from Yahoo Finance."""
    stock = yf.Ticker(ticker)
    info = stock.info

    income = stock.income_stmt          # annual, columns = dates descending
    balance = stock.balance_sheet
    cashflow = stock.cashflow

    return {
        "info": info,
        "income": income,
        "balance": balance,
        "cashflow": cashflow,
        "stock": stock,
    }


# ── Growth Rate Helpers ───────────────────────────────────────────────────────

def cagr(begin: float, end: float, years: int) -> float | None:
    """Compound annual growth rate. Returns None if inputs are invalid."""
    if begin is None or end is None or years <= 0:
        return None
    if begin <= 0 or end <= 0:
        return None
    return (end / begin) ** (1 / years) - 1


def get_series(df, row_labels: list[str]) -> list[float | None]:
    """Extract a time-series (oldest→newest) from a dataframe by trying multiple row labels."""
    if df is None or df.empty:
        return []
    for label in row_labels:
        if label in df.index:
            vals = df.loc[label].tolist()
            vals.reverse()  # oldest first
            return [float(v) if v is not None and not np.isnan(v) else None for v in vals]
    return []


def growth_rates(series: list[float | None]) -> dict:
    """Compute 10yr, 5yr, 3yr, 1yr CAGR from a time series (oldest→newest)."""
    n = len(series)
    results = {}
    for label, years in [("10yr", 10), ("5yr", 5), ("3yr", 3), ("1yr", 1)]:
        if n >= years + 1 and series[-(years + 1)] is not None and series[-1] is not None:
            results[label] = cagr(series[-(years + 1)], series[-1], years)
        else:
            results[label] = None
    return results


# ── Big 5 Calculations ───────────────────────────────────────────────────────

def compute_roic_series(data: dict) -> list[float | None]:
    """ROIC = Net Income / (Total Stockholder Equity + Long Term Debt)."""
    income = data["income"]
    balance = data["balance"]

    net_income = get_series(income, ["Net Income", "NetIncome", "Net Income Common Stockholders"])
    equity = get_series(balance, ["Stockholders Equity", "StockholdersEquity",
                                   "Total Stockholder Equity", "Common Stock Equity"])
    lt_debt = get_series(balance, ["Long Term Debt", "LongTermDebt", "Long Term Debt And Capital Lease Obligation"])

    length = min(len(net_income), len(equity))
    if length == 0:
        return []

    # Pad lt_debt with 0 if missing
    if not lt_debt:
        lt_debt = [0.0] * length
    length = min(length, len(lt_debt))

    roic = []
    for i in range(length):
        ni = net_income[i]
        eq = equity[i]
        debt = lt_debt[i] if lt_debt[i] is not None else 0.0
        if ni is not None and eq is not None:
            invested = eq + debt
            roic.append(ni / invested if invested != 0 else None)
        else:
            roic.append(None)
    return roic


def compute_sales_series(data: dict) -> list[float | None]:
    return get_series(data["income"], ["Total Revenue", "TotalRevenue", "Revenue",
                                        "Operating Revenue"])


def compute_eps_series(data: dict) -> list[float | None]:
    """Try to get EPS from income stmt, fall back to net_income / shares."""
    eps = get_series(data["income"], ["Basic EPS", "Diluted EPS", "BasicEPS", "DilutedEPS"])
    if eps:
        return eps
    # Fallback
    net_income = get_series(data["income"], ["Net Income", "NetIncome", "Net Income Common Stockholders"])
    shares = get_series(data["income"], ["Basic Average Shares", "Diluted Average Shares",
                                          "BasicAverageShares", "ShareIssued"])
    if net_income and shares:
        length = min(len(net_income), len(shares))
        return [
            net_income[i] / shares[i] if net_income[i] is not None and shares[i] else None
            for i in range(length)
        ]
    return []


def compute_bvps_series(data: dict) -> list[float | None]:
    """Book Value Per Share = Equity / Shares Outstanding."""
    equity = get_series(data["balance"], ["Stockholders Equity", "StockholdersEquity",
                                           "Total Stockholder Equity", "Common Stock Equity"])
    shares = get_series(data["income"], ["Basic Average Shares", "Diluted Average Shares",
                                          "BasicAverageShares", "ShareIssued"])
    if not equity or not shares:
        # Try from balance sheet
        shares = get_series(data["balance"], ["Share Issued", "Ordinary Shares Number"])
    if not equity or not shares:
        return equity  # return raw equity as fallback
    length = min(len(equity), len(shares))
    return [
        equity[i] / shares[i] if equity[i] is not None and shares[i] else None
        for i in range(length)
    ]


def compute_fcf_series(data: dict) -> list[float | None]:
    """Free Cash Flow = Operating Cash Flow - Capital Expenditures."""
    ocf = get_series(data["cashflow"], ["Operating Cash Flow", "Total Cash From Operating Activities",
                                         "OperatingCashFlow"])
    capex = get_series(data["cashflow"], ["Capital Expenditure", "CapitalExpenditure",
                                           "Capital Expenditures"])
    if ocf and capex:
        length = min(len(ocf), len(capex))
        return [
            ocf[i] - abs(capex[i]) if ocf[i] is not None and capex[i] is not None else None
            for i in range(length)
        ]
    fcf = get_series(data["cashflow"], ["Free Cash Flow", "FreeCashFlow"])
    return fcf


def compute_big5(data: dict) -> dict:
    """Compute all Big 5 growth rates."""
    roic_series = compute_roic_series(data)
    sales_series = compute_sales_series(data)
    eps_series = compute_eps_series(data)
    bvps_series = compute_bvps_series(data)
    fcf_series = compute_fcf_series(data)

    # For ROIC, we report the values themselves (not growth of ROIC)
    # Phil Town wants ROIC > 10% consistently, plus growth rates of the other 4
    return {
        "ROIC": {
            "series": roic_series,
            "latest": roic_series[-1] if roic_series else None,
            "rates": avg_roic_periods(roic_series),
        },
        "Sales": {
            "series": sales_series,
            "rates": growth_rates(sales_series),
        },
        "EPS": {
            "series": eps_series,
            "rates": growth_rates(eps_series),
        },
        "Equity (BVPS)": {
            "series": bvps_series,
            "rates": growth_rates(bvps_series),
        },
        "Free Cash Flow": {
            "series": fcf_series,
            "rates": growth_rates(fcf_series),
        },
    }


def avg_roic_periods(roic_series: list[float | None]) -> dict:
    """Average ROIC over 10yr, 5yr, 3yr, 1yr windows."""
    n = len(roic_series)
    results = {}
    for label, years in [("10yr", 10), ("5yr", 5), ("3yr", 3), ("1yr", 1)]:
        if n >= years:
            window = [v for v in roic_series[-years:] if v is not None]
            results[label] = sum(window) / len(window) if window else None
        else:
            results[label] = None
    return results


# ── Debt Payoff ───────────────────────────────────────────────────────────────

def compute_debt_payoff(data: dict) -> float | None:
    """Years to pay off long-term debt with current free cash flow."""
    lt_debt = get_series(data["balance"], ["Long Term Debt", "LongTermDebt",
                                            "Long Term Debt And Capital Lease Obligation"])
    fcf = compute_fcf_series(data)
    if lt_debt and fcf and lt_debt[-1] is not None and fcf[-1] is not None and fcf[-1] > 0:
        return lt_debt[-1] / fcf[-1]
    return None


# ── Sticker Price ─────────────────────────────────────────────────────────────

def compute_sticker_price(data: dict, big5: dict, marr: float = 0.15) -> dict:
    """
    Sticker Price calculation per Rule #1:
    1. Current EPS
    2. Estimated EPS growth rate (use the lower of analyst or historical equity growth)
    3. Estimated future PE = 2x growth rate (capped at historical PE)
    4. Future EPS (10 years out) = current EPS * (1 + growth)^10
    5. Future market price = future EPS * future PE
    6. Sticker Price = future price / (1 + MARR)^10
    7. MOS Price = Sticker Price / 2
    """
    info = data["info"]

    # Current EPS
    current_eps = info.get("trailingEps") or info.get("forwardEps")
    if current_eps is None:
        eps_series = big5["EPS"]["series"]
        current_eps = eps_series[-1] if eps_series else None

    # Analyst growth estimate
    analyst_growth = info.get("earningsGrowth") or info.get("earningsQuarterlyGrowth")

    # Historical equity/BVPS growth — use the best available long-term rate
    equity_rates = big5["Equity (BVPS)"]["rates"]
    hist_growth = None
    for period in ["10yr", "5yr", "3yr", "1yr"]:
        if equity_rates.get(period) is not None:
            hist_growth = equity_rates[period]
            break

    # EPS growth rates as another reference
    eps_rates = big5["EPS"]["rates"]
    hist_eps_growth = None
    for period in ["10yr", "5yr", "3yr", "1yr"]:
        if eps_rates.get(period) is not None:
            hist_eps_growth = eps_rates[period]
            break

    # Pick the most conservative growth rate
    candidates = [g for g in [analyst_growth, hist_growth, hist_eps_growth] if g is not None and g > 0]
    growth_rate = min(candidates) if candidates else None

    # PE ratio
    current_pe = info.get("trailingPE") or info.get("forwardPE")
    default_pe = (growth_rate * 200) if growth_rate else None  # 2x growth as percentage

    if default_pe is not None and current_pe is not None:
        future_pe = min(default_pe, current_pe)
    elif default_pe is not None:
        future_pe = default_pe
    elif current_pe is not None:
        future_pe = current_pe
    else:
        future_pe = None

    # Calculate prices
    if current_eps and growth_rate and future_pe and current_eps > 0:
        future_eps = current_eps * (1 + growth_rate) ** 10
        future_price = future_eps * future_pe
        sticker_price = future_price / (1 + marr) ** 10
        mos_price = sticker_price / 2
    else:
        future_eps = None
        future_price = None
        sticker_price = None
        mos_price = None

    return {
        "current_eps": current_eps,
        "growth_rate": growth_rate,
        "analyst_growth": analyst_growth,
        "hist_equity_growth": hist_growth,
        "hist_eps_growth": hist_eps_growth,
        "current_pe": current_pe,
        "future_pe": future_pe,
        "future_eps": future_eps,
        "future_price": future_price,
        "sticker_price": sticker_price,
        "mos_price": mos_price,
        "marr": marr,
    }


# ── Display ───────────────────────────────────────────────────────────────────

def fmt_pct(val: float | None) -> str:
    if val is None:
        return "  N/A  "
    return f"{val * 100:>6.1f}%"


def fmt_dollar(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"${val:,.2f}"


def fmt_num(val: float | None, billions: bool = False) -> str:
    if val is None:
        return "N/A"
    if billions:
        return f"${val / 1e9:,.2f}B"
    return f"{val:,.2f}"


def pass_fail(val: float | None, threshold: float = 0.10) -> str:
    if val is None:
        return "?"
    return "PASS" if val >= threshold else "FAIL"


def print_report(ticker: str, data: dict, big5: dict, debt_payoff: float | None, sticker: dict):
    info = data["info"]
    name = info.get("longName") or info.get("shortName") or ticker
    price = info.get("currentPrice") or info.get("previousClose") or info.get("regularMarketPrice")
    sector = info.get("sector", "N/A")
    industry = info.get("industry", "N/A")

    print()
    print("=" * 72)
    print(f"  RULE #1 ANALYSIS: {name} ({ticker.upper()})")
    print("=" * 72)
    print(f"  Sector:   {sector}")
    print(f"  Industry: {industry}")
    print(f"  Price:    {fmt_dollar(price)}")
    print()

    # ── Big 5 ──
    print("-" * 72)
    print("  THE BIG 5 NUMBERS")
    print("  (Rule #1: All growth rates should be >= 10%)")
    print("-" * 72)
    header = f"  {'Metric':<20} {'10yr':>8} {'5yr':>8} {'3yr':>8} {'1yr':>8}  {'Verdict'}"
    print(header)
    print("  " + "-" * 68)

    # ROIC row — shows average ROIC per period (not growth of ROIC)
    roic = big5["ROIC"]
    roic_rates = roic["rates"]
    # For verdict, check if most recent ROIC > 10%
    roic_verdict = pass_fail(roic["latest"])
    print(f"  {'ROIC':<20} {fmt_pct(roic_rates.get('10yr')):>8} {fmt_pct(roic_rates.get('5yr')):>8} "
          f"{fmt_pct(roic_rates.get('3yr')):>8} {fmt_pct(roic_rates.get('1yr')):>8}  {roic_verdict}")

    # Other 4 metrics — show growth rates
    for label in ["Sales", "EPS", "Equity (BVPS)", "Free Cash Flow"]:
        rates = big5[label]["rates"]
        # Verdict based on longest available rate
        verdict_val = None
        for period in ["10yr", "5yr", "3yr", "1yr"]:
            if rates.get(period) is not None:
                verdict_val = rates[period]
                break
        verdict = pass_fail(verdict_val)
        print(f"  {label:<20} {fmt_pct(rates.get('10yr')):>8} {fmt_pct(rates.get('5yr')):>8} "
              f"{fmt_pct(rates.get('3yr')):>8} {fmt_pct(rates.get('1yr')):>8}  {verdict}")

    print()

    # ── Moat / Debt ──
    print("-" * 72)
    print("  MOAT INDICATORS")
    print("-" * 72)
    if debt_payoff is not None:
        debt_status = "PASS" if debt_payoff <= 3 else ("OK" if debt_payoff <= 5 else "FAIL")
        print(f"  Debt Payoff Time:  {debt_payoff:.1f} years  ({debt_status}, target < 3 years)")
    else:
        print("  Debt Payoff Time:  N/A")
    print()

    # ── Sticker Price ──
    print("-" * 72)
    print("  STICKER PRICE CALCULATION")
    print("-" * 72)
    print(f"  Current EPS:           {fmt_dollar(sticker['current_eps'])}")
    print(f"  EPS Growth Rate Used:  {fmt_pct(sticker['growth_rate'])}")
    print(f"    - Analyst Estimate:  {fmt_pct(sticker['analyst_growth'])}")
    print(f"    - Hist. Equity Gr.:  {fmt_pct(sticker['hist_equity_growth'])}")
    print(f"    - Hist. EPS Growth:  {fmt_pct(sticker['hist_eps_growth'])}")
    print(f"  Current PE:            {fmt_num(sticker['current_pe'])}")
    print(f"  Future PE (est.):      {fmt_num(sticker['future_pe'])}")
    print(f"  Min. Acceptable RoR:   {fmt_pct(sticker['marr'])}")
    print()
    print(f"  Future EPS (10yr):     {fmt_dollar(sticker['future_eps'])}")
    print(f"  Future Mkt Price:      {fmt_dollar(sticker['future_price'])}")
    print(f"  >> Sticker Price:      {fmt_dollar(sticker['sticker_price'])}")
    print(f"  >> MOS Price (50%):    {fmt_dollar(sticker['mos_price'])}")
    print()

    # ── Final Verdict ──
    print("-" * 72)
    print("  VERDICT")
    print("-" * 72)
    if price and sticker["mos_price"]:
        if price <= sticker["mos_price"]:
            print(f"  Current price ({fmt_dollar(price)}) is BELOW the MOS Price ({fmt_dollar(sticker['mos_price'])})")
            print("  >> POTENTIALLY A BUY at this price (do your own due diligence!)")
        elif price <= sticker["sticker_price"]:
            print(f"  Current price ({fmt_dollar(price)}) is below Sticker ({fmt_dollar(sticker['sticker_price'])}) "
                  f"but ABOVE MOS ({fmt_dollar(sticker['mos_price'])})")
            print("  >> ON WATCHLIST — wait for a better price")
        else:
            print(f"  Current price ({fmt_dollar(price)}) is ABOVE the Sticker Price ({fmt_dollar(sticker['sticker_price'])})")
            print("  >> OVERPRICED by Rule #1 standards")
    else:
        print("  Could not determine buy/sell verdict (insufficient data).")

    print()
    print("=" * 72)
    print("  Disclaimer: This is not financial advice. Always do your own research.")
    print("=" * 72)
    print()


# ── Structured Analysis (for dashboard) ───────────────────────────────────────

def full_analysis(ticker: str, marr: float = 0.15) -> dict | None:
    """Run full Rule #1 analysis, return structured dict (or None on failure)."""
    try:
        data = fetch_data(ticker)
    except Exception:
        return None

    info = data["info"]
    if not info.get("longName") and not info.get("shortName"):
        return None

    big5 = compute_big5(data)
    debt_payoff = compute_debt_payoff(data)
    sticker = compute_sticker_price(data, big5, marr=marr)

    price = info.get("currentPrice") or info.get("previousClose") or info.get("regularMarketPrice")

    # Determine verdict
    if price and sticker["mos_price"]:
        if price <= sticker["mos_price"]:
            verdict = "BUY"
        elif price <= sticker["sticker_price"]:
            verdict = "WATCHLIST"
        else:
            verdict = "OVERPRICED"
    else:
        verdict = "UNKNOWN"

    # Count Big 5 passes
    passes = 0
    total = 0
    # ROIC
    if big5["ROIC"]["latest"] is not None:
        total += 1
        if big5["ROIC"]["latest"] >= 0.10:
            passes += 1
    for label in ["Sales", "EPS", "Equity (BVPS)", "Free Cash Flow"]:
        rates = big5[label]["rates"]
        for period in ["10yr", "5yr", "3yr", "1yr"]:
            if rates.get(period) is not None:
                total += 1
                if rates[period] >= 0.10:
                    passes += 1
                break

    return {
        "ticker": ticker.upper(),
        "name": info.get("longName") or info.get("shortName") or ticker,
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "price": price,
        "big5": big5,
        "big5_score": f"{passes}/{total}",
        "debt_payoff": debt_payoff,
        "sticker": sticker,
        "verdict": verdict,
    }


def get_news(ticker: str, count: int = 5) -> list[dict]:
    """Get recent news for a ticker via yfinance."""
    try:
        stock = yf.Ticker(ticker)
        news = stock.news or []
        results = []
        for item in news[:count]:
            content = item.get("content", {})
            results.append({
                "title": content.get("title", item.get("title", "No title")),
                "publisher": content.get("provider", {}).get("displayName", "Unknown"),
                "link": content.get("canonicalUrl", {}).get("url", item.get("link", "")),
                "published": content.get("pubDate", ""),
            })
        return results
    except Exception:
        return []


# ── Main ──────────────────────────────────────────────────────────────────────

def analyze(ticker: str, marr: float = 0.15):
    print(f"\nFetching data for {ticker.upper()}...")
    data = fetch_data(ticker)

    if not data["info"].get("longName") and not data["info"].get("shortName"):
        print(f"Error: Could not find data for ticker '{ticker}'. Check the symbol and try again.")
        sys.exit(1)

    big5 = compute_big5(data)
    debt_payoff = compute_debt_payoff(data)
    sticker = compute_sticker_price(data, big5, marr=marr)
    print_report(ticker, data, big5, debt_payoff, sticker)


def main():
    parser = argparse.ArgumentParser(
        description="Rule #1 Stock Analyzer — Phil Town's investing methodology"
    )
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., AAPL, MSFT, GOOG)")
    parser.add_argument("--marr", type=float, default=0.15,
                        help="Minimum Acceptable Rate of Return (default: 0.15 = 15%%)")
    args = parser.parse_args()
    analyze(args.ticker, marr=args.marr)


if __name__ == "__main__":
    main()
