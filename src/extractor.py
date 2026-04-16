from __future__ import annotations

import json
import re
from urllib.error import URLError
from urllib.request import Request, urlopen
from typing import Any

import pandas as pd

from src.config import llm_provider, ollama_base_url, ollama_model


FIELD_PATTERNS = {
    "fund_name": [
        r"Fund\s*Name[:\-]\s*(.+)",
        r"Fund[:\-]\s*(.+)",
    ],
    "investor": [
        r"Investor[:\-]\s*(.+)",
        r"Limited\s*Partner[:\-]\s*(.+)",
        r"LP[:\-]\s*(.+)",
    ],
    "currency": [
        r"Currency[:\-]\s*([A-Z]{3})",
        r"\b(EUR|USD|GBP|CHF|JPY|CAD|AUD|SGD|HKD|CNY)\b",
    ],
    "iban": [
        r"IBAN[:\-]?\s*([A-Z]{2}[A-Z0-9\s]{10,34})",
        r"Account\s*Number[:\-]?\s*([A-Z0-9\s]{10,34})",
    ],
    "swift": [
        r"SWIFT(?:/BIC)?[:\-]?\s*([A-Z0-9]{8,11})",
        r"BIC[:\-]?\s*([A-Z0-9]{8,11})",
    ],
    "beneficiary_bank": [
        r"Beneficiary\s*Bank[:\-]\s*(.+)",
        r"Bank[:\-]\s*(.+)",
    ],
}


### Normalize extracted text fragments by collapsing whitespace.
###############################################################################
def _clean_text(value: str) -> str:
    return " ".join(value.strip().split())


### Search the notice text with a sequence of regex patterns and return the first hit.
###############################################################################
def _search_patterns(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_text(match.group(1))
    return ""


### Extract amount and currency values from free-form notice text.
###############################################################################
def _extract_amount_and_currency(text: str) -> tuple[float | None, str]:
    currency = _search_patterns(text, FIELD_PATTERNS["currency"])
    patterns = [
        r"Amount\s*(?:Due)?[:\-]?\s*(?:[A-Z]{3}\s*)?([0-9][0-9,.' ]*[0-9])",
        r"Capital\s*Call\s*Amount[:\-]?\s*(?:[A-Z]{3}\s*)?([0-9][0-9,.' ]*[0-9])",
        r"Contribution\s*Amount[:\-]?\s*(?:[A-Z]{3}\s*)?([0-9][0-9,.' ]*[0-9])",
    ]
    raw_amount = _search_patterns(text, patterns)
    if not raw_amount:
        return None, currency

    normalized = raw_amount.replace("'", "").replace(" ", "")
    if normalized.count(",") > 1 and "." not in normalized:
        normalized = normalized.replace(",", "")
    elif "," in normalized and "." not in normalized:
        normalized = normalized.replace(",", ".")
    else:
        normalized = normalized.replace(",", "")

    try:
        return float(normalized), currency
    except ValueError:
        return None, currency


### Extract the due date using a small set of expected date labels.
###############################################################################
def _extract_due_date(text: str) -> pd.Timestamp | pd.NaT:
    patterns = [
        r"Due\s*Date[:\-]\s*([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4})",
        r"Payment\s*Date[:\-]\s*([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4})",
        r"Value\s*Date[:\-]\s*([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            parsed = pd.to_datetime(match.group(1), dayfirst=True, errors="coerce")
            if pd.notna(parsed):
                return parsed
    return pd.NaT


### Extract the first email address found in the notice text.
###############################################################################
def _find_counterparty_email(text: str) -> str:
    match = re.search(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", text, flags=re.IGNORECASE)
    return match.group(1) if match else ""


### Determine the fund name either from explicit labels or from the first plausible line.
###############################################################################
def _extract_fund_name(text: str) -> str:
    explicit = _search_patterns(text, FIELD_PATTERNS["fund_name"])
    if explicit:
        return explicit

    lines = [_clean_text(line) for line in text.splitlines() if _clean_text(line)]
    for line in lines:
        lowered = line.lower()
        if lowered.startswith(("to:", "amount:", "due date:", "payment instructions", "bank:", "iban:", "swift:", "bic:")):
            continue
        return line
    return ""


### Heuristic extraction fallback used when no LLM extraction is available.
###############################################################################
def heuristic_extract_notice_fields(text: str, filename: str = "") -> dict[str, Any]:
    amount, currency = _extract_amount_and_currency(text)
    due_date = _extract_due_date(text)

    return {
        "source_filename": filename,
        "fund_name": _extract_fund_name(text),
        "investor": _search_patterns(text, FIELD_PATTERNS["investor"]),
        "amount": amount,
        "currency": currency or "EUR",
        "due_date": due_date,
        "beneficiary_bank": _search_patterns(text, FIELD_PATTERNS["beneficiary_bank"]),
        "iban": _search_patterns(text, FIELD_PATTERNS["iban"]),
        "swift": _search_patterns(text, FIELD_PATTERNS["swift"]),
        "counterparty_email": _find_counterparty_email(text),
        "raw_text": text,
        "extraction_provider": "heuristic",
        "extraction_model": "rules",
    }


### Parse the JSON object from an LLM response, including wrapped or noisy outputs.
###############################################################################
def _extract_json_object(response_text: str) -> dict[str, Any]:
    response_text = response_text.strip()
    if not response_text:
        raise ValueError("Empty response from local LLM.")

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", response_text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


### Build the extraction prompt sent to the local LLM.
###############################################################################
def _ollama_prompt(text: str, filename: str) -> str:
    return f"""
Extract the capital call notice fields from the text below.
Return JSON only with exactly these keys:
fund_name, investor, amount, currency, due_date, beneficiary_bank, iban, swift, counterparty_email

Rules:
- amount must be a number only
- currency must be a 3-letter code if available
- due_date must be in ISO format YYYY-MM-DD if available
- iban and swift should be plain strings
- if a field is missing, return an empty string

Filename: {filename}

Notice text:
{text}
""".strip()


### Call Ollama, parse the structured response, and normalize the extracted fields.
###############################################################################
def ollama_extract_notice_fields(text: str, filename: str = "") -> dict[str, Any]:
    payload = {
        "model": ollama_model(),
        "prompt": _ollama_prompt(text, filename),
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
        },
    }
    request = Request(
        f"{ollama_base_url()}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    with urlopen(request, timeout=60) as response:
        response_payload = json.loads(response.read().decode("utf-8"))

    parsed = _extract_json_object(response_payload.get("response", ""))
    due_date = pd.to_datetime(parsed.get("due_date", ""), errors="coerce")

    amount_value = parsed.get("amount", "")
    amount = None
    if amount_value not in ("", None):
        try:
            amount = float(str(amount_value).replace(",", ""))
        except ValueError:
            amount = None

    return {
        "source_filename": filename,
        "fund_name": str(parsed.get("fund_name", "")).strip(),
        "investor": str(parsed.get("investor", "")).strip(),
        "amount": amount,
        "currency": str(parsed.get("currency", "")).strip() or "EUR",
        "due_date": due_date,
        "beneficiary_bank": str(parsed.get("beneficiary_bank", "")).strip(),
        "iban": str(parsed.get("iban", "")).strip(),
        "swift": str(parsed.get("swift", "")).strip(),
        "counterparty_email": str(parsed.get("counterparty_email", "")).strip(),
        "raw_text": text,
        "extraction_provider": "ollama",
        "extraction_model": ollama_model(),
    }


### Main extraction entrypoint selecting either Ollama or heuristic fallback logic.
###############################################################################
def extract_notice_fields(text: str, filename: str = "") -> dict[str, Any]:
    provider = llm_provider()
    if provider == "ollama":
        try:
            return ollama_extract_notice_fields(text, filename=filename)
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError):
            fallback = heuristic_extract_notice_fields(text, filename=filename)
            fallback["extraction_provider"] = "heuristic_fallback"
            fallback["extraction_model"] = "rules_after_ollama_failure"
            return fallback

    return heuristic_extract_notice_fields(text, filename=filename)
