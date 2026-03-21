"""
Portfolio storage — simple JSON file for tracking holdings and watchlist.
"""
from __future__ import annotations

import json
import os

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio.json")

DEFAULT = {
    "holdings": {},   # ticker -> {"shares": float, "avg_cost": float}
    "watchlist": [],  # list of ticker strings
}


def _load() -> dict:
    if not os.path.exists(PORTFOLIO_FILE):
        return json.loads(json.dumps(DEFAULT))
    with open(PORTFOLIO_FILE, "r") as f:
        return json.load(f)


def _save(data: dict):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_portfolio() -> dict:
    return _load()


def add_holding(ticker: str, shares: float, avg_cost: float):
    data = _load()
    ticker = ticker.upper()
    if ticker in data["holdings"]:
        existing = data["holdings"][ticker]
        total_shares = existing["shares"] + shares
        total_cost = (existing["shares"] * existing["avg_cost"]) + (shares * avg_cost)
        existing["shares"] = total_shares
        existing["avg_cost"] = total_cost / total_shares if total_shares else 0
    else:
        data["holdings"][ticker] = {"shares": shares, "avg_cost": avg_cost}
    _save(data)


def remove_holding(ticker: str):
    data = _load()
    data["holdings"].pop(ticker.upper(), None)
    _save(data)


def add_to_watchlist(ticker: str):
    data = _load()
    ticker = ticker.upper()
    if ticker not in data["watchlist"]:
        data["watchlist"].append(ticker)
    _save(data)


def remove_from_watchlist(ticker: str):
    data = _load()
    ticker = ticker.upper()
    data["watchlist"] = [t for t in data["watchlist"] if t != ticker]
    _save(data)
