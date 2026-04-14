from __future__ import annotations

from typing import Any

import pandas as pd


def _fmt_amount(amount: Any, currency: str) -> str:
    if amount in (None, ""):
        return f"{currency} -"
    formatted_amount = f"{float(amount):,.2f}".replace(",", "'")
    return f"{currency} {formatted_amount}"


def _fmt_date(value: Any) -> str:
    if not value:
        return "-"
    parsed = pd.to_datetime(value, errors="coerce")
    return parsed.strftime("%d.%m.%Y") if pd.notna(parsed) else str(value)


def generate_payment_confirmation_email(notice: dict[str, Any]) -> str:
    fund_name = notice.get("fund_name", "your fund")
    amount = _fmt_amount(notice.get("amount"), notice.get("currency", "EUR"))
    due_date = _fmt_date(notice.get("due_date"))
    iban = notice.get("iban", "-")
    swift = notice.get("swift", "-")

    return f"""Subject: Payment Confirmation - {fund_name}

Dear Counterparty,

We confirm that the capital call payment for {fund_name} has been instructed.

Amount: {amount}
Due Date: {due_date}
IBAN: {iban}
SWIFT/BIC: {swift}

Please let us know if you require any additional details.

Kind regards,
Treasury Operations
Calibrium AG
"""
