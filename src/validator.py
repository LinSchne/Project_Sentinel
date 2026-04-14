from __future__ import annotations

from typing import Any

import pandas as pd

from src.approved_wires import normalize_iban, normalize_text


def _match_fund_row(commitment_df: pd.DataFrame, fund_name: str) -> dict[str, Any] | None:
    if commitment_df.empty or not fund_name:
        return None

    normalized_target = normalize_text(fund_name)
    exact_matches = commitment_df[
        commitment_df["Fund Name"].astype(str).apply(normalize_text).eq(normalized_target)
    ]
    if not exact_matches.empty:
        return exact_matches.iloc[0].to_dict()

    partial_matches = commitment_df[
        commitment_df["Fund Name"].astype(str).apply(
            lambda value: normalized_target in normalize_text(value)
            or normalize_text(value) in normalized_target
        )
    ]
    if not partial_matches.empty:
        return partial_matches.iloc[0].to_dict()

    return None


def validate_commitment(
    extracted_notice: dict[str, Any],
    commitment_df: pd.DataFrame,
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

    if amount is None:
        return {
            "status": "fail",
            "message": "Notice amount could not be extracted.",
            "matched_fund": matched_fund,
            "investor": investor,
            "remaining_open_commitment": remaining,
        }

    is_within_limit = float(amount) <= remaining
    return {
        "status": "pass" if is_within_limit else "fail",
        "message": (
            "Requested amount is within the remaining open commitment."
            if is_within_limit
            else "Requested amount exceeds the remaining open commitment."
        ),
        "matched_fund": matched_fund,
        "investor": investor,
        "remaining_open_commitment": remaining,
    }


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

    matches = approved_wires_df[
        approved_wires_df["IBAN / Account Number"]
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


def validate_notice(
    extracted_notice: dict[str, Any],
    commitment_df: pd.DataFrame,
    approved_wires_df: pd.DataFrame,
) -> dict[str, Any]:
    commitment_result = validate_commitment(extracted_notice, commitment_df)
    wire_result = validate_wire(extracted_notice, approved_wires_df)
    overall_status = (
        "pass"
        if commitment_result["status"] == "pass" and wire_result["status"] == "pass"
        else "fail"
    )

    return {
        "overall_status": overall_status,
        "commitment_check": commitment_result,
        "wire_check": wire_result,
    }
