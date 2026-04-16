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
        r"To[:\-]\s*(.+)",
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


### Detect obvious placeholder values that are not usable as an extracted investor name.
###############################################################################
def _is_placeholder_investor(value: Any) -> bool:
    cleaned = _clean_text(str(value or "")).lower()
    return cleaned in {"", "to", "investor", "limited partner", "lp"}


### Filter out structural lines that should not be interpreted as investor names.
###############################################################################
def _is_non_investor_line(value: str) -> bool:
    lowered = _clean_text(value).lower()
    return (
        not lowered
        or lowered.startswith(("amount", "due date", "payment instructions", "bank", "iban", "swift", "bic"))
        or bool(re.match(r"^(eur|usd|gbp|chf|jpy|cad|aud|sgd|hkd|cny)\b", lowered))
        or bool(re.match(r"^[0-9]", lowered))
    )


### Return the meaningful text lines of a notice in reading order.
###############################################################################
def _content_lines(text: str) -> list[str]:
    return [_clean_text(line) for line in text.splitlines() if _clean_text(line)]


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

    lines = _content_lines(text)
    for line in lines:
        lowered = line.lower()
        if lowered.startswith(("to:", "amount:", "due date:", "payment instructions", "bank:", "iban:", "swift:", "bic:")):
            continue
        return line
    return ""


### Determine the investor / limited partner from labels, addressee lines, or known notice layout.
###############################################################################
def _extract_investor(text: str) -> str:
    lines = _content_lines(text)

    for line in lines:
        line_match = re.match(r"^(?:Investor|Limited\s*Partner|LP|To)\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if line_match:
            candidate = _clean_text(line_match.group(1))
            if not _is_placeholder_investor(candidate):
                return candidate

    explicit = _search_patterns(text, FIELD_PATTERNS["investor"])
    if explicit and not _is_placeholder_investor(explicit):
        return explicit

    for line in lines:
        lowered = line.lower()
        if lowered.startswith("to:") or lowered.startswith("to :"):
            candidate = _clean_text(line.split(":", 1)[1]) if ":" in line else ""
            if not _is_placeholder_investor(candidate):
                return candidate

    fund_name = _extract_fund_name(text)
    if fund_name:
        try:
            fund_index = lines.index(fund_name)
        except ValueError:
            fund_index = -1

        if fund_index >= 0:
            for candidate in lines[fund_index + 1 :]:
                if _is_non_investor_line(candidate):
                    break
                if not _is_placeholder_investor(candidate):
                    return candidate

    return ""


### Heuristic extraction fallback used when no LLM extraction is available.
###############################################################################
def heuristic_extract_notice_fields(text: str, filename: str = "") -> dict[str, Any]:
    amount, currency = _extract_amount_and_currency(text)
    due_date = _extract_due_date(text)

    return {
        "source_filename": filename,
        "fund_name": _extract_fund_name(text),
        "investor": _extract_investor(text),
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
- investor may appear as Investor, Limited Partner, LP, or To
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

    extracted = {
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

    heuristic_fallback = heuristic_extract_notice_fields(text, filename=filename)
    for field_name in [
        "fund_name",
        "investor",
        "amount",
        "currency",
        "due_date",
        "beneficiary_bank",
        "iban",
        "swift",
        "counterparty_email",
    ]:
        current_value = extracted.get(field_name)
        should_replace = current_value in ("", None) or (
            field_name == "due_date" and pd.isna(current_value)
        )
        if field_name == "investor" and _is_placeholder_investor(current_value):
            should_replace = True

        if should_replace:
            fallback_value = heuristic_fallback.get(field_name)
            if fallback_value not in ("", None) and not (
                field_name == "due_date" and pd.isna(fallback_value)
            ):
                extracted[field_name] = fallback_value

    heuristic_investor = heuristic_fallback.get("investor", "")
    heuristic_fund_name = heuristic_fallback.get("fund_name", "")
    if heuristic_investor and heuristic_fund_name:
        normalized_fund = _clean_text(str(extracted.get("fund_name", "")))
        normalized_investor = _clean_text(str(extracted.get("investor", "")))
        if heuristic_investor in normalized_fund and (
            _is_placeholder_investor(normalized_investor)
            or normalized_investor in {"", "To"}
        ):
            extracted["fund_name"] = heuristic_fund_name
            extracted["investor"] = heuristic_investor

    return extracted


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
