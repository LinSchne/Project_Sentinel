from __future__ import annotations

import re
from typing import Any

import pandas as pd

from src.approved_wires import normalize_iban, normalize_text
from src.fund_name_utils import normalize_fund_name_for_matching


GENERIC_FUND_NAME_SUFFIX_WORDS = {
    "capital",
    "call",
    "drawdown",
    "notice",
    "distribution",
    "test",
}


### Remove generic suffix words from a fund name while preserving the original numeral form.
###############################################################################
def _strip_generic_fund_name_words(value: str) -> str:
    cleaned = normalize_text(value).upper()
    tokens = re.findall(r"[A-Z0-9]+", cleaned)
    filtered_tokens = [
        token for token in tokens if token.lower() not in GENERIC_FUND_NAME_SUFFIX_WORDS
    ]
    return " ".join(filtered_tokens)


### Normalize fund names for loose matching by removing generic suffix words.
###############################################################################
def _normalize_fund_name_for_loose_match(value: str) -> str:
    return normalize_fund_name_for_matching(_strip_generic_fund_name_words(value))


### Match an extracted fund name against the commitment tracker using exact and partial logic.
###############################################################################
def _match_fund_row(commitment_df: pd.DataFrame, fund_name: str) -> dict[str, Any] | None:
    if commitment_df.empty or not fund_name:
        return None

    normalized_target = normalize_text(fund_name)
    normalized_numeric_target = normalize_fund_name_for_matching(fund_name)
    normalized_loose_target = _normalize_fund_name_for_loose_match(fund_name)
    exact_matches = commitment_df[
        commitment_df["Fund Name"].astype(str).apply(normalize_text).eq(normalized_target)
    ]
    if not exact_matches.empty:
        matched = exact_matches.iloc[0].to_dict()
        matched["_fund_match_type"] = "exact"
        return matched

    numeric_matches = commitment_df[
        commitment_df["Fund Name"]
        .astype(str)
        .apply(normalize_fund_name_for_matching)
        .eq(normalized_numeric_target)
    ]
    if not numeric_matches.empty:
        matched = numeric_matches.iloc[0].to_dict()
        matched["_fund_match_type"] = "numeric_variant"
        return matched

    partial_matches = commitment_df[
        commitment_df["Fund Name"].astype(str).apply(
            lambda value: (
                normalized_target in normalize_text(value)
                or normalize_text(value) in normalized_target
                or normalized_numeric_target in normalize_fund_name_for_matching(value)
                or normalize_fund_name_for_matching(value) in normalized_numeric_target
                or normalized_loose_target in _normalize_fund_name_for_loose_match(value)
                or _normalize_fund_name_for_loose_match(value) in normalized_loose_target
            )
        )
    ]
    if not partial_matches.empty:
        matched = partial_matches.iloc[0].to_dict()
        matched["_fund_match_type"] = "partial"
        return matched

    return None


### Sum scheduled workflow notices already reserving commitment for the same fund and investor.
###############################################################################
def _scheduled_commitment_usage(
    notices: list[dict[str, Any]],
    matched_fund: str,
    matched_investor: str,
) -> tuple[float, list[dict[str, Any]]]:
    scheduled_matches: list[dict[str, Any]] = []
    normalized_fund = normalize_text(matched_fund)
    normalized_numeric_fund = normalize_fund_name_for_matching(matched_fund)
    normalized_investor = normalize_text(matched_investor)

    for notice in notices:
        if str(notice.get("status", "")).strip().lower() != "scheduled":
            continue

        notice_fund = str(notice.get("fund_name", "")).strip()
        notice_investor = str(notice.get("investor", "")).strip()
        if not notice_fund or not notice_investor:
            continue

        fund_matches = (
            normalize_text(notice_fund) == normalized_fund
            or normalize_fund_name_for_matching(notice_fund) == normalized_numeric_fund
        )
        investor_matches = normalize_text(notice_investor) == normalized_investor
        if not (fund_matches and investor_matches):
            continue

        amount = notice.get("amount")
        try:
            scheduled_amount = float(amount or 0)
        except (TypeError, ValueError):
            scheduled_amount = 0.0

        scheduled_matches.append(
            {
                "id": notice.get("id", ""),
                "amount": scheduled_amount,
                "due_date": notice.get("due_date", ""),
            }
        )

    scheduled_total = sum(entry["amount"] for entry in scheduled_matches)
    return scheduled_total, scheduled_matches


### Sum historical upcoming capital calls already reserving commitment for the same fund and investor.
###############################################################################
def _historical_upcoming_commitment_usage(
    upcoming_df: pd.DataFrame,
    matched_fund: str,
    matched_investor: str,
) -> tuple[float, list[dict[str, Any]]]:
    if upcoming_df.empty:
        return 0.0, []

    normalized_fund = normalize_text(matched_fund)
    normalized_numeric_fund = normalize_fund_name_for_matching(matched_fund)
    normalized_investor = normalize_text(matched_investor)
    historical_matches: list[dict[str, Any]] = []

    for _, row in upcoming_df.iterrows():
        upcoming_fund = str(row.get("Fund Name", "")).strip()
        upcoming_investor = str(row.get("Investor", "")).strip()
        if not upcoming_fund or not upcoming_investor:
            continue

        fund_matches = (
            normalize_text(upcoming_fund) == normalized_fund
            or normalize_fund_name_for_matching(upcoming_fund) == normalized_numeric_fund
        )
        investor_matches = normalize_text(upcoming_investor) == normalized_investor
        if not (fund_matches and investor_matches):
            continue

        amount = row.get("Amount", 0)
        try:
            reserved_amount = float(amount or 0)
        except (TypeError, ValueError):
            reserved_amount = 0.0

        due_date = row.get("Due Date", "")
        if pd.notna(due_date):
            due_date = str(due_date)
        else:
            due_date = ""

        historical_matches.append(
            {
                "id": "",
                "amount": reserved_amount,
                "due_date": due_date,
                "source": "historical_upcoming",
            }
        )

    reserved_total = sum(entry["amount"] for entry in historical_matches)
    return reserved_total, historical_matches


### Provide a likely commitment-tracker fund suggestion for upload-review warnings.
###############################################################################
def suggest_fund_name_match(
    extracted_fund_name: str,
    commitment_df: pd.DataFrame,
) -> dict[str, str] | None:
    matched_row = _match_fund_row(commitment_df, extracted_fund_name)
    if not matched_row:
        return None

    matched_fund = str(matched_row.get("Fund Name", "")).strip()
    match_type = str(matched_row.get("_fund_match_type", ""))
    if match_type not in {"numeric_variant", "partial"}:
        return None

    stripped_extracted = _strip_generic_fund_name_words(extracted_fund_name)
    stripped_matched = _strip_generic_fund_name_words(matched_fund)
    numeric_stripped_extracted = normalize_fund_name_for_matching(stripped_extracted)
    numeric_stripped_matched = normalize_fund_name_for_matching(stripped_matched)

    has_extra_wording = normalize_text(extracted_fund_name) != normalize_text(stripped_extracted)
    has_numeric_variant = (
        normalize_text(stripped_extracted) != normalize_text(stripped_matched)
        and numeric_stripped_extracted == numeric_stripped_matched
    )

    hint = {
        "matched_fund": matched_fund,
        "match_type": match_type,
    }
    if has_extra_wording and has_numeric_variant:
        hint["message"] = (
            "The extracted fund name may include extra wording and may also use Arabic numbers "
            "where the Commitment Tracker uses Roman numerals, or vice versa."
        )
    elif has_numeric_variant or match_type == "numeric_variant":
        hint["message"] = (
            "The extracted fund name may use Arabic numbers where the Commitment Tracker uses "
            "Roman numerals, or vice versa."
        )
    else:
        hint["message"] = (
            "The extracted fund name may include extra wording that is not part of the stored "
            "Commitment Tracker fund name."
        )

    return hint


### Validate whether the requested notice amount fits within the remaining open commitment.
###############################################################################
def validate_commitment(
    extracted_notice: dict[str, Any],
    commitment_df: pd.DataFrame,
    notices: list[dict[str, Any]] | None = None,
    historical_upcoming_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    fund_row = _match_fund_row(commitment_df, extracted_notice.get("fund_name", ""))
    amount = extracted_notice.get("amount")

    if fund_row is None:
        return {
            "status": "fail",
            "message": "Fund name could not be matched to the Commitment Tracker.",
            "matched_fund": None,
            "investor": "",
            "remaining_open_commitment": None,
        }

    remaining = float(fund_row.get("Remaining Open Commitment", 0) or 0)
    investor = str(fund_row.get("Investor", "")).strip()
    matched_fund = str(fund_row.get("Fund Name", "")).strip()
    match_type = str(fund_row.get("_fund_match_type", "exact"))
    workflow_scheduled_total, workflow_scheduled_entries = _scheduled_commitment_usage(
        notices or [],
        matched_fund,
        investor,
    )
    historical_upcoming_total, historical_upcoming_entries = _historical_upcoming_commitment_usage(
        historical_upcoming_df if historical_upcoming_df is not None else pd.DataFrame(),
        matched_fund,
        investor,
    )
    scheduled_total = workflow_scheduled_total + historical_upcoming_total
    scheduled_entries = historical_upcoming_entries + workflow_scheduled_entries
    adjusted_remaining = remaining - scheduled_total

    if amount is None:
        return {
            "status": "fail",
            "message": "Notice amount could not be extracted.",
            "matched_fund": matched_fund,
            "match_type": match_type,
            "investor": investor,
            "remaining_open_commitment": remaining,
            "historical_upcoming_amount": historical_upcoming_total,
            "historical_upcoming_entries": historical_upcoming_entries,
            "workflow_scheduled_amount": workflow_scheduled_total,
            "workflow_scheduled_entries": workflow_scheduled_entries,
            "scheduled_amount": scheduled_total,
            "scheduled_entries": scheduled_entries,
            "adjusted_remaining_open_commitment": adjusted_remaining,
        }

    is_within_limit = float(amount) <= adjusted_remaining
    return {
        "status": "pass" if is_within_limit else "fail",
        "message": (
            "Requested amount is within the remaining open commitment."
            if is_within_limit
            else "Requested amount exceeds the remaining open commitment."
        ),
        "matched_fund": matched_fund,
        "match_type": match_type,
        "investor": investor,
        "remaining_open_commitment": remaining,
        "historical_upcoming_amount": historical_upcoming_total,
        "historical_upcoming_entries": historical_upcoming_entries,
        "workflow_scheduled_amount": workflow_scheduled_total,
        "workflow_scheduled_entries": workflow_scheduled_entries,
        "scheduled_amount": scheduled_total,
        "scheduled_entries": scheduled_entries,
        "adjusted_remaining_open_commitment": adjusted_remaining,
    }


### Validate the extracted investor/limited partner against the matched commitment record.
###############################################################################
def validate_investor(
    extracted_notice: dict[str, Any],
    commitment_result: dict[str, Any],
) -> dict[str, Any]:
    extracted_investor = normalize_text(extracted_notice.get("investor", ""))
    matched_investor = normalize_text(commitment_result.get("investor", ""))

    if commitment_result.get("status") == "fail" and not matched_investor:
        return {
            "status": "fail",
            "message": "Investor / Limited Partner could not be validated because the commitment match failed.",
            "matched_investor": commitment_result.get("investor", ""),
        }

    if not extracted_investor:
        return {
            "status": "fail",
            "message": "Investor / Limited Partner could not be extracted from the notice.",
            "matched_investor": commitment_result.get("investor", ""),
        }

    is_match = extracted_investor == matched_investor
    return {
        "status": "pass" if is_match else "fail",
        "message": (
            "Investor / Limited Partner matches the Commitment Tracker record."
            if is_match
            else "Investor / Limited Partner does not match the Commitment Tracker record."
        ),
        "matched_investor": commitment_result.get("investor", ""),
    }


### Validate the notice IBAN against active approved wire records only.
###############################################################################
def validate_wire(
    extracted_notice: dict[str, Any],
    approved_wires_df: pd.DataFrame,
) -> dict[str, Any]:
    iban = extracted_notice.get("iban", "")
    normalized_notice_iban = normalize_iban(iban)

    if not normalized_notice_iban:
        return {
            "status": "fail",
            "message": "IBAN could not be extracted from the notice.",
            "matched_record": None,
        }

    if approved_wires_df.empty:
        return {
            "status": "fail",
            "message": "Approved wires database is empty.",
            "matched_record": None,
        }

    active_wires_df = approved_wires_df
    if "Status" in approved_wires_df.columns:
        active_wires_df = approved_wires_df[
            approved_wires_df["Status"].astype(str).str.strip().eq("Active")
        ]

    if active_wires_df.empty:
        return {
            "status": "fail",
            "message": "No active approved wire records are available.",
            "matched_record": None,
        }

    matches = active_wires_df[
        active_wires_df["IBAN / Account Number"]
        .astype(str)
        .apply(normalize_iban)
        .eq(normalized_notice_iban)
    ]

    if matches.empty:
        return {
            "status": "fail",
            "message": "IBAN was not found in Approved Wires.",
            "matched_record": None,
        }

    matched_record = matches.iloc[0].to_dict()
    return {
        "status": "pass",
        "message": "IBAN was verified against Approved Wires.",
        "matched_record": matched_record,
    }


### Run the full notice validation and combine commitment and wire checks into one result.
###############################################################################
def validate_notice(
    extracted_notice: dict[str, Any],
    commitment_df: pd.DataFrame,
    approved_wires_df: pd.DataFrame,
    notices: list[dict[str, Any]] | None = None,
    historical_upcoming_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    commitment_result = validate_commitment(
        extracted_notice,
        commitment_df,
        notices=notices,
        historical_upcoming_df=historical_upcoming_df,
    )
    investor_result = validate_investor(extracted_notice, commitment_result)
    wire_result = validate_wire(extracted_notice, approved_wires_df)
    overall_status = (
        "pass"
        if commitment_result["status"] == "pass"
        and investor_result["status"] == "pass"
        and wire_result["status"] == "pass"
        else "fail"
    )

    return {
        "overall_status": overall_status,
        "commitment_check": commitment_result,
        "investor_check": investor_result,
        "wire_check": wire_result,
    }
