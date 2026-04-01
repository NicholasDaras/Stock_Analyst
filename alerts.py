"""
Alert system for Rule #1 investing signals.
Triggers when market conditions + individual stock quality align.

Criteria for a "green light" alert:
- Market conditions score <= 40 (FEAR or CAUTIOUS)
- Stock has 5/5 Big 5 score (all growth metrics >= 10%)
- Stock is priced at or below MOS price (BUY verdict)
"""
from __future__ import annotations

import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def find_green_light_stocks(scan_results: dict, market_score: int | None = None) -> list[dict]:
    """
    Scan results and return stocks that pass ALL criteria.
    Each result includes investment strategy suggestions.
    """
    if not scan_results or not scan_results.get("results"):
        return []

    alerts = []
    for ticker, data in scan_results["results"].items():
        # Must be a BUY verdict (price <= MOS)
        if data.get("verdict") != "BUY":
            continue

        # Must have 5/5 Big 5 (100% green flags)
        score = data.get("big5_score", "0/0")
        try:
            passed, total = score.split("/")
            if int(total) == 0 or int(passed) < int(total):
                continue
        except (ValueError, AttributeError):
            continue

        sticker = data.get("sticker", {})
        price = data.get("price")
        mos_price = sticker.get("mos_price")
        sticker_price = sticker.get("sticker_price")
        growth_rate = sticker.get("growth_rate")

        if not price or not mos_price or not sticker_price:
            continue

        # Calculate discount and strategy
        discount_to_mos = (1 - price / mos_price) * 100 if mos_price else 0
        discount_to_sticker = (1 - price / sticker_price) * 100 if sticker_price else 0
        upside = (sticker_price / price - 1) * 100 if price else 0

        # Investment length suggestion based on Rule #1 methodology
        # Phil Town: buy wonderful companies, hold until they're no longer wonderful
        # or the price exceeds intrinsic value
        if growth_rate and growth_rate > 0.15:
            hold_suggestion = "3-5 years"
            hold_reason = "High growth rate — could reach sticker price faster"
        elif growth_rate and growth_rate > 0.10:
            hold_suggestion = "5-10 years"
            hold_reason = "Solid growth — standard Rule #1 holding period"
        else:
            hold_suggestion = "7-10+ years"
            hold_reason = "Moderate growth — patience required for full value"

        # Entry strategy
        if discount_to_mos > 20:
            entry = "STRONG BUY"
            entry_detail = f"Trading {discount_to_mos:.0f}% below MOS price — deep value"
        elif discount_to_mos > 0:
            entry = "BUY"
            entry_detail = f"Trading {discount_to_mos:.0f}% below MOS price"
        else:
            entry = "BUY AT MOS"
            entry_detail = "Right at the Margin of Safety price"

        # Debt consideration
        debt = data.get("debt_payoff")
        debt_note = ""
        if debt is not None:
            if debt <= 2:
                debt_note = "Very low debt — strong balance sheet."
            elif debt <= 3:
                debt_note = "Manageable debt."
            elif debt <= 5:
                debt_note = "Moderate debt — monitor cash flow."
            else:
                debt_note = "High debt — added risk. Consider smaller position."

        alerts.append({
            "ticker": ticker,
            "name": data.get("name", ticker),
            "sector": data.get("sector", "N/A"),
            "price": price,
            "mos_price": mos_price,
            "sticker_price": sticker_price,
            "big5_score": score,
            "growth_rate": growth_rate,
            "discount_to_mos": discount_to_mos,
            "discount_to_sticker": discount_to_sticker,
            "upside_to_sticker": upside,
            "debt_payoff": debt,
            "entry_signal": entry,
            "entry_detail": entry_detail,
            "hold_suggestion": hold_suggestion,
            "hold_reason": hold_reason,
            "debt_note": debt_note,
            "strategy": {
                "buy_at": f"${price:,.2f} or below",
                "target_price": f"${sticker_price:,.2f}",
                "mos_price": f"${mos_price:,.2f}",
                "potential_return": f"{upside:,.0f}%",
                "suggested_hold": hold_suggestion,
            },
        })

    # Sort by deepest discount first
    alerts.sort(key=lambda x: x["discount_to_sticker"], reverse=True)
    return alerts


def build_alert_text(alerts: list[dict], market_score: int | None = None) -> str:
    """Build a plain-text alert summary."""
    lines = []
    lines.append("=" * 60)
    lines.append("  RULE #1 GREEN LIGHT ALERT")
    lines.append(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)

    if market_score is not None:
        if market_score <= 30:
            lines.append(f"\n  Market Score: {market_score}/100 — FEAR")
            lines.append("  Conditions are highly favorable for buying.")
        elif market_score <= 45:
            lines.append(f"\n  Market Score: {market_score}/100 — CAUTIOUS")
            lines.append("  Mixed conditions, but quality stocks are worth buying.")

    lines.append(f"\n  {len(alerts)} stock(s) passed ALL Rule #1 criteria:")
    lines.append("  - 5/5 Big 5 growth metrics (all >= 10%)")
    lines.append("  - Price at or below Margin of Safety")
    lines.append("")

    for a in alerts:
        lines.append("-" * 60)
        lines.append(f"  {a['name']} ({a['ticker']})")
        lines.append(f"  Sector: {a['sector']}")
        lines.append(f"  Signal: {a['entry_signal']} — {a['entry_detail']}")
        lines.append("")
        lines.append(f"  Current Price:   ${a['price']:>10,.2f}")
        lines.append(f"  MOS Price:       ${a['mos_price']:>10,.2f}")
        lines.append(f"  Sticker Price:   ${a['sticker_price']:>10,.2f}")
        lines.append(f"  Big 5 Score:     {a['big5_score']}")
        if a['growth_rate']:
            lines.append(f"  Growth Rate:     {a['growth_rate']*100:.1f}%")
        lines.append("")
        lines.append(f"  Upside to Sticker: {a['upside_to_sticker']:.0f}%")
        lines.append(f"  Suggested Hold:    {a['hold_suggestion']}")
        lines.append(f"  Reason:            {a['hold_reason']}")
        if a['debt_note']:
            lines.append(f"  Debt:              {a['debt_note']}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("  This is not financial advice. Always do your own research.")
    lines.append("=" * 60)
    return "\n".join(lines)


def build_alert_html(alerts: list[dict], market_score: int | None = None) -> str:
    """Build an HTML email body."""
    if market_score is not None and market_score <= 30:
        market_badge = '<span style="color:#3fb950;font-weight:700;">FEAR</span>'
        market_msg = "Conditions are highly favorable for buying."
    elif market_score is not None and market_score <= 45:
        market_badge = '<span style="color:#d29922;font-weight:700;">CAUTIOUS</span>'
        market_msg = "Mixed conditions, but quality stocks are worth buying."
    else:
        market_badge = '<span style="color:#7d8590;">NEUTRAL</span>'
        market_msg = ""

    stock_rows = ""
    for a in alerts:
        signal_color = "#3fb950" if a["entry_signal"] == "STRONG BUY" else "#58a6ff"
        stock_rows += f"""
        <tr style="border-bottom:1px solid #21262d;">
            <td style="padding:12px;">
                <strong style="font-size:1.1em;">{a['ticker']}</strong><br>
                <span style="color:#7d8590;">{a['name']}</span>
            </td>
            <td style="padding:12px;">
                <span style="color:{signal_color};font-weight:600;">{a['entry_signal']}</span><br>
                <span style="color:#7d8590;font-size:0.85em;">{a['entry_detail']}</span>
            </td>
            <td style="padding:12px;text-align:right;">
                ${a['price']:,.2f}<br>
                <span style="color:#7d8590;font-size:0.85em;">MOS: ${a['mos_price']:,.2f}</span>
            </td>
            <td style="padding:12px;text-align:right;">
                <span style="color:#3fb950;font-weight:600;">{a['upside_to_sticker']:.0f}%</span><br>
                <span style="color:#7d8590;font-size:0.85em;">to ${a['sticker_price']:,.2f}</span>
            </td>
            <td style="padding:12px;">
                {a['hold_suggestion']}<br>
                <span style="color:#7d8590;font-size:0.85em;">{a['hold_reason']}</span>
            </td>
        </tr>"""

    return f"""
    <div style="font-family:-apple-system,Arial,sans-serif;max-width:800px;margin:0 auto;
                background:#0d1117;color:#e6edf3;padding:24px;border-radius:8px;">
        <h1 style="color:#3fb950;margin:0 0 4px 0;">Rule #1 Green Light Alert</h1>
        <p style="color:#7d8590;margin:0 0 20px 0;">{datetime.now().strftime('%B %d, %Y')}</p>

        <div style="background:#161b22;border:1px solid #21262d;border-radius:6px;padding:16px;margin-bottom:20px;">
            <p style="margin:0;">Market Conditions: {market_badge}
            {f' — Score: {market_score}/100' if market_score else ''}</p>
            {f'<p style="color:#7d8590;margin:4px 0 0 0;">{market_msg}</p>' if market_msg else ''}
        </div>

        <p><strong>{len(alerts)} stock(s)</strong> passed ALL Rule #1 criteria (5/5 Big 5 + below MOS price):</p>

        <table style="width:100%;border-collapse:collapse;margin:16px 0;">
            <thead>
                <tr style="border-bottom:2px solid #21262d;color:#7d8590;text-align:left;">
                    <th style="padding:8px 12px;">Stock</th>
                    <th style="padding:8px 12px;">Signal</th>
                    <th style="padding:8px 12px;text-align:right;">Price</th>
                    <th style="padding:8px 12px;text-align:right;">Upside</th>
                    <th style="padding:8px 12px;">Hold Period</th>
                </tr>
            </thead>
            <tbody>{stock_rows}</tbody>
        </table>

        <p style="color:#7d8590;font-size:0.85em;border-top:1px solid #21262d;padding-top:12px;">
            This is not financial advice. Always do your own research.<br>
            Generated by Rule #1 Dashboard
        </p>
    </div>
    """


def send_email_alert(
    alerts: list[dict],
    market_score: int | None,
    to_email: str,
    smtp_user: str,
    smtp_password: str,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
):
    """Send an alert email via SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Rule #1 Alert: {len(alerts)} Green Light Stock(s)"
    msg["From"] = smtp_user
    msg["To"] = to_email

    text_body = build_alert_text(alerts, market_score)
    html_body = build_alert_html(alerts, market_score)

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to_email, msg.as_string())


def check_and_alert(
    scan_file: str | None = None,
    market_score: int | None = None,
    email_config: dict | None = None,
) -> list[dict]:
    """
    Check scan results for green light stocks and optionally send email.
    Returns the list of alerts found.
    """
    if scan_file is None:
        scan_file = os.path.join(os.path.dirname(__file__), "scan_results.json")

    if not os.path.exists(scan_file):
        return []

    with open(scan_file, "r") as f:
        scan_data = json.load(f)

    alerts = find_green_light_stocks(scan_data, market_score)

    if not alerts:
        return []

    # Save alerts to file for dashboard
    alert_file = os.path.join(os.path.dirname(__file__), "alerts.json")
    with open(alert_file, "w") as f:
        json.dump({
            "date": datetime.now().isoformat(),
            "market_score": market_score,
            "alerts": alerts,
        }, f, indent=2)

    # Send email if configured
    if email_config and email_config.get("to_email"):
        try:
            send_email_alert(
                alerts=alerts,
                market_score=market_score,
                to_email=email_config["to_email"],
                smtp_user=email_config["smtp_user"],
                smtp_password=email_config["smtp_password"],
                smtp_host=email_config.get("smtp_host", "smtp.gmail.com"),
                smtp_port=email_config.get("smtp_port", 587),
            )
            print(f"[{datetime.now()}] Alert email sent to {email_config['to_email']}")
        except Exception as e:
            print(f"[{datetime.now()}] Failed to send alert email: {e}")

    return alerts
