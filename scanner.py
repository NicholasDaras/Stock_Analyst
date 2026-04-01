#!/usr/bin/env python3
from __future__ import annotations

"""
Nightly S&P 500 scanner — runs Rule #1 analysis on all S&P 500 stocks
and caches results to scan_results.json.

Usage:
    python3 scanner.py              # full scan
    python3 scanner.py --resume     # resume interrupted scan
    python3 scanner.py --ticker-only  # just refresh ticker list
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TICKERS_FILE = os.path.join(SCRIPT_DIR, "sp500_tickers.json")
RESULTS_FILE = os.path.join(SCRIPT_DIR, "scan_results.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "scan.log")


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def fetch_sp500_tickers() -> list[str]:
    """Fetch current S&P 500 constituents from Wikipedia."""
    try:
        import io
        import pandas as pd
        import urllib.request
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req).read().decode("utf-8")
        tables = pd.read_html(io.StringIO(html))
        df = tables[0]
        tickers = df["Symbol"].tolist()
        tickers = [t.replace(".", "-") for t in tickers]
        return sorted(tickers)
    except Exception as e:
        log(f"Failed to fetch S&P 500 list from Wikipedia: {e}")
        log("Using bundled S&P 500 list as fallback")
        return _FALLBACK_SP500[:]


# Fallback list — top ~500 S&P 500 constituents (updated periodically)
_FALLBACK_SP500 = [
    "AAPL", "ABBV", "ABT", "ACN", "ADBE", "ADI", "ADM", "ADP", "ADSK", "AEE",
    "AEP", "AES", "AFL", "AIG", "AIZ", "AJG", "AKAM", "ALB", "ALGN", "ALK",
    "ALL", "ALLE", "AMAT", "AMCR", "AMD", "AME", "AMGN", "AMP", "AMT", "AMZN",
    "ANET", "ANSS", "AON", "AOS", "APA", "APD", "APH", "APTV", "ARE", "ATO",
    "ATVI", "AVB", "AVGO", "AVY", "AWK", "AXP", "AZO", "BA", "BAC", "BAX",
    "BBWI", "BBY", "BDX", "BEN", "BF-B", "BIIB", "BIO", "BK", "BKNG", "BKR",
    "BLK", "BMY", "BR", "BRK-B", "BRO", "BSX", "BWA", "BXP", "C", "CAG",
    "CAH", "CARR", "CAT", "CB", "CBOE", "CBRE", "CCI", "CCL", "CDAY", "CDNS",
    "CDW", "CE", "CEG", "CF", "CFG", "CHD", "CHRW", "CHTR", "CI", "CINF",
    "CL", "CLX", "CMA", "CMCSA", "CME", "CMG", "CMI", "CMS", "CNC", "CNP",
    "COF", "COO", "COP", "COST", "CPB", "CPRT", "CPT", "CRL", "CRM", "CSCO",
    "CSGP", "CSX", "CTAS", "CTLT", "CTRA", "CTSH", "CTVA", "CVS", "CVX", "CZR",
    "D", "DAL", "DD", "DE", "DFS", "DG", "DGX", "DHI", "DHR", "DIS",
    "DISH", "DLR", "DLTR", "DOV", "DOW", "DPZ", "DRI", "DTE", "DUK", "DVA",
    "DVN", "DXC", "DXCM", "EA", "EBAY", "ECL", "ED", "EFX", "EIX", "EL",
    "EMN", "EMR", "ENPH", "EOG", "EPAM", "EQIX", "EQR", "EQT", "ES", "ESS",
    "ETN", "ETR", "ETSY", "EVRG", "EW", "EXC", "EXPD", "EXPE", "EXR", "F",
    "FANG", "FAST", "FBHS", "FCX", "FDS", "FDX", "FE", "FFIV", "FIS", "FISV",
    "FITB", "FLT", "FMC", "FOX", "FOXA", "FRC", "FRT", "FTNT", "FTV", "GD",
    "GE", "GILD", "GIS", "GL", "GLW", "GM", "GNRC", "GOOG", "GOOGL", "GPC",
    "GPN", "GRMN", "GS", "GWW", "HAL", "HAS", "HBAN", "HCA", "HD", "HOLX",
    "HON", "HPE", "HPQ", "HRL", "HSIC", "HST", "HSY", "HUM", "HWM", "IBM",
    "ICE", "IDXX", "IEX", "IFF", "ILMN", "INCY", "INTC", "INTU", "INVH", "IP",
    "IPG", "IQV", "IR", "IRM", "ISRG", "IT", "ITW", "IVZ", "J", "JBHT",
    "JCI", "JKHY", "JNJ", "JNPR", "JPM", "K", "KDP", "KEY", "KEYS", "KHC",
    "KIM", "KLAC", "KMB", "KMI", "KMX", "KO", "KR", "L", "LDOS", "LEN",
    "LH", "LHX", "LIN", "LKQ", "LLY", "LMT", "LNC", "LNT", "LOW", "LRCX",
    "LUMN", "LUV", "LVS", "LW", "LYB", "LYV", "MA", "MAA", "MAR", "MAS",
    "MCD", "MCHP", "MCK", "MCO", "MDLZ", "MDT", "MET", "META", "MGM", "MHK",
    "MKC", "MKTX", "MLM", "MMC", "MMM", "MNST", "MO", "MOH", "MOS", "MPC",
    "MPWR", "MRK", "MRNA", "MRO", "MS", "MSCI", "MSFT", "MSI", "MTB", "MTCH",
    "MTD", "MU", "NCLH", "NDAQ", "NDSN", "NEE", "NEM", "NFLX", "NI", "NKE",
    "NOC", "NOW", "NRG", "NSC", "NTAP", "NTRS", "NUE", "NVDA", "NVR", "NWL",
    "NWS", "NWSA", "NXPI", "O", "ODFL", "OGN", "OKE", "OMC", "ON", "ORCL",
    "ORLY", "OTIS", "OXY", "PARA", "PAYC", "PAYX", "PCAR", "PCG", "PEAK", "PEG",
    "PEP", "PFE", "PFG", "PG", "PGR", "PH", "PHM", "PKG", "PKI", "PLD",
    "PM", "PNC", "PNR", "PNW", "POOL", "PPG", "PPL", "PRU", "PSA", "PSX",
    "PTC", "PVH", "PWR", "PXD", "PYPL", "QCOM", "QRVO", "RCL", "RE", "REG",
    "REGN", "RF", "RHI", "RJF", "RL", "RMD", "ROK", "ROL", "ROP", "ROST",
    "RSG", "RTX", "SBAC", "SBNY", "SBUX", "SCHW", "SEE", "SHW", "SIVB", "SJM",
    "SLB", "SNA", "SNPS", "SO", "SPG", "SPGI", "SRE", "STE", "STT", "STX",
    "STZ", "SWK", "SWKS", "SYF", "SYK", "SYY", "T", "TAP", "TDG", "TDY",
    "TECH", "TEL", "TER", "TFC", "TFX", "TGT", "TMO", "TMUS", "TPR", "TRGP",
    "TRMB", "TROW", "TRV", "TSCO", "TSLA", "TSN", "TT", "TTWO", "TXN", "TXT",
    "TYL", "UAL", "UDR", "UHS", "ULTA", "UNH", "UNP", "UPS", "URI", "USB",
    "V", "VFC", "VICI", "VLO", "VMC", "VNO", "VRSK", "VRSN", "VRTX", "VTR",
    "VTRS", "VZ", "WAB", "WAT", "WBA", "WBD", "WDC", "WEC", "WELL", "WFC",
    "WHR", "WM", "WMB", "WMT", "WRB", "WRK", "WST", "WTW", "WY", "WYNN",
    "XEL", "XOM", "XRAY", "XYL", "YUM", "ZBH", "ZBRA", "ZION", "ZTS",
]


def load_tickers() -> list[str]:
    """Load cached ticker list, or fetch fresh."""
    if os.path.exists(TICKERS_FILE):
        with open(TICKERS_FILE, "r") as f:
            data = json.load(f)
        age_days = (datetime.now() - datetime.fromisoformat(data["updated"])).days
        if age_days < 30:
            return data["tickers"]
        log(f"Ticker list is {age_days} days old, refreshing...")

    tickers = fetch_sp500_tickers()
    if tickers:
        with open(TICKERS_FILE, "w") as f:
            json.dump({"updated": datetime.now().isoformat(), "tickers": tickers}, f, indent=2)
        log(f"Saved {len(tickers)} S&P 500 tickers")
    return tickers


def load_existing_results() -> dict:
    """Load previously cached scan results."""
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r") as f:
            return json.load(f)
    return {"scan_date": None, "results": {}}


def save_results(results: dict):
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)


def run_scan(resume: bool = False):
    from rule1 import full_analysis

    tickers = load_tickers()
    if not tickers:
        log("No tickers to scan. Exiting.")
        sys.exit(1)

    log(f"Starting scan of {len(tickers)} S&P 500 stocks...")

    existing = load_existing_results() if resume else {"scan_date": None, "results": {}}
    already_done = set(existing["results"].keys()) if resume else set()

    if resume and already_done:
        log(f"Resuming — {len(already_done)} already scanned, {len(tickers) - len(already_done)} remaining")

    existing["scan_date"] = datetime.now().isoformat()
    succeeded = len(already_done)
    failed = 0
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        if ticker in already_done:
            continue

        try:
            result = full_analysis(ticker)
            if result:
                existing["results"][ticker] = result
                succeeded += 1
                verdict = result["verdict"]
                log(f"[{i+1}/{total}] {ticker}: {verdict}")
            else:
                failed += 1
                log(f"[{i+1}/{total}] {ticker}: SKIP (no data)")
        except Exception as e:
            failed += 1
            log(f"[{i+1}/{total}] {ticker}: ERROR ({e})")

        # Save progress every 25 stocks
        if (i + 1) % 25 == 0:
            save_results(existing)

        # Rate limit — be polite to Yahoo
        time.sleep(1.5)

    save_results(existing)

    # Summary
    buys = [t for t, r in existing["results"].items() if r["verdict"] == "BUY"]
    watches = [t for t, r in existing["results"].items() if r["verdict"] == "WATCHLIST"]

    log(f"Scan complete: {succeeded} succeeded, {failed} failed")
    log(f"BUY signals: {', '.join(buys) if buys else 'None'}")
    log(f"WATCHLIST: {', '.join(watches) if watches else 'None'}")

    # ── Green Light Alert Check ──────────────────────────────────────────────
    try:
        from alerts import check_and_alert

        # Get market score if FRED is available
        market_score = None
        try:
            secrets_file = os.path.expanduser("~/.streamlit/secrets.toml")
            fred_key = None
            if os.path.exists(secrets_file):
                with open(secrets_file, "r") as f:
                    for line in f:
                        if line.strip().startswith("fred_api_key"):
                            fred_key = line.split("=")[1].strip().strip('"').strip("'")
                            break
            if fred_key:
                from fred_data import fetch_macro_snapshot, compute_fear_greed
                snapshot = fetch_macro_snapshot(api_key=fred_key)
                fg = compute_fear_greed(snapshot)
                market_score = fg["score"]
                log(f"Market conditions score: {market_score}/100 ({fg['label']})")
        except Exception as e:
            log(f"Could not fetch market conditions: {e}")

        # Load email config from secrets
        email_config = None
        try:
            if os.path.exists(secrets_file):
                cfg = {}
                with open(secrets_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line and not line.startswith("#"):
                            key, val = line.split("=", 1)
                            cfg[key.strip()] = val.strip().strip('"').strip("'")
                if cfg.get("alert_email") and cfg.get("smtp_user") and cfg.get("smtp_password"):
                    email_config = {
                        "to_email": cfg["alert_email"],
                        "smtp_user": cfg["smtp_user"],
                        "smtp_password": cfg["smtp_password"],
                    }
        except Exception:
            pass

        alerts = check_and_alert(
            scan_file=RESULTS_FILE,
            market_score=market_score,
            email_config=email_config,
        )

        if alerts:
            log(f"GREEN LIGHT: {len(alerts)} stocks passed all criteria: "
                f"{', '.join(a['ticker'] for a in alerts)}")
        else:
            log("No green light alerts this scan.")
    except Exception as e:
        log(f"Alert check failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="S&P 500 Rule #1 Scanner")
    parser.add_argument("--resume", action="store_true", help="Resume interrupted scan")
    parser.add_argument("--tickers-only", action="store_true", help="Just refresh ticker list")
    args = parser.parse_args()

    if args.tickers_only:
        tickers = fetch_sp500_tickers()
        if tickers:
            with open(TICKERS_FILE, "w") as f:
                json.dump({"updated": datetime.now().isoformat(), "tickers": tickers}, f, indent=2)
            log(f"Saved {len(tickers)} tickers")
        return

    run_scan(resume=args.resume)


if __name__ == "__main__":
    main()
