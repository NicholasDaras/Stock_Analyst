"""
SEC EDGAR integration for insider trading data.
Uses edgartools — free, no API key required.

Install: pip install edgartools
"""
from __future__ import annotations

import signal
from datetime import datetime, timedelta

_TIMEOUT = 15  # seconds max per EDGAR call


class _Timeout:
    """Context manager that raises TimeoutError after N seconds (Unix only)."""
    def __init__(self, seconds):
        self.seconds = seconds

    def __enter__(self):
        try:
            signal.signal(signal.SIGALRM, self._handler)
            signal.alarm(self.seconds)
        except (ValueError, AttributeError):
            pass  # Windows or non-main thread — skip timeout
        return self

    def __exit__(self, *args):
        try:
            signal.alarm(0)
        except (ValueError, AttributeError):
            pass

    def _handler(self, signum, frame):
        raise TimeoutError("EDGAR request timed out")


def _init_edgar():
    """Set EDGAR identity (required by SEC fair access policy)."""
    from edgar import set_identity
    set_identity("StockAnalystDashboard support@example.com")


def get_insider_trading(ticker: str, months: int = 12) -> dict:
    """
    Fetch insider trading (Form 4) data for a ticker from SEC EDGAR.
    Returns summary + recent transactions.
    """
    empty = {"transactions": [], "summary": None}
    try:
        with _Timeout(_TIMEOUT):
            _init_edgar()
            from edgar import Company

            company = Company(ticker.upper())
            filings = company.get_filings(form="4")

            if filings is None or len(filings) == 0:
                return empty

            cutoff = datetime.now() - timedelta(days=months * 30)

            transactions = []
            total_buys = 0
            total_sells = 0
            buy_value = 0.0
            sell_value = 0.0

            for filing in filings[:50]:
                try:
                    filing_date = filing.filing_date
                    if isinstance(filing_date, str):
                        filing_date = datetime.strptime(filing_date[:10], "%Y-%m-%d")
                    elif hasattr(filing_date, 'year'):
                        filing_date = datetime(filing_date.year, filing_date.month, filing_date.day)

                    if filing_date < cutoff:
                        break

                    try:
                        form4 = filing.obj()
                    except Exception:
                        continue

                    owner_name = ""
                    owner_title = ""
                    if hasattr(form4, 'reporting_owner') and form4.reporting_owner:
                        owner = form4.reporting_owner
                        if hasattr(owner, 'name'):
                            owner_name = str(owner.name)
                        elif hasattr(owner, 'owner_name'):
                            owner_name = str(owner.owner_name)
                        if hasattr(owner, 'officer_title'):
                            owner_title = str(owner.officer_title) if owner.officer_title else ""

                    txns = []
                    if hasattr(form4, 'non_derivative_transactions'):
                        txns = form4.non_derivative_transactions or []
                    elif hasattr(form4, 'transactions'):
                        txns = form4.transactions or []

                    for txn in txns:
                        try:
                            code = ""
                            if hasattr(txn, 'transaction_code'):
                                code = str(txn.transaction_code or "")
                            elif hasattr(txn, 'code'):
                                code = str(txn.code or "")

                            is_buy = code.upper() in ("P",)
                            is_sell = code.upper() in ("S",)

                            shares = 0
                            if hasattr(txn, 'transaction_shares'):
                                shares = float(txn.transaction_shares or 0)
                            elif hasattr(txn, 'shares'):
                                shares = float(txn.shares or 0)

                            price = 0
                            if hasattr(txn, 'transaction_price_per_share'):
                                price = float(txn.transaction_price_per_share or 0)
                            elif hasattr(txn, 'price_per_share'):
                                price = float(txn.price_per_share or 0)
                            elif hasattr(txn, 'price'):
                                price = float(txn.price or 0)

                            value = abs(shares) * price

                            if is_buy:
                                total_buys += 1
                                buy_value += value
                            elif is_sell:
                                total_sells += 1
                                sell_value += value
                            else:
                                continue

                            transactions.append({
                                "date": filing_date.strftime("%Y-%m-%d"),
                                "name": owner_name,
                                "title": owner_title,
                                "type": "BUY" if is_buy else "SELL",
                                "shares": abs(shares),
                                "price": price,
                                "value": value,
                            })
                        except (ValueError, TypeError, AttributeError):
                            continue

                except Exception:
                    continue

            transactions.sort(key=lambda x: x["date"], reverse=True)

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

            return {
                "transactions": transactions[:20],
                "summary": {
                    "total_buys": total_buys,
                    "total_sells": total_sells,
                    "buy_value": buy_value,
                    "sell_value": sell_value,
                    "net_value": buy_value - sell_value,
                    "sentiment": sentiment,
                    "buy_ratio": buy_ratio,
                    "period_months": months,
                },
            }

    except (TimeoutError, Exception):
        return empty
