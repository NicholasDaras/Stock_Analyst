"""
Quiver Quantitative integration.
Fetches insider trading, congressional trading, lobbying, and government contracts.

API docs: https://api.quiverquant.com/docs/
API key: Sign up at quiverquant.com
Store key in .streamlit/secrets.toml as: quiver_api_key = "YOUR_KEY"
"""
from __future__ import annotations

import os
import requests
from datetime import datetime, timedelta

BASE_URL = "https://api.quiverquant.com/beta"


def _headers(api_key: str | None = None) -> dict:
    if api_key is None:
        api_key = os.environ.get("QUIVER_API_KEY")
    if not api_key:
        raise ValueError("Quiver API key required. Set QUIVER_API_KEY env var or pass api_key.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }


def _get(endpoint: str, api_key: str | None = None) -> list[dict]:
    """Make a GET request to Quiver API."""
    try:
        resp = requests.get(f"{BASE_URL}{endpoint}", headers=_headers(api_key), timeout=15)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception:
        return []


# ── Insider Trading ──────────────────────────────────────────────────────────

def get_insider_trading(ticker: str, api_key: str | None = None, months: int = 12) -> dict:
    """
    Get insider trading activity for a ticker.
    Returns summary + recent transactions.
    """
    raw = _get(f"/historical/insiders/{ticker.upper()}", api_key)
    if not raw:
        return {"transactions": [], "summary": None}

    cutoff = datetime.now() - timedelta(days=months * 30)

    transactions = []
    total_buys = 0
    total_sells = 0
    buy_value = 0.0
    sell_value = 0.0

    for entry in raw:
        try:
            date_str = entry.get("Date", "")
            if not date_str:
                continue
            date = datetime.strptime(date_str[:10], "%Y-%m-%d")
            if date < cutoff:
                continue

            name = entry.get("Name", "Unknown")
            title = entry.get("Title", "")
            transaction_type = entry.get("Transaction", "")
            shares = entry.get("Shares", 0) or 0
            price = entry.get("Price", 0) or 0
            value = shares * price

            is_buy = "purchase" in transaction_type.lower() or "buy" in transaction_type.lower()
            is_sell = "sale" in transaction_type.lower() or "sell" in transaction_type.lower()

            if is_buy:
                total_buys += 1
                buy_value += value
            elif is_sell:
                total_sells += 1
                sell_value += value

            transactions.append({
                "date": date_str[:10],
                "name": name,
                "title": title,
                "type": "BUY" if is_buy else ("SELL" if is_sell else transaction_type),
                "shares": shares,
                "price": price,
                "value": value,
            })
        except (ValueError, TypeError):
            continue

    transactions.sort(key=lambda x: x["date"], reverse=True)

    # Net insider sentiment
    if total_buys + total_sells > 0:
        buy_ratio = total_buys / (total_buys + total_sells)
        if buy_ratio > 0.6:
            sentiment = "BULLISH"
        elif buy_ratio > 0.4:
            sentiment = "NEUTRAL"
        else:
            sentiment = "BEARISH"
    else:
        sentiment = "NO DATA"
        buy_ratio = 0

    summary = {
        "total_buys": total_buys,
        "total_sells": total_sells,
        "buy_value": buy_value,
        "sell_value": sell_value,
        "net_value": buy_value - sell_value,
        "sentiment": sentiment,
        "buy_ratio": buy_ratio,
        "period_months": months,
    }

    return {
        "transactions": transactions[:20],  # most recent 20
        "summary": summary,
    }


# ── Congressional Trading ────────────────────────────────────────────────────

def get_congressional_trading(ticker: str, api_key: str | None = None, months: int = 12) -> dict:
    """
    Get congressional trading activity for a ticker.
    Returns recent trades by members of Congress.
    """
    raw = _get(f"/historical/congresstrading/{ticker.upper()}", api_key)
    if not raw:
        return {"trades": [], "summary": None}

    cutoff = datetime.now() - timedelta(days=months * 30)

    trades = []
    buys = 0
    sells = 0

    for entry in raw:
        try:
            date_str = entry.get("Date", entry.get("TransactionDate", ""))
            if not date_str:
                continue
            date = datetime.strptime(date_str[:10], "%Y-%m-%d")
            if date < cutoff:
                continue

            representative = entry.get("Representative", "Unknown")
            transaction = entry.get("Transaction", "")
            amount = entry.get("Amount", entry.get("Range", "Unknown"))
            party = entry.get("Party", "")
            chamber = entry.get("House", entry.get("Chamber", ""))

            is_buy = "purchase" in transaction.lower() or "buy" in transaction.lower()
            is_sell = "sale" in transaction.lower() or "sell" in transaction.lower()

            if is_buy:
                buys += 1
            elif is_sell:
                sells += 1

            trades.append({
                "date": date_str[:10],
                "representative": representative,
                "party": party,
                "chamber": chamber,
                "type": "BUY" if is_buy else ("SELL" if is_sell else transaction),
                "amount": amount,
            })
        except (ValueError, TypeError):
            continue

    trades.sort(key=lambda x: x["date"], reverse=True)

    summary = {
        "total_buys": buys,
        "total_sells": sells,
        "total_trades": len(trades),
        "period_months": months,
    }

    return {
        "trades": trades[:15],
        "summary": summary,
    }


# ── Lobbying ─────────────────────────────────────────────────────────────────

def get_lobbying(ticker: str, api_key: str | None = None) -> dict:
    """
    Get lobbying expenditure data for a ticker.
    High lobbying spend can indicate regulatory moat building.
    """
    raw = _get(f"/historical/lobbying/{ticker.upper()}", api_key)
    if not raw:
        return {"records": [], "total_spend": 0}

    records = []
    total_spend = 0.0

    for entry in raw:
        try:
            amount = entry.get("Amount", 0) or 0
            issue = entry.get("Issue", "")
            date_str = entry.get("Date", "")

            total_spend += amount
            records.append({
                "date": date_str[:10] if date_str else "",
                "amount": amount,
                "issue": issue,
            })
        except (ValueError, TypeError):
            continue

    records.sort(key=lambda x: x["date"], reverse=True)

    return {
        "records": records[:10],
        "total_spend": total_spend,
    }


# ── Government Contracts ─────────────────────────────────────────────────────

def get_gov_contracts(ticker: str, api_key: str | None = None) -> dict:
    """
    Get government contract data for a ticker.
    Recurring contracts = predictable revenue.
    """
    raw = _get(f"/historical/govcontracts/{ticker.upper()}", api_key)
    if not raw:
        return {"contracts": [], "total_value": 0}

    contracts = []
    total_value = 0.0

    for entry in raw:
        try:
            amount = entry.get("Amount", 0) or 0
            agency = entry.get("Agency", "")
            desc = entry.get("Description", "")
            date_str = entry.get("Date", "")

            total_value += amount
            contracts.append({
                "date": date_str[:10] if date_str else "",
                "amount": amount,
                "agency": agency,
                "description": desc[:100],
            })
        except (ValueError, TypeError):
            continue

    contracts.sort(key=lambda x: x["date"], reverse=True)

    return {
        "contracts": contracts[:10],
        "total_value": total_value,
    }


# ── Combined Ticker Report ───────────────────────────────────────────────────

def get_alternative_data(ticker: str, api_key: str | None = None) -> dict:
    """
    Fetch all available Quiver data for a ticker.
    Returns a combined dict with insider, congressional, lobbying, and contracts data.
    """
    return {
        "insider": get_insider_trading(ticker, api_key),
        "congress": get_congressional_trading(ticker, api_key),
        "lobbying": get_lobbying(ticker, api_key),
        "contracts": get_gov_contracts(ticker, api_key),
    }
