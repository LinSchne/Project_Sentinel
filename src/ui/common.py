from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from pandas.io.formats.style import Styler
import streamlit as st

from src.fund_name_utils import normalize_fund_name_for_matching
from src.app_context import APPROVED_WIRES_HIDDEN_COLUMNS


### Return the first existing path from a candidate list.
###############################################################################
def get_first_existing(paths):
    for path in paths:
        if path.exists():
            return path
    return None


### Convert an image file into base64 so it can be embedded directly in Streamlit markup.
###############################################################################
def image_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


### Derive a MIME type from the logo file extension.
###############################################################################
def get_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".svg":
        return "image/svg+xml"
    if suffix == ".png":
        return "image/png"
    if suffix in [".jpg", ".jpeg"]:
        return "image/jpeg"
    return "application/octet-stream"


### Build the HTML snippet used to render the branded sidebar logo.
###############################################################################
def render_logo_html(path: Path, max_width_px: int = 250) -> str:
    mime_type = get_mime_type(path)
    encoded = image_to_base64(path)
    return f"""
        <div class="sidebar-logo-wrap">
            <img
                src="data:{mime_type};base64,{encoded}"
                class="sidebar-logo-img"
                style="max-width: {max_width_px}px;"
                alt="Calibrium logo"
            />
        </div>
    """


### Return the sidebar date/time in the target office timezone.
###############################################################################
def get_sidebar_timestamp() -> tuple[str, str]:
    now = datetime.now(ZoneInfo("Europe/Zurich"))
    return now.strftime("%d.%m.%Y"), now.strftime("%H:%M")


### Render the shared hero/header card used across all pages.
###############################################################################
def render_page_hero(title: str, subtitle: str, eyebrow: str = "") -> None:
    eyebrow_html = f'<div class="hero-eyebrow">{eyebrow}</div>' if eyebrow.strip() else ""
    st.markdown(
        (
            f'<div class="hero-card">'
            f"{eyebrow_html}"
            f'<div class="hero-title">{title}</div>'
            f'<div class="hero-subtitle">{subtitle}</div>'
            f"</div>"
        ),
        unsafe_allow_html=True,
    )


### Return the approved-wire columns that should remain visible in the UI table.
###############################################################################
def visible_approved_wires_columns(df):
    return [col for col in df.columns if col not in APPROVED_WIRES_HIDDEN_COLUMNS]


### Prepare the approved-wires DataFrame for display, including status labels.
###############################################################################
def build_approved_wires_display_df(df):
    display_df = df[visible_approved_wires_columns(df)].copy()
    if "Status" in display_df.columns:
        display_df["Status"] = display_df["Status"].apply(
            lambda value: "🟢 Active" if value == "Active" else "🔴 Inactive"
        )
    return display_df


### Render a simple field/value summary table for notices and wire records.
###############################################################################
def render_record_summary(record, title):
    st.markdown(f"**{title}**")
    summary_df = pd.DataFrame(
        {
            "Field": list(record.keys()),
            "Value": [record.get(field, "") for field in record.keys()],
        }
    )
    st.dataframe(summary_df, use_container_width=True, hide_index=True)


### Render the side-by-side validation summary for commitment and wire checks.
###############################################################################
def render_validation_summary(validation_result):
    commitment = validation_result["commitment_check"]
    investor = validation_result["investor_check"]
    wire = validation_result["wire_check"]

    st.markdown("**Validation Results**")
    result_col1, result_col2, result_col3 = st.columns(3)
    with result_col1:
        if commitment["status"] == "pass":
            st.success(commitment["message"])
        else:
            st.error(commitment["message"])
    with result_col2:
        if investor["status"] == "pass":
            st.success(investor["message"])
        else:
            st.error(investor["message"])
    with result_col3:
        if wire["status"] == "pass":
            st.success(wire["message"])
        else:
            st.error(wire["message"])


### Prepare a notice payload in the format expected by the review/edit dialogs.
###############################################################################
def editable_notice_payload(notice):
    due_date = pd.to_datetime(notice.get("due_date"), errors="coerce")
    return {
        "fund_name": notice.get("fund_name", ""),
        "investor": notice.get("investor", ""),
        "amount": float(notice.get("amount", 0) or 0),
        "currency": notice.get("currency", "EUR"),
        "due_date": due_date,
        "beneficiary_bank": notice.get("beneficiary_bank", ""),
        "iban": notice.get("iban", ""),
        "swift": notice.get("swift", ""),
    }


### Format numeric amounts into the app-wide display style.
###############################################################################
def format_amount_input(value):
    amount = float(value or 0)
    return f"{amount:,.2f}".replace(",", "'")


### Parse a manually edited amount field back into a numeric value.
###############################################################################
def parse_amount_input(value):
    cleaned = str(value).strip().replace("'", "").replace(" ", "")
    if not cleaned:
        return 0.0
    return float(cleaned)


### Combine a currency code and amount into the standard display string.
###############################################################################
def format_currency_display(value, currency="EUR"):
    return f"{currency} {format_amount_input(value)}"


### Format a numeric cell without currency while preserving the treasury display style.
###############################################################################
def format_decimal_display(value):
    if value in (None, "") or pd.isna(value):
        return ""
    return format_amount_input(value)


### Format a date-like cell into the DD.MM.YYYY display used across the app.
###############################################################################
def format_date_display(value):
    if value in (None, "") or pd.isna(value):
        return ""
    parsed = pd.to_datetime(value, errors="coerce")
    return parsed.strftime("%d.%m.%Y") if pd.notna(parsed) else str(value)


### Apply shared amount and date formatting to typed DataFrames without losing sortability.
###############################################################################
def build_table_styler(
    df: pd.DataFrame,
    amount_columns: list[str] | None = None,
    date_columns: list[str] | None = None,
) -> Styler:
    amount_columns = amount_columns or []
    date_columns = date_columns or []

    formatters = {
        column: format_decimal_display for column in amount_columns if column in df.columns
    }
    formatters.update(
        {
            column: format_date_display
            for column in date_columns
            if column in df.columns
        }
    )

    return df.style.format(formatters)


### Shorten long IBANs for compact table rendering.
###############################################################################
def compact_iban_display(value):
    if value in (None, "") or pd.isna(value):
        return "-"
    text = str(value).strip()
    if len(text) <= 18:
        return text
    return f"{text[:10]} ... {text[-6:]}"


### Translate a selected table row into the notice ID used by the edit dialog.
###############################################################################
def open_uploaded_notice_editor_for_checked_rows(checked_rows, notices_df):
    if len(checked_rows) != 1:
        return False
    row_position = checked_rows[0]
    if row_position >= len(notices_df):
        return False
    st.session_state["uploaded_notice_edit_id"] = str(notices_df.iloc[row_position]["id"])
    return True


### Normalize free-text lookup values for matching across datasets.
###############################################################################
def normalize_lookup_text(value):
    if value in (None, "") or pd.isna(value):
        return ""
    return " ".join(str(value).strip().upper().split())


### Normalize IBAN lookup values for matching across datasets.
###############################################################################
def normalize_lookup_iban(value):
    if value in (None, "") or pd.isna(value):
        return ""
    return "".join(str(value).strip().upper().split())


### Find the best matching active approved-wire record for a notice-like record.
###############################################################################
def find_matching_approved_wire_record(record, approved_wires_df):
    if approved_wires_df.empty:
        return None

    active_wires_df = approved_wires_df.copy()
    if "Status" in active_wires_df.columns:
        active_wires_df = active_wires_df[
            active_wires_df["Status"].astype(str).str.strip().eq("Active")
        ]

    if active_wires_df.empty:
        return None

    fund_name = normalize_lookup_text(record.get("fund_name", ""))
    normalized_numeric_fund_name = normalize_fund_name_for_matching(record.get("fund_name", ""))
    currency = normalize_lookup_text(record.get("currency", ""))
    iban = normalize_lookup_iban(record.get("iban", ""))
    beneficiary_bank = normalize_lookup_text(record.get("beneficiary_bank", ""))

    if iban and "IBAN / Account Number" in active_wires_df.columns:
        iban_matches = active_wires_df[
            active_wires_df["IBAN / Account Number"].apply(normalize_lookup_iban).eq(iban)
        ]
        if currency and not iban_matches.empty and "Currency" in iban_matches.columns:
            currency_matches = iban_matches[
                iban_matches["Currency"].apply(normalize_lookup_text).eq(currency)
            ]
            if not currency_matches.empty:
                return currency_matches.iloc[0].to_dict()
        if not iban_matches.empty:
            return iban_matches.iloc[0].to_dict()

    if not fund_name:
        if beneficiary_bank and "Beneficiary Bank" in active_wires_df.columns:
            bank_matches = active_wires_df[
                active_wires_df["Beneficiary Bank"]
                .apply(normalize_lookup_text)
                .eq(beneficiary_bank)
            ]
            if currency and not bank_matches.empty and "Currency" in bank_matches.columns:
                currency_matches = bank_matches[
                    bank_matches["Currency"].apply(normalize_lookup_text).eq(currency)
                ]
                if not currency_matches.empty:
                    return currency_matches.iloc[0].to_dict()
            if not bank_matches.empty:
                return bank_matches.iloc[0].to_dict()
        return None

    candidate_df = active_wires_df[
        active_wires_df["Fund Name"].apply(normalize_lookup_text).eq(fund_name)
    ]

    if currency and not candidate_df.empty and "Currency" in candidate_df.columns:
        currency_matches = candidate_df[
            candidate_df["Currency"].apply(normalize_lookup_text).eq(currency)
        ]
        if not currency_matches.empty:
            return currency_matches.iloc[0].to_dict()

    if not candidate_df.empty:
        return candidate_df.iloc[0].to_dict()

    numeric_candidate_df = active_wires_df[
        active_wires_df["Fund Name"]
        .astype(str)
        .apply(normalize_fund_name_for_matching)
        .eq(normalized_numeric_fund_name)
    ]

    if currency and not numeric_candidate_df.empty and "Currency" in numeric_candidate_df.columns:
        currency_matches = numeric_candidate_df[
            numeric_candidate_df["Currency"].apply(normalize_lookup_text).eq(currency)
        ]
        if not currency_matches.empty:
            return currency_matches.iloc[0].to_dict()

    if not numeric_candidate_df.empty:
        return numeric_candidate_df.iloc[0].to_dict()

    fallback_df = active_wires_df[
        active_wires_df["Fund Name"].apply(
            lambda value: fund_name in normalize_lookup_text(value)
            or normalize_lookup_text(value) in fund_name
        )
    ]

    if currency and not fallback_df.empty and "Currency" in fallback_df.columns:
        currency_matches = fallback_df[
            fallback_df["Currency"].apply(normalize_lookup_text).eq(currency)
        ]
        if not currency_matches.empty:
            return currency_matches.iloc[0].to_dict()

    if not fallback_df.empty:
        return fallback_df.iloc[0].to_dict()

    return None


### Fill missing notice bank fields from the matched approved-wire reference data.
###############################################################################
def enrich_record_with_approved_wire(record, approved_wires_df):
    enriched_record = dict(record)
    if (
        enriched_record.get("iban")
        and enriched_record.get("swift")
        and enriched_record.get("beneficiary_bank")
    ):
        return enriched_record

    matched_wire = find_matching_approved_wire_record(enriched_record, approved_wires_df)
    if not matched_wire:
        return enriched_record

    if not enriched_record.get("beneficiary_bank"):
        enriched_record["beneficiary_bank"] = matched_wire.get("Beneficiary Bank", "")
    if not enriched_record.get("iban"):
        enriched_record["iban"] = matched_wire.get("IBAN / Account Number", "")
    if not enriched_record.get("swift"):
        enriched_record["swift"] = matched_wire.get("Swift/BIC", "")

    return enriched_record


### Build non-invasive wire suggestions when the reference data contains richer details.
###############################################################################
def build_approved_wire_suggestions(record, approved_wires_df):
    matched_wire = find_matching_approved_wire_record(record, approved_wires_df)
    if not matched_wire:
        return {}

    suggestions = {}
    if not str(record.get("swift", "")).strip() and str(matched_wire.get("Swift/BIC", "")).strip():
        suggestions["SWIFT/BIC"] = matched_wire.get("Swift/BIC", "")
    if not str(record.get("beneficiary_bank", "")).strip() and str(
        matched_wire.get("Beneficiary Bank", "")
    ).strip():
        suggestions["Beneficiary Bank"] = matched_wire.get("Beneficiary Bank", "")
    if not str(record.get("iban", "")).strip() and str(
        matched_wire.get("IBAN / Account Number", "")
    ).strip():
        suggestions["IBAN"] = matched_wire.get("IBAN / Account Number", "")
    return suggestions


### Build the minimal context object needed for the executed-call email template.
###############################################################################
def build_executed_email_context(row):
    due_date = row.get("due_date") or row.get("value_date") or row.get("executed_at") or ""
    return {
        "id": row.get("id", ""),
        "fund_name": row.get("fund_name", ""),
        "investor": row.get("investor", ""),
        "amount": row.get("amount", 0),
        "currency": row.get("currency", "EUR"),
        "due_date": due_date,
        "iban": row.get("iban", ""),
        "swift": row.get("swift", ""),
    }


### Map a selected executed-call table row to the stored email-dialog notice ID.
###############################################################################
def open_executed_email_for_checked_rows(checked_rows, executed_df):
    if len(checked_rows) != 1:
        return False
    row_position = checked_rows[0]
    if row_position >= len(executed_df):
        return False
    selected_notice_id = executed_df.iloc[row_position]["id"]
    st.session_state["executed_email_notice_id"] = selected_notice_id
    return True


### Mark an executed notice as email-confirmed and store the timestamp in session state.
###############################################################################
def mark_executed_email_as_sent(notice_id):
    sent_notice_ids = set(st.session_state.get("executed_email_sent_ids", []))
    sent_notice_ids.add(str(notice_id))
    st.session_state["executed_email_sent_ids"] = sorted(sent_notice_ids)
    sent_timestamps = dict(st.session_state.get("executed_email_sent_at", {}))
    sent_timestamps[str(notice_id)] = datetime.now(ZoneInfo("Europe/Zurich")).strftime(
        "%d.%m.%Y %H:%M"
    )
    st.session_state["executed_email_sent_at"] = sent_timestamps
    st.session_state["executed_calls_table_nonce"] = (
        st.session_state.get("executed_calls_table_nonce", 0) + 1
    )
    st.session_state.pop("executed_email_notice_id", None)
