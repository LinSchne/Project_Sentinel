from pathlib import Path
import base64
from datetime import datetime
import shutil
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

from src.approved_wires import (
    add_approved_wire_record,
    apply_approved_wires_filters,
    editable_columns_for_ui,
    find_duplicate_record,
    load_approved_wires,
    reset_approved_wires_to_source,
    save_approved_wires,
    update_editable_fields,
)
from src.commitment_tracker import (
    apply_workflow_updates,
    dashboard_metrics,
    ensure_commitment_dashboard_workbook,
    load_commitment_dashboard,
    prepare_commitment_tracker_display,
    prepare_executed_capital_calls_display,
    prepare_upcoming_capital_calls_display,
    reset_commitment_dashboard_to_source,
)
from src.email_templates import generate_payment_confirmation_email
from src.extractor import extract_notice_fields
from src.pdf_reader import extract_text_from_pdf_bytes
from src.validator import validate_notice
from src.workflow import (
    accept_notice_record,
    approve_notice,
    create_notice_record,
    delete_notice_by_id,
    get_notice_by_id,
    load_workflow_state,
    notices_to_dataframe,
    reset_workflow_state,
    save_workflow_state,
    set_notice_validation,
    upsert_notice,
)

BASE_DIR = Path(__file__).resolve().parent
BRANDING_DIR = BASE_DIR / "assets" / "branding"

LOGO_CANDIDATES = [
    BRANDING_DIR / "calibrium_logo.svg",
    BRANDING_DIR / "calibrium_logo_clean.png",
    BRANDING_DIR / "calibrium_logo.png",
]

LOGO_ICON = BRANDING_DIR / "calibrium_icon.png"
WORKFLOW_STATE_PATH = BASE_DIR / "data" / "processed" / "workflow_state.json"
UPLOADS_DIR = BASE_DIR / "data" / "processed" / "uploads"


def get_first_existing(paths):
    for path in paths:
        if path.exists():
            return path
    return None


def image_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def get_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".svg":
        return "image/svg+xml"
    if suffix == ".png":
        return "image/png"
    if suffix in [".jpg", ".jpeg"]:
        return "image/jpeg"
    return "application/octet-stream"


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


def get_sidebar_timestamp() -> tuple[str, str]:
    now = datetime.now(ZoneInfo("Europe/Zurich"))
    return now.strftime("%d.%m.%Y"), now.strftime("%H:%M")


def render_page_hero(title: str, subtitle: str, eyebrow: str = "") -> None:
    eyebrow_html = (
        f'<div class="hero-eyebrow">{eyebrow}</div>'
        if eyebrow.strip()
        else ""
    )
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


LOGO_FILE = get_first_existing(LOGO_CANDIDATES)
APPROVED_WIRES_HIDDEN_COLUMNS = {"Comment", "Created at", "Created At"}
COMMON_CURRENCY_CODES = [
    "EUR",
    "USD",
    "GBP",
    "CHF",
    "JPY",
    "CAD",
    "AUD",
    "NZD",
    "SEK",
    "NOK",
    "DKK",
    "CZK",
    "PLN",
    "HUF",
    "RON",
    "TRY",
    "AED",
    "SAR",
    "QAR",
    "KWD",
    "BHD",
    "SGD",
    "HKD",
    "CNY",
    "CNH",
    "INR",
    "KRW",
    "TWD",
    "ZAR",
    "BRL",
    "MXN",
    "ILS",
    "Other",
]


def visible_approved_wires_columns(df):
    return [col for col in df.columns if col not in APPROVED_WIRES_HIDDEN_COLUMNS]


def build_approved_wires_display_df(df):
    display_df = df[visible_approved_wires_columns(df)].copy()
    if "Status" in display_df.columns:
        display_df["Status"] = display_df["Status"].apply(
            lambda value: "🟢 Active" if value == "Active" else "🔴 Inactive"
        )
    return display_df


def reset_approved_wire_form():
    st.session_state["approved_wire_fund_name"] = ""
    st.session_state["approved_wire_beneficiary_bank"] = ""
    st.session_state["approved_wire_swift_bic"] = ""
    st.session_state["approved_wire_iban_account_number"] = ""
    st.session_state["approved_wire_currency"] = "EUR"
    st.session_state["approved_wire_currency_choice"] = "EUR"
    st.session_state["approved_wire_currency_other"] = ""
    st.session_state["approved_wire_status"] = "Active"


def render_record_summary(record, title):
    st.markdown(f"**{title}**")
    summary_df = pd.DataFrame(
        {
            "Field": list(record.keys()),
            "Value": [record.get(field, "") for field in record.keys()],
        }
    )
    st.dataframe(summary_df, use_container_width=True, hide_index=True)


def clear_approved_wire_state():
    for key in [
        "approved_wire_show_add_dialog",
        "approved_wire_pending_record",
        "approved_wire_is_duplicate",
        "approved_wire_duplicate_details",
    ]:
        st.session_state.pop(key, None)


def clear_commitment_tracker_state():
    for key in [
        "commitment_tracker_show_reset_dialog",
        "commitment_tracker_search",
        "commitment_tracker_investors",
        "commitment_tracker_funds",
    ]:
        st.session_state.pop(key, None)


def clear_uploaded_notice_state():
    for key in [
        "current_notice_id",
        "upload_notice_feedback",
        "validation_feedback",
        "uploaded_file",
        "show_notice_reset_dialog",
        "uploaded_notice_edit_id",
        "executed_email_notice_id",
        "executed_calls_last_opened_id",
        "executed_email_sent_ids",
        "executed_email_sent_at",
    ]:
        st.session_state.pop(key, None)


def workflow_state():
    return load_workflow_state(WORKFLOW_STATE_PATH)


def persist_workflow_state(state):
    save_workflow_state(WORKFLOW_STATE_PATH, state)


def clear_uploaded_notice_files():
    if UPLOADS_DIR.exists():
        shutil.rmtree(UPLOADS_DIR)


def save_uploaded_notice_file(uploaded_file) -> Path:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    target_path = UPLOADS_DIR / f"{timestamp}_{uploaded_file.name}"
    target_path.write_bytes(uploaded_file.getvalue())
    return target_path


def render_validation_summary(validation_result):
    commitment = validation_result["commitment_check"]
    wire = validation_result["wire_check"]

    st.markdown("**Validation Results**")
    result_col1, result_col2 = st.columns(2)
    with result_col1:
        if commitment["status"] == "pass":
            st.success(commitment["message"])
        else:
            st.error(commitment["message"])
    with result_col2:
        if wire["status"] == "pass":
            st.success(wire["message"])
        else:
            st.error(wire["message"])


def editable_notice_payload(notice):
    due_date = pd.to_datetime(notice.get("due_date"), errors="coerce")
    return {
        "fund_name": notice.get("fund_name", ""),
        "amount": float(notice.get("amount", 0) or 0),
        "currency": notice.get("currency", "EUR"),
        "due_date": due_date,
        "beneficiary_bank": notice.get("beneficiary_bank", ""),
        "iban": notice.get("iban", ""),
        "swift": notice.get("swift", ""),
    }


def format_amount_input(value):
    amount = float(value or 0)
    return f"{amount:,.2f}".replace(",", "'")


def parse_amount_input(value):
    cleaned = str(value).strip().replace("'", "").replace(" ", "")
    if not cleaned:
        return 0.0
    return float(cleaned)


def format_currency_display(value, currency="EUR"):
    return f"{currency} {format_amount_input(value)}"


def compact_iban_display(value):
    if value in (None, "") or pd.isna(value):
        return "-"
    text = str(value).strip()
    if len(text) <= 18:
        return text
    return f"{text[:10]} ... {text[-6:]}"


def open_uploaded_notice_editor_for_checked_rows(checked_rows, notices_df):
    if len(checked_rows) != 1:
        return False
    row_position = checked_rows[0]
    if row_position >= len(notices_df):
        return False
    st.session_state["uploaded_notice_edit_id"] = str(notices_df.iloc[row_position]["id"])
    return True


def normalize_lookup_text(value):
    if value in (None, "") or pd.isna(value):
        return ""
    return " ".join(str(value).strip().upper().split())


def normalize_lookup_iban(value):
    if value in (None, "") or pd.isna(value):
        return ""
    return "".join(str(value).strip().upper().split())


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
                active_wires_df["Beneficiary Bank"].apply(normalize_lookup_text).eq(beneficiary_bank)
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


def enrich_record_with_approved_wire(record, approved_wires_df):
    enriched_record = dict(record)
    if enriched_record.get("iban") and enriched_record.get("swift"):
        return enriched_record

    matched_wire = find_matching_approved_wire_record(enriched_record, approved_wires_df)
    if not matched_wire:
        return enriched_record

    if not enriched_record.get("iban"):
        enriched_record["iban"] = matched_wire.get("IBAN / Account Number", "")
    if not enriched_record.get("swift"):
        enriched_record["swift"] = matched_wire.get("Swift/BIC", "")

    return enriched_record


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


def build_executed_email_context(row):
    due_date = row.get("due_date") or row.get("value_date") or row.get("executed_at") or ""
    return {
        "id": row.get("id", ""),
        "fund_name": row.get("fund_name", ""),
        "amount": row.get("amount", 0),
        "currency": row.get("currency", "EUR"),
        "due_date": due_date,
        "iban": row.get("iban", ""),
        "swift": row.get("swift", ""),
    }


def open_executed_email_for_checked_rows(checked_rows, executed_df):
    if len(checked_rows) != 1:
        return False
    row_position = checked_rows[0]
    if row_position >= len(executed_df):
        return False
    selected_notice_id = executed_df.iloc[row_position]["id"]
    st.session_state["executed_email_notice_id"] = selected_notice_id
    st.session_state["executed_calls_last_opened_id"] = selected_notice_id
    return True


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


@st.cache_data(show_spinner=False)
def get_commitment_dashboard(source_workbook_path: str, source_workbook_mtime: float):
    _ = source_workbook_mtime
    return load_commitment_dashboard(Path(source_workbook_path))


@st.dialog("Add Approved Wire")
def approved_wire_confirmation_dialog(master_df, managed_workbook):
    pending_record = st.session_state.get("approved_wire_pending_record")

    if not pending_record:
        st.write("No pending approved wire record found.")
        if st.button("Close", use_container_width=True):
            st.rerun()
        return

    render_record_summary(pending_record, "Entered record")

    duplicate_details = st.session_state.get("approved_wire_duplicate_details")

    if st.session_state.get("approved_wire_is_duplicate"):
        matched_columns = duplicate_details.get("matched_columns", []) if duplicate_details else []
        matched_columns_text = ", ".join(matched_columns) if matched_columns else "IBAN / Account Number"
        st.warning(
            f"Duplicate detected. A matching record was found based on: {matched_columns_text}."
        )
        if duplicate_details and duplicate_details.get("matched_row"):
            render_record_summary(duplicate_details["matched_row"], "Existing matching record")
        if st.button("Close", use_container_width=True):
            clear_approved_wire_state()
            st.rerun()
        return

    st.info("No duplicate found. Would you like to add these CWire instructions?")

    confirm_col, cancel_col = st.columns(2)

    with confirm_col:
        if st.button("Confirm", use_container_width=True):
            updated_df = add_approved_wire_record(master_df, pending_record)
            save_approved_wires(updated_df, managed_workbook)
            clear_approved_wire_state()
            reset_approved_wire_form()
            st.session_state["approved_wire_feedback"] = (
                "New approved wire record added successfully."
            )
            st.rerun()

    with cancel_col:
        if st.button("Cancel", use_container_width=True):
            clear_approved_wire_state()
            st.rerun()


@st.dialog("Add New Approved Wire")
def approved_wire_add_dialog(master_df):
    st.caption("Please enter the new approved wire details.")

    with st.form("approved_wire_add_dialog_form", clear_on_submit=False):
        add_col1, add_col2, add_col3 = st.columns(3)

        with add_col1:
            fund_name = st.text_input("Fund Name", key="approved_wire_fund_name")
            beneficiary_bank = st.text_input(
                "Beneficiary Bank",
                key="approved_wire_beneficiary_bank",
            )

        with add_col2:
            swift_bic = st.text_input("Swift/BIC", key="approved_wire_swift_bic")
            iban_account_number = st.text_input(
                "IBAN / Account Number",
                key="approved_wire_iban_account_number",
            )

        with add_col3:
            currency_choice = st.selectbox(
                "Currency",
                options=COMMON_CURRENCY_CODES,
                key="approved_wire_currency_choice",
            )
            currency_other = ""
            if currency_choice == "Other":
                currency_other = st.text_input(
                    "Other Currency Code",
                    key="approved_wire_currency_other",
                    placeholder="e.g. THB",
                )
            status = st.selectbox(
                "Status",
                options=["Active", "Inactive"],
                key="approved_wire_status",
            )

        action_col1, action_col2 = st.columns(2)
        submitted = action_col1.form_submit_button("Review Record", use_container_width=True)
        canceled = action_col2.form_submit_button("Cancel", use_container_width=True)

        if canceled:
            st.session_state.pop("approved_wire_show_add_dialog", None)
            reset_approved_wire_form()
            st.rerun()

        if submitted:
            currency = (
                currency_other.strip().upper()
                if currency_choice == "Other"
                else currency_choice
            )
            new_record = {
                "Fund Name": fund_name,
                "Beneficiary Bank": beneficiary_bank,
                "Swift/BIC": swift_bic,
                "IBAN / Account Number": iban_account_number,
                "Currency": currency,
                "Status": status,
            }

            duplicate_details = find_duplicate_record(master_df, new_record)
            st.session_state["approved_wire_pending_record"] = new_record
            st.session_state["approved_wire_is_duplicate"] = duplicate_details is not None
            st.session_state["approved_wire_duplicate_details"] = duplicate_details
            st.session_state.pop("approved_wire_show_add_dialog", None)
            st.rerun()


@st.dialog("Reset Approved Wires")
def approved_wires_reset_dialog(source_workbook, managed_workbook):
    st.warning(
        "This will reset Approved Wires to the original records from the source Excel file."
    )
    st.caption("All manual changes and added records in the current managed list will be replaced.")

    confirm_col, cancel_col = st.columns(2)

    with confirm_col:
        if st.button("Reset List", use_container_width=True, type="primary"):
            reset_approved_wires_to_source(source_workbook, managed_workbook)
            clear_approved_wire_state()
            reset_approved_wire_form()
            st.session_state["approved_wire_feedback"] = (
                "Approved wires were reset to the original Excel source."
            )
            st.session_state.pop("approved_wire_show_reset_dialog", None)
            st.rerun()

    with cancel_col:
        if st.button("Cancel Reset", use_container_width=True):
            st.session_state.pop("approved_wire_show_reset_dialog", None)
            st.rerun()


@st.dialog("Reset Commitment Tracker")
def commitment_tracker_reset_dialog(source_workbook, managed_workbook):
    st.warning(
        "This will reset the Commitment Tracker workbook to the original reference Excel file."
    )
    st.caption("All prototype changes in the managed workbook will be replaced.")

    confirm_col, cancel_col = st.columns(2)

    with confirm_col:
        if st.button("Reset Workbook", use_container_width=True, type="primary"):
            reset_commitment_dashboard_to_source(source_workbook, managed_workbook)
            clear_commitment_tracker_state()
            reset_workflow_state(WORKFLOW_STATE_PATH)
            clear_uploaded_notice_files()
            clear_uploaded_notice_state()
            st.session_state["commitment_tracker_feedback"] = (
                "Commitment Tracker workbook was reset to the original source and all new capital calls were deleted."
            )
            st.rerun()

    with cancel_col:
        if st.button("Cancel Reset", use_container_width=True):
            st.session_state.pop("commitment_tracker_show_reset_dialog", None)
            st.rerun()


@st.dialog("Delete Uploaded Notices")
def uploaded_notices_reset_dialog():
    st.warning("This will delete all uploaded notices from the prototype workflow.")
    st.caption("Validation, executed notices, and generated email selections based on uploaded notices will be cleared.")

    confirm_col, cancel_col = st.columns(2)

    with confirm_col:
        if st.button("Delete All Notices", use_container_width=True, type="primary"):
            reset_workflow_state(WORKFLOW_STATE_PATH)
            clear_uploaded_notice_files()
            clear_uploaded_notice_state()
            st.session_state["upload_notice_feedback"] = "All uploaded notices were deleted."
            st.rerun()

    with cancel_col:
        if st.button("Cancel", use_container_width=True):
            st.session_state.pop("show_notice_reset_dialog", None)
            st.rerun()


@st.dialog("Payment Confirmation Email")
def executed_email_dialog(notice):
    email_text = generate_payment_confirmation_email(notice or {})
    st.caption("Please review all the information.")
    st.text_area(
        "Copyable email template",
        value=email_text,
        height=260,
        key=f"executed_email_dialog_{notice.get('id', 'notice')}",
    )
    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button("Copy and Mark as Sent", use_container_width=True, type="primary"):
            mark_executed_email_as_sent(notice.get("id", ""))
            st.rerun()
    with action_col2:
        if st.button("Close", use_container_width=True):
            st.session_state.pop("executed_email_notice_id", None)
            st.rerun()


@st.dialog("Review Extracted Data")
def review_notice_dialog(review_notice):
    st.info(
        "Please verify the extracted data. If everything is correct, accept it. If something is wrong, edit the fields below and then accept."
    )

    editable = editable_notice_payload(review_notice)

    with st.form("notice_review_form", clear_on_submit=False):
        review_col1, review_col2 = st.columns(2)

        with review_col1:
            reviewed_fund_name = st.text_input("Fund Name", value=editable["fund_name"])
            reviewed_amount = st.text_input(
                "Amount",
                value=format_amount_input(editable["amount"]),
            )
            reviewed_currency = st.text_input("Currency", value=editable["currency"])
            reviewed_due_date = st.text_input(
                "Due Date",
                value=editable["due_date"].strftime("%d.%m.%Y")
                if pd.notna(editable["due_date"])
                else "",
            )

        with review_col2:
            reviewed_beneficiary_bank = st.text_input(
                "Beneficiary Bank",
                value=editable["beneficiary_bank"],
            )
            reviewed_iban = st.text_input("IBAN", value=editable["iban"])
            reviewed_swift = st.text_input("SWIFT/BIC", value=editable["swift"])

        review_action_col1, review_action_col2 = st.columns(2)
        accept_clicked = review_action_col1.form_submit_button(
            "Accept Notice Data",
            use_container_width=True,
        )
        delete_clicked = review_action_col2.form_submit_button(
            "Delete Notice",
            use_container_width=True,
        )

        if accept_clicked:
            state = workflow_state()
            updated_notice = accept_notice_record(
                review_notice,
                {
                    "fund_name": reviewed_fund_name,
                    "amount": parse_amount_input(reviewed_amount),
                    "currency": reviewed_currency,
                    "due_date": pd.to_datetime(
                        reviewed_due_date,
                        dayfirst=True,
                        errors="coerce",
                    ),
                    "beneficiary_bank": reviewed_beneficiary_bank,
                    "iban": reviewed_iban,
                    "swift": reviewed_swift,
                },
            )
            upsert_notice(state, updated_notice)
            persist_workflow_state(state)
            st.session_state["current_notice_id"] = updated_notice["id"]
            st.session_state["upload_notice_feedback"] = (
                "Notice data accepted and moved to Validation."
            )
            st.rerun()

        if delete_clicked:
            state = workflow_state()
            updated_state = delete_notice_by_id(state, review_notice["id"])
            persist_workflow_state(updated_state)
            st.session_state.pop("current_notice_id", None)
            st.session_state["upload_notice_feedback"] = "Review notice deleted."
            st.rerun()


@st.dialog("Edit Uploaded Notice")
def edit_uploaded_notice_dialog(notice):
    editable = editable_notice_payload(notice)

    with st.form("edit_uploaded_notice_form", clear_on_submit=False):
        edit_col1, edit_col2 = st.columns(2)

        with edit_col1:
            edited_fund_name = st.text_input("Fund Name", value=editable["fund_name"])
            edited_amount = st.text_input("Amount", value=format_amount_input(editable["amount"]))
            edited_currency = st.text_input("Currency", value=editable["currency"])
            edited_due_date = st.text_input(
                "Due Date",
                value=editable["due_date"].strftime("%d.%m.%Y")
                if pd.notna(editable["due_date"])
                else "",
            )

        with edit_col2:
            edited_bank = st.text_input("Bank", value=editable["beneficiary_bank"] or "-")
            edited_iban = st.text_input("IBAN", value=editable["iban"] or "-")
            edited_swift = st.text_input("SWIFT/BIC", value=editable["swift"] or "-")

        save_col, cancel_col = st.columns(2)
        save_clicked = save_col.form_submit_button("Save Notice Changes", use_container_width=True)
        cancel_clicked = cancel_col.form_submit_button("Close", use_container_width=True)

        if save_clicked:
            state = workflow_state()
            updated_notice = dict(notice)
            updated_notice.update(
                {
                    "fund_name": edited_fund_name,
                    "amount": parse_amount_input(edited_amount),
                    "currency": edited_currency,
                    "due_date": pd.to_datetime(
                        edited_due_date,
                        dayfirst=True,
                        errors="coerce",
                    ),
                    "beneficiary_bank": "" if edited_bank.strip() == "-" else edited_bank.strip(),
                    "iban": "" if edited_iban.strip() == "-" else edited_iban.strip(),
                    "swift": "" if edited_swift.strip() == "-" else edited_swift.strip(),
                }
            )
            upsert_notice(state, updated_notice)
            persist_workflow_state(state)
            st.session_state["upload_notice_feedback"] = "Uploaded notice updated successfully."
            st.session_state.pop("uploaded_notice_edit_id", None)
            st.rerun()

        if cancel_clicked:
            st.session_state.pop("uploaded_notice_edit_id", None)
            st.rerun()

st.set_page_config(
    page_title="Project Sentinel",
    page_icon=str(LOGO_ICON) if LOGO_ICON.exists() else "C",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container,
        div[data-testid="stAppViewBlockContainer"] {
            padding-top: 2.6rem;
            padding-bottom: 2rem;
            padding-left: 2rem;
            padding-right: 2rem;
            overflow: visible !important;
        }

        div[data-testid="stDialog"] div[role="dialog"] {
            width: min(1100px, 92vw);
        }

        div[data-testid="stFileUploader"] > section {
            padding: 0.95rem 1rem;
            min-height: 5.25rem;
            border-radius: 18px;
        }

        div[data-testid="stFileUploaderDropzone"] {
            padding: 0.7rem 0.85rem;
            min-height: 3.9rem;
            display: flex;
            align-items: center;
        }

        section[data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e6e9f2;
        }

        div[data-testid="stSidebarUserContent"] {
            padding-top: 0.8rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .sidebar-logo-wrap {
            display: flex;
            justify-content: center;
            align-items: center;
            padding-top: 0.25rem;
            padding-bottom: 0.5rem;
        }

        .sidebar-logo-img {
            display: block;
            width: 100%;
            height: auto;
            object-fit: contain;
        }

        .sidebar-timestamp {
            text-align: center;
            margin-top: 0.15rem;
            margin-bottom: 0.85rem;
        }

        .sidebar-timestamp-label {
            color: #7a8499;
            font-size: 0.76rem;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.2rem;
        }

        .sidebar-timestamp-date {
            color: #1f2a44;
            font-size: 1rem;
            font-weight: 700;
            line-height: 1.25;
        }

        .sidebar-timestamp-time {
            color: #4b5f9e;
            font-size: 0.92rem;
            font-weight: 600;
            line-height: 1.3;
        }

        .sidebar-bottom-line {
            margin-top: 1.5rem;
            padding-top: 1rem;
            border-top: 1px solid #e6e9f2;
            text-align: center;
        }

        .sidebar-office-title {
            color: #3f56a6;
            font-size: 0.98rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
            line-height: 1.3;
            text-align: center;
        }

        .sidebar-office-details {
            color: #5f6b85;
            font-size: 0.83rem;
            line-height: 1.55;
            text-align: center;
        }

        .hero-card {
            background: linear-gradient(135deg, #f8faff 0%, #eef3ff 100%);
            border: 1px solid #dfe7fb;
            border-radius: 18px;
            padding: 28px 30px;
            margin-top: 0.35rem;
            margin-bottom: 1.25rem;
            overflow: visible !important;
        }

        .hero-eyebrow {
            color: #4b5f9e;
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            margin-bottom: 0.4rem;
        }

        .hero-title {
            color: #18233a;
            font-size: 3rem;
            font-weight: 800;
            line-height: 1.05;
            margin-bottom: 0.5rem;
            word-break: normal;
        }

        .hero-subtitle {
            color: #33415c;
            font-size: 1.15rem;
            font-weight: 500;
            margin-bottom: 0.9rem;
            line-height: 1.4;
        }

        .hero-text {
            color: #4a556f;
            font-size: 1rem;
            line-height: 1.7;
            max-width: 900px;
        }

        .section-title {
            color: #1f2a44;
            font-size: 1.35rem;
            font-weight: 700;
            margin-top: 0.2rem;
            margin-bottom: 0.8rem;
        }

        .page-title {
            color: #1f2a44;
            font-size: 2.9rem;
            font-weight: 800;
            line-height: 1.05;
            margin-top: 0.1rem;
            margin-bottom: 1.1rem;
        }

        .mini-card {
            background: #ffffff;
            border: 1px solid #e7ebf3;
            border-radius: 16px;
            padding: 18px 18px;
            min-height: 180px;
            height: 100%;
            display: flex;
            flex-direction: column;
        }

        .mini-card-muted {
            background: #f5f6f8;
            border-color: #dde2eb;
        }

        .mini-label {
            color: #6b7280;
            font-size: 0.9rem;
            margin-bottom: 0.35rem;
        }

        .mini-value {
            color: #1f2a44;
            font-size: 1.8rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 0.4rem;
        }

        .mini-note {
            color: #6b7280;
            font-size: 0.92rem;
            line-height: 1.45;
            margin-top: auto;
        }

        .content-card {
            background: #ffffff;
            border: 1px solid #e7ebf3;
            border-radius: 18px;
            padding: 22px 24px;
            margin-top: 0.5rem;
        }

    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    if LOGO_FILE is not None:
        st.markdown(render_logo_html(LOGO_FILE, max_width_px=260), unsafe_allow_html=True)

    sidebar_date, sidebar_time = get_sidebar_timestamp()
    st.markdown(
        f"""
        <div class="sidebar-timestamp">
            <div class="sidebar-timestamp-label">Current Time</div>
            <div class="sidebar-timestamp-date">{sidebar_date}</div>
            <div class="sidebar-timestamp-time">{sidebar_time} CET/CEST</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    page = st.radio(
        "Navigation",
        [
            "Overview",
            "Approved Wires",
            "Commitment Tracker",
            "Upload Notice",
            "Validation",
            "Executed Calls",
        ],
    )

    st.markdown(
        """
        <div class="sidebar-bottom-line">
            <div class="sidebar-office-title">Private Investment Office</div>
            <div class="sidebar-office-details">
                Calibrium AG · Beethovenstrasse 33<br>
                CH-8002 Zürich · +41 55 511 12 22
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

if page == "Overview":
    source_workbook = BASE_DIR / "data" / "reference" / "IO_Case_study_Capital_Calls.xlsx"
    managed_workbook = BASE_DIR / "data" / "processed" / "capital_calls_master.xlsx"
    active_workbook = ensure_commitment_dashboard_workbook(source_workbook, managed_workbook)
    dashboard_data = get_commitment_dashboard(
        str(active_workbook),
        active_workbook.stat().st_mtime,
    )
    state = workflow_state()
    dashboard_data = apply_workflow_updates(dashboard_data, state.get("notices", []))
    metrics = dashboard_metrics(dashboard_data)

    render_page_hero(
        "Project Sentinel",
        "Private Equity capital call handling with extraction, controls, and approval workflow.",
        eyebrow="Treasury Operations Automation",
    )

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    with metric_col1:
        st.markdown(
            f"""
            <div class="mini-card">
                <div class="mini-label">Funds</div>
                <div class="mini-value">{metrics["Funds"]}</div>
                <div class="mini-note">Tracked funds in the commitment sheet.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with metric_col2:
        st.markdown(
            f"""
            <div class="mini-card">
                <div class="mini-label">Total Commitment</div>
                <div class="mini-value" style="font-size:1.55rem;">{metrics["Total Commitment"]}</div>
                <div class="mini-note">Aggregate commitment across all funds.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with metric_col3:
        st.markdown(
            f"""
            <div class="mini-card">
                <div class="mini-label">Funded YTD</div>
                <div class="mini-value" style="font-size:1.55rem;">{metrics["Funded YTD"]}</div>
                <div class="mini-note">Current funded amount from the tracker sheet.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with metric_col4:
        st.markdown(
            f"""
            <div class="mini-card mini-card-muted">
                <div class="mini-label">Remaining Open</div>
                <div class="mini-value" style="font-size:1.55rem;">{metrics["Remaining Open"]}</div>
                <div class="mini-note">Open commitment still available.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Upcoming Capital Calls</div>', unsafe_allow_html=True)

    upcoming_overview_df = dashboard_data.upcoming_df.copy()
    if upcoming_overview_df.empty:
        st.info("No upcoming capital calls are currently scheduled.")
    else:
        if "Due Date" in upcoming_overview_df.columns:
            upcoming_overview_df["Due Date"] = pd.to_datetime(
                upcoming_overview_df["Due Date"], errors="coerce"
            )
            today = pd.Timestamp(datetime.now(ZoneInfo("Europe/Zurich")).date())
            upcoming_overview_df["Due In Days"] = upcoming_overview_df["Due Date"].apply(
                lambda value: (
                    int((value.normalize() - today).days)
                    if pd.notna(value)
                    else None
                )
            )
            upcoming_overview_df = upcoming_overview_df.sort_values(
                by=["Due Date", "Investor", "Fund Name"],
                na_position="last",
            )

        overview_display_df = prepare_upcoming_capital_calls_display(upcoming_overview_df)
        if "Due In Days" in upcoming_overview_df.columns:
            overview_display_df["Due In Days"] = upcoming_overview_df["Due In Days"].apply(
                lambda value: "" if pd.isna(value) else int(value)
            ).tolist()

        overview_columns = [
            col
            for col in ["Investor", "Fund Name", "Amount", "Due Date", "Due In Days"]
            if col in overview_display_df.columns
        ]
        st.dataframe(
            overview_display_df[overview_columns],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Due In Days": st.column_config.NumberColumn(
                    "Due In Days",
                    format="%d",
                    width="small",
                )
            },
        )

        if "Amount" in upcoming_overview_df.columns:
            upcoming_total = float(upcoming_overview_df["Amount"].fillna(0).sum())
        else:
            upcoming_total = 0.0
        next_due_date = (
            upcoming_overview_df["Due Date"].dropna().min().strftime("%d.%m.%Y")
            if "Due Date" in upcoming_overview_df.columns
            and not upcoming_overview_df["Due Date"].dropna().empty
            else "-"
        )
        st.caption(
            f"Upcoming calls: {len(upcoming_overview_df)} | Total upcoming amount: "
            f"{format_currency_display(upcoming_total)} | Next due date: {next_due_date}"
        )

elif page == "Approved Wires":
    source_workbook = BASE_DIR / "data" / "reference" / "IO_Case_study_Capital_Calls.xlsx"
    managed_workbook = BASE_DIR / "data" / "processed" / "approved_wires_master.xlsx"

    render_page_hero(
        "Approved Wires",
        "Maintain and review approved wire instructions used for payment verification.",
        eyebrow="",
    )

    master_df = load_approved_wires(
        source_workbook=source_workbook,
        managed_workbook=managed_workbook,
    )

    if st.session_state.get("approved_wire_pending_record"):
        approved_wire_confirmation_dialog(master_df, managed_workbook)
    if st.session_state.get("approved_wire_show_add_dialog"):
        approved_wire_add_dialog(master_df)
    if st.session_state.get("approved_wire_show_reset_dialog"):
        approved_wires_reset_dialog(source_workbook, managed_workbook)

    st.markdown(
        """
        <div class="content-card">
            Maintain the approved counterparty wire instructions used for wire verification.
            You can filter the list, review the current records, and add new records without allowing duplicates.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Filters")

    if "approved_wires_filter_currencies" not in st.session_state:
        st.session_state["approved_wires_filter_currencies"] = []
    if "approved_wires_filter_statuses" not in st.session_state:
        st.session_state["approved_wires_filter_statuses"] = []

    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        search_text = st.text_input(
            "Search",
            placeholder="Fund, bank, IBAN, SWIFT",
        )
        selected_funds = st.multiselect(
            "Fund Name",
            options=sorted(master_df["Fund Name"].dropna().astype(str).unique().tolist()),
        )
        selected_banks = st.multiselect(
            "Beneficiary Bank",
            options=sorted(master_df["Beneficiary Bank"].dropna().astype(str).unique().tolist()),
        )

    with filter_col2:
        all_currencies = sorted(master_df["Currency"].dropna().astype(str).unique().tolist())
        all_statuses = sorted(master_df["Status"].dropna().astype(str).unique().tolist())

        st.session_state["approved_wires_filter_currencies"] = [
            value
            for value in st.session_state["approved_wires_filter_currencies"]
            if value in all_currencies
        ]
        st.session_state["approved_wires_filter_statuses"] = [
            value
            for value in st.session_state["approved_wires_filter_statuses"]
            if value in all_statuses
        ]

        selected_currencies = st.multiselect(
            "Currency",
            options=all_currencies,
            key="approved_wires_filter_currencies",
        )
        selected_statuses = st.multiselect(
            "Status",
            options=all_statuses,
            key="approved_wires_filter_statuses",
        )

    filtered_df = apply_approved_wires_filters(
        master_df,
        search_text=search_text,
        fund_names=selected_funds,
        banks=selected_banks,
        currencies=selected_currencies,
        statuses=selected_statuses,
    )

    display_df = build_approved_wires_display_df(filtered_df)

    st.markdown("### Approved Wire Instructions")

    editable_cols = [
        col for col in editable_columns_for_ui(filtered_df) if col in display_df.columns
    ]

    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        disabled=[col for col in display_df.columns if col not in editable_cols],
        num_rows="fixed",
        column_config={
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=["🟢 Active", "🔴 Inactive"],
                width="small",
                required=True,
            ),
            "Updated At": st.column_config.TextColumn(
                "Updated At",
                width="medium",
            ),
        },
    )

    active_count = int(filtered_df["Status"].eq("Active").sum()) if "Status" in filtered_df.columns else 0
    inactive_count = (
        int(filtered_df["Status"].eq("Inactive").sum()) if "Status" in filtered_df.columns else 0
    )
    st.caption(
        f"Total wires: {len(filtered_df)} | Active: {active_count} | Inactive: {inactive_count}"
    )

    action_col1, action_col2, action_col3, _action_spacer = st.columns([1, 1, 1, 2])

    with action_col1:
        if st.button("Save Changes", use_container_width=True):
            updated_master = update_editable_fields(master_df, edited_df)
            save_approved_wires(updated_master, managed_workbook)
            st.success("Approved wires updated successfully.")
            st.rerun()

    with action_col2:
        if st.button("Reset to Source", use_container_width=True):
            st.session_state["approved_wire_show_reset_dialog"] = True
            st.rerun()

    with action_col3:
        if st.button("Add New Record", use_container_width=True):
            st.session_state["approved_wire_show_add_dialog"] = True
            st.rerun()

    feedback_message = st.session_state.pop("approved_wire_feedback", None)
    if feedback_message:
        st.success(feedback_message)

    if "approved_wire_currency" not in st.session_state:
        st.session_state["approved_wire_currency"] = "EUR"
    if "approved_wire_currency_choice" not in st.session_state:
        st.session_state["approved_wire_currency_choice"] = "EUR"
    if "approved_wire_currency_other" not in st.session_state:
        st.session_state["approved_wire_currency_other"] = ""
    if "approved_wire_status" not in st.session_state:
        st.session_state["approved_wire_status"] = "Active"

elif page == "Commitment Tracker":
    source_workbook = BASE_DIR / "data" / "reference" / "IO_Case_study_Capital_Calls.xlsx"
    managed_workbook = BASE_DIR / "data" / "processed" / "capital_calls_master.xlsx"
    active_workbook = ensure_commitment_dashboard_workbook(source_workbook, managed_workbook)

    if st.session_state.get("commitment_tracker_show_reset_dialog"):
        commitment_tracker_reset_dialog(source_workbook, managed_workbook)

    dashboard_data = get_commitment_dashboard(
        str(active_workbook),
        active_workbook.stat().st_mtime,
    )
    state = workflow_state()
    dashboard_data = apply_workflow_updates(dashboard_data, state.get("notices", []))
    metrics = dashboard_metrics(dashboard_data)

    tracker_df = dashboard_data.tracker_df.copy()
    upcoming_df = dashboard_data.upcoming_df.copy()
    executed_df = dashboard_data.executed_df.copy()

    render_page_hero(
        "Commitment Tracker",
        "Track commitments, upcoming capital calls & executed payments in one place.",
        eyebrow="",
    )

    feedback_message = st.session_state.pop("commitment_tracker_feedback", None)
    if feedback_message:
        st.success(feedback_message)

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    with metric_col1:
        st.markdown(
            f"""
            <div class="mini-card">
                <div class="mini-label">Funds</div>
                <div class="mini-value">{metrics["Funds"]}</div>
                <div class="mini-note">Tracked funds in the commitment sheet.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with metric_col2:
        st.markdown(
            f"""
            <div class="mini-card">
                <div class="mini-label">Total Commitment</div>
                <div class="mini-value" style="font-size:1.55rem;">{metrics["Total Commitment"]}</div>
                <div class="mini-note">Aggregate commitment across all funds.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with metric_col3:
        st.markdown(
            f"""
            <div class="mini-card">
                <div class="mini-label">Funded YTD</div>
                <div class="mini-value" style="font-size:1.55rem;">{metrics["Funded YTD"]}</div>
                <div class="mini-note">Current funded amount from the tracker sheet.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with metric_col4:
        st.markdown(
            f"""
            <div class="mini-card mini-card-muted">
                <div class="mini-label">Remaining Open</div>
                <div class="mini-value" style="font-size:1.55rem;">{metrics["Remaining Open"]}</div>
                <div class="mini-note">Open commitment still available.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Filters")
    filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 1.35])

    fund_options = sorted(tracker_df["Fund Name"].dropna().astype(str).unique().tolist())
    investor_options = sorted(tracker_df["Investor"].dropna().astype(str).unique().tolist())

    with filter_col1:
        selected_investors = st.multiselect(
            "Investor",
            options=investor_options,
            key="commitment_tracker_investors",
        )

    with filter_col2:
        selected_funds = st.multiselect(
            "Fund Name",
            options=fund_options,
            key="commitment_tracker_funds",
        )

    with filter_col3:
        tracker_search = st.text_input(
            "Search",
            placeholder="Investor or fund name",
            key="commitment_tracker_search",
        )

    if tracker_search:
        search_value = tracker_search.strip().lower()
        tracker_df = tracker_df[
            tracker_df[["Investor", "Fund Name"]]
            .astype(str)
            .apply(lambda col: col.str.lower().str.contains(search_value, na=False))
            .any(axis=1)
        ]
        upcoming_df = upcoming_df[
            upcoming_df[["Investor", "Fund Name"]]
            .astype(str)
            .apply(lambda col: col.str.lower().str.contains(search_value, na=False))
            .any(axis=1)
        ]
        executed_df = executed_df[
            executed_df[["Investor", "Fund Name"]]
            .astype(str)
            .apply(lambda col: col.str.lower().str.contains(search_value, na=False))
            .any(axis=1)
        ]

    if selected_investors:
        tracker_df = tracker_df[tracker_df["Investor"].isin(selected_investors)]
        upcoming_df = upcoming_df[upcoming_df["Investor"].isin(selected_investors)]
        executed_df = executed_df[executed_df["Investor"].isin(selected_investors)]

    if selected_funds:
        tracker_df = tracker_df[tracker_df["Fund Name"].isin(selected_funds)]
        upcoming_df = upcoming_df[upcoming_df["Fund Name"].isin(selected_funds)]
        executed_df = executed_df[executed_df["Fund Name"].isin(selected_funds)]

    tracker_display_df = prepare_commitment_tracker_display(tracker_df)
    upcoming_display_df = prepare_upcoming_capital_calls_display(upcoming_df)
    executed_display_df = prepare_executed_capital_calls_display(executed_df)

    tracker_tab, upcoming_tab, executed_tab = st.tabs(
        ["Commitment Tracker", "Upcoming Capital Calls", "Executed Capital Calls"]
    )

    with tracker_tab:
        st.dataframe(tracker_display_df, use_container_width=True, hide_index=True)
        tracker_remaining = (
            tracker_df["Remaining Open Commitment"].sum()
            if "Remaining Open Commitment" in tracker_df.columns
            else 0
        )
        st.caption(
            f"Funds: {len(tracker_df)} | Remaining open commitment: {format_currency_display(tracker_remaining)}"
        )

    with upcoming_tab:
        st.dataframe(upcoming_display_df, use_container_width=True, hide_index=True)
        upcoming_total = upcoming_df["Amount"].sum() if "Amount" in upcoming_df.columns else 0
        st.caption(
            f"Upcoming calls: {len(upcoming_df)} | Total upcoming amount: {format_currency_display(upcoming_total)} | Next due date: {metrics['Next Due Date']}"
        )

    with executed_tab:
        st.dataframe(executed_display_df, use_container_width=True, hide_index=True)
        executed_total = (
            executed_df["Capital Call Amount Paid"].sum()
            if "Capital Call Amount Paid" in executed_df.columns
            else 0
        )
        st.caption(
            f"Executed calls: {len(executed_df)} | Total executed amount: {format_currency_display(executed_total)}"
        )

    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
    reset_col1, reset_col2 = st.columns([1, 5])
    with reset_col1:
        if st.button("Reset to Source", key="commitment_tracker_reset_button", use_container_width=True):
            st.session_state["commitment_tracker_show_reset_dialog"] = True
            st.rerun()

elif page == "Upload Notice":
    render_page_hero(
        "Upload Notice",
        "Upload and extract capital call notices before review and validation.",
        eyebrow="",
    )
    st.markdown(
        """
        <div class="content-card">
            Upload a capital call notice PDF. The prototype extracts the core notice fields and stores the notice for validation.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("show_notice_reset_dialog"):
        uploaded_notices_reset_dialog()

    uploaded_file = st.file_uploader("File Dropzone", type=["pdf"])

    if uploaded_file is not None:
        st.info(f"Ready to extract: {uploaded_file.name}")

        if st.button("Extract Notice Data", use_container_width=True):
            with st.spinner("Extracting notice data..."):
                pdf_path = save_uploaded_notice_file(uploaded_file)
                raw_text = extract_text_from_pdf_bytes(uploaded_file.getvalue())
                extracted = extract_notice_fields(raw_text, filename=uploaded_file.name)
                extracted["pdf_path"] = str(pdf_path)

                notice_record = create_notice_record(extracted)
                state = workflow_state()
                upsert_notice(state, notice_record)
                persist_workflow_state(state)

                st.session_state["current_notice_id"] = notice_record["id"]
                st.session_state["upload_notice_feedback"] = (
                    "Notice uploaded and extracted successfully."
                )
                st.rerun()

    upload_feedback = st.session_state.pop("upload_notice_feedback", None)
    if upload_feedback:
        st.success(upload_feedback)

    state = workflow_state()
    review_notices_df = notices_to_dataframe(state.get("notices", []), statuses=["review"])

    if not review_notices_df.empty:
        review_notice = (
            get_notice_by_id(state, st.session_state.get("current_notice_id", ""))
            if st.session_state.get("current_notice_id")
            else None
        )
        if review_notice is None or review_notice.get("status") != "review":
            review_notice = get_notice_by_id(state, review_notices_df.iloc[0]["id"])

        if review_notice:
            review_notice_dialog(review_notice)

    notices_df = notices_to_dataframe(state.get("notices", []), statuses=["uploaded", "validated", "executed"])
    if st.session_state.get("uploaded_notice_edit_id") and not notices_df.empty:
        selected_uploaded_notice = get_notice_by_id(state, st.session_state["uploaded_notice_edit_id"])
        if selected_uploaded_notice:
            edit_uploaded_notice_dialog(selected_uploaded_notice)

    if not notices_df.empty:
        upload_display_df = notices_df.copy()
        upload_display_df["Select"] = False
        if "amount" in upload_display_df.columns:
            upload_display_df["amount"] = upload_display_df.apply(
                lambda row: (
                    format_currency_display(
                        float(row.get("amount", 0) or 0),
                        row.get("currency", "EUR"),
                    )
                    if row.get("amount") not in (None, "")
                    else ""
                ),
                axis=1,
            )
        if "due_date" in upload_display_df.columns:
            upload_display_df["due_date"] = pd.to_datetime(
                upload_display_df["due_date"], errors="coerce"
            ).dt.strftime("%d.%m.%Y")
        for source_col, display_col in [
            ("beneficiary_bank", "bank"),
            ("iban", "iban"),
            ("swift", "swift"),
        ]:
            if source_col in upload_display_df.columns:
                upload_display_df[display_col] = upload_display_df[source_col].apply(
                    lambda value: "-" if value in (None, "") or pd.isna(value) else str(value)
                )
            else:
                upload_display_df[display_col] = "-"
        upload_display_df["iban_short"] = upload_display_df["iban"].apply(compact_iban_display)
        preview_columns = [
            col
            for col in ["Select", "fund_name", "amount", "bank", "iban_short", "swift", "due_date", "status"]
            if col in upload_display_df.columns
        ]
        st.markdown("### Uploaded Notices")
        upload_table_df = upload_display_df[preview_columns].rename(
            columns={
                "Select": "Select",
                "fund_name": "Fund Name",
                "amount": "Amount",
                "bank": "Bank",
                "iban_short": "IBAN",
                "swift": "SWIFT",
                "due_date": "Due",
                "status": "Status",
            }
        )
        edited_upload_df = st.data_editor(
            upload_table_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", width="small"),
                "Fund Name": st.column_config.TextColumn("Fund Name", disabled=True, width="medium"),
                "Amount": st.column_config.TextColumn("Amount", disabled=True, width="small"),
                "Bank": st.column_config.TextColumn("Bank", disabled=True, width="medium"),
                "IBAN": st.column_config.TextColumn("IBAN", disabled=True, width="medium"),
                "SWIFT": st.column_config.TextColumn("SWIFT", disabled=True, width="small"),
                "Due": st.column_config.TextColumn("Due", disabled=True, width="small"),
                "Status": st.column_config.TextColumn("Status", disabled=True, width="small"),
            },
            disabled=["Fund Name", "Amount", "Bank", "IBAN", "SWIFT", "Due", "Status"],
            key="uploaded_notices_editor",
        )

        checked_rows = edited_upload_df.index[edited_upload_df["Select"]].tolist()
        table_action_col1, table_action_col2, table_action_col3 = st.columns([1, 1, 3])
        with table_action_col1:
            if st.button("Edit Selected Notice", use_container_width=True):
                if len(checked_rows) != 1:
                    st.warning("Please select exactly one notice.")
                elif open_uploaded_notice_editor_for_checked_rows(checked_rows, notices_df.reset_index(drop=True)):
                    st.rerun()
        with table_action_col2:
            if st.button("Delete All Notices", use_container_width=True):
                st.session_state["show_notice_reset_dialog"] = True
                st.rerun()

elif page == "Validation":
    render_page_hero(
        "Validation",
        "Run commitment and wire checks before routing notices to execution or upcoming calls.",
        eyebrow="",
    )

    state = workflow_state()
    notices = state.get("notices", [])
    notices_df = notices_to_dataframe(notices, statuses=["uploaded", "validated"])

    if notices_df.empty:
        st.info("No uploaded notices are waiting for validation.")
    else:
        notice_options = {
            f"{row['source_filename']} | {row.get('fund_name', '')} | {row['status']}": row["id"]
            for _, row in notices_df.iterrows()
        }
        selected_label = st.selectbox("Select notice", options=list(notice_options.keys()))
        selected_notice = get_notice_by_id(state, notice_options[selected_label])

        if selected_notice:
            extracted_summary = {
                "Fund Name": selected_notice.get("fund_name", ""),
                "Amount": (
                    format_currency_display(
                        float(selected_notice.get("amount", 0) or 0),
                        selected_notice.get("currency", "EUR"),
                    )
                    if selected_notice.get("amount") not in (None, "")
                    else ""
                ),
                "Due Date": pd.to_datetime(selected_notice.get("due_date"), errors="coerce").strftime("%d.%m.%Y")
                if pd.notna(pd.to_datetime(selected_notice.get("due_date"), errors="coerce"))
                else "",
                "IBAN": selected_notice.get("iban", ""),
                "SWIFT/BIC": selected_notice.get("swift", ""),
                "Beneficiary Bank": selected_notice.get("beneficiary_bank", ""),
            }
            render_record_summary(extracted_summary, "Extracted notice")

            commitment_workbook = BASE_DIR / "data" / "processed" / "capital_calls_master.xlsx"
            approved_source = BASE_DIR / "data" / "reference" / "IO_Case_study_Capital_Calls.xlsx"
            approved_managed = BASE_DIR / "data" / "processed" / "approved_wires_master.xlsx"

            commitment_workbook = ensure_commitment_dashboard_workbook(
                BASE_DIR / "data" / "reference" / "IO_Case_study_Capital_Calls.xlsx",
                commitment_workbook,
            )
            dashboard_data = load_commitment_dashboard(commitment_workbook)
            dashboard_data = apply_workflow_updates(dashboard_data, state.get("notices", []))
            approved_wires_df = load_approved_wires(approved_source, approved_managed)
            approved_wire_suggestions = build_approved_wire_suggestions(
                selected_notice,
                approved_wires_df,
            )

            validation_result = validate_notice(
                selected_notice,
                dashboard_data.tracker_df,
                approved_wires_df,
            )

            if approved_wire_suggestions:
                st.markdown(
                    """
                    <div style="background:#fff3cd;border:1px solid #ffe69c;color:#7a5a00;
                                border-radius:12px;padding:0.8rem 1rem;margin:0.9rem 0 1rem 0;
                                font-size:0.95rem;">
                        Additional reference data was found in Approved Wires. Please review the suggested fields below.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                render_record_summary(approved_wire_suggestions, "Suggested from Approved Wires")

            render_validation_summary(validation_result)

            commitment_check = validation_result["commitment_check"]
            wire_check = validation_result["wire_check"]

            detail_col1, detail_col2 = st.columns(2)
            with detail_col1:
                st.markdown("**Commitment Check Details**")
                st.write(f"Matched fund: {commitment_check.get('matched_fund') or '-'}")
                st.write(f"Investor: {commitment_check.get('investor') or '-'}")
                if commitment_check.get("remaining_open_commitment") is not None:
                    st.write(
                        "Remaining open commitment: "
                        f"{format_currency_display(float(commitment_check['remaining_open_commitment']))}"
                    )
            with detail_col2:
                st.markdown("**Wire Check Details**")
                matched_wire = wire_check.get("matched_record")
                if matched_wire:
                    st.write(f"Matched fund: {matched_wire.get('Fund Name', '-')}")
                    st.write(f"IBAN: {matched_wire.get('IBAN / Account Number', '-')}")
                    st.write(f"SWIFT/BIC: {matched_wire.get('Swift/BIC', '-')}")
                else:
                    st.write("No approved wire match found.")

            approval_allowed = validation_result["overall_status"] == "pass"
            if not approval_allowed:
                st.warning("Approval is blocked until both checks pass.")

            action_col1, action_col2, action_col3 = st.columns([1, 1, 2])
            with action_col1:
                if st.button(
                    "Approve and Execute",
                    use_container_width=True,
                    disabled=not approval_allowed,
                ):
                    selected_notice["investor"] = commitment_check.get("investor", "")
                    selected_notice = set_notice_validation(selected_notice, validation_result)
                    selected_notice = approve_notice(selected_notice)
                    upsert_notice(state, selected_notice)
                    persist_workflow_state(state)
                    st.session_state["current_notice_id"] = selected_notice["id"]
                    st.session_state["validation_feedback"] = (
                        "Notice approved and moved to Executed."
                    )
                    st.rerun()
            with action_col2:
                if st.button("Reject and Delete", use_container_width=True):
                    updated_state = delete_notice_by_id(state, selected_notice["id"])
                    persist_workflow_state(updated_state)
                    st.session_state.pop("current_notice_id", None)
                    st.session_state["validation_feedback"] = (
                        "Notice was rejected and deleted."
                    )
                    st.rerun()

    validation_feedback = st.session_state.pop("validation_feedback", None)
    if validation_feedback:
        st.success(validation_feedback)

elif page == "Executed Calls":
    render_page_hero(
        "Executed Calls",
        "Review historical and workflow payments and generate confirmation emails.",
        eyebrow="",
    )

    state = workflow_state()
    commitment_workbook = ensure_commitment_dashboard_workbook(
        BASE_DIR / "data" / "reference" / "IO_Case_study_Capital_Calls.xlsx",
        BASE_DIR / "data" / "processed" / "capital_calls_master.xlsx",
    )
    approved_wires_df = load_approved_wires(
        BASE_DIR / "data" / "reference" / "IO_Case_study_Capital_Calls.xlsx",
        BASE_DIR / "data" / "processed" / "approved_wires_master.xlsx",
    )
    dashboard_data = load_commitment_dashboard(commitment_workbook)

    historical_executed_df = dashboard_data.executed_df.copy()
    if not historical_executed_df.empty:
        historical_executed_df = historical_executed_df.rename(
            columns={
                "Fund Name": "fund_name",
                "Investor": "investor",
                "Capital Call Amount Paid": "amount",
                "Value Date": "value_date",
            }
        )
        historical_executed_df["currency"] = "EUR"
        historical_executed_df["executed_at"] = pd.to_datetime(
            historical_executed_df["value_date"],
            errors="coerce",
        )
        historical_executed_df["id"] = [
            f"historical_{index}" for index in historical_executed_df.index
        ]
        historical_executed_df["source"] = "Historical"
        historical_executed_df["iban"] = ""
        historical_executed_df["swift"] = ""

    workflow_executed_df = notices_to_dataframe(state.get("notices", []), statuses=["executed"])
    if not workflow_executed_df.empty:
        workflow_executed_df = workflow_executed_df.copy()
        workflow_executed_df["value_date"] = pd.to_datetime(
            workflow_executed_df["executed_at"],
            errors="coerce",
        )
        workflow_executed_df["source"] = "Workflow"

    executed_df = pd.concat(
        [historical_executed_df, workflow_executed_df],
        ignore_index=True,
        sort=False,
    ) if not historical_executed_df.empty or not workflow_executed_df.empty else pd.DataFrame()

    if st.session_state.get("executed_email_notice_id") and not executed_df.empty:
        selected_email_row = executed_df[
            executed_df["id"].astype(str).eq(st.session_state["executed_email_notice_id"])
        ]
        if not selected_email_row.empty:
            email_context = enrich_record_with_approved_wire(
                selected_email_row.iloc[0].to_dict(),
                approved_wires_df,
            )
            executed_email_dialog(build_executed_email_context(email_context))

    if executed_df.empty:
        st.info("No capital calls have been executed yet.")
    else:
        executed_display_df = executed_df.copy()
        executed_display_df["Open"] = False
        sent_notice_ids = set(st.session_state.get("executed_email_sent_ids", []))
        sent_timestamps = dict(st.session_state.get("executed_email_sent_at", {}))
        executed_display_df["status_sent"] = executed_df["id"].astype(str).apply(
            lambda notice_id: notice_id in sent_notice_ids
        )
        executed_display_df["sent_at"] = executed_df["id"].astype(str).apply(
            lambda notice_id: sent_timestamps.get(notice_id, "")
        )
        if "sent_at" in executed_display_df.columns:
            executed_display_df["sent_at"] = pd.to_datetime(
                executed_display_df["sent_at"], errors="coerce"
            )
        if "amount" in executed_display_df.columns:
            executed_display_df["amount"] = executed_display_df.apply(
                lambda row: format_currency_display(
                    float(row.get("amount", 0) or 0),
                    row.get("currency", "EUR"),
                ),
                axis=1,
            )
        for column in ["due_date", "value_date", "executed_at"]:
            if column in executed_display_df.columns:
                executed_display_df[column] = pd.to_datetime(
                    executed_display_df[column], errors="coerce"
                )
        executed_table_df = executed_display_df[
            ["status_sent", "sent_at", "Open", "investor", "fund_name", "amount", "value_date", "executed_at"]
        ].rename(
            columns={
                "status_sent": "Email Status",
                "sent_at": "Email Sent On",
                "Open": "Select",
                "investor": "Investor",
                "fund_name": "Fund Name",
                "amount": "Amount",
                "value_date": "Value Date",
                "executed_at": "Executed At",
            }
        )
        for date_column in ["Email Sent On", "Value Date", "Executed At"]:
            if date_column in executed_table_df.columns:
                executed_table_df[date_column] = pd.to_datetime(
                    executed_table_df[date_column], errors="coerce"
                )
        executed_table_df["Email Status"] = (
            executed_table_df["Email Status"].fillna(False).astype(bool)
        )
        executed_table_df["Select"] = executed_table_df["Select"].fillna(False).astype(bool)

        edited_executed_df = st.data_editor(
            executed_table_df,
            use_container_width=True,
            hide_index=True,
            disabled=[
                "Email Status",
                "Email Sent On",
                "Investor",
                "Fund Name",
                "Amount",
                "Value Date",
                "Executed At",
            ],
            column_config={
                "Email Status": st.column_config.CheckboxColumn("Email Status", width="small"),
                "Email Sent On": st.column_config.DateColumn(
                    "Email Sent On",
                    width="small",
                    format="DD.MM.YYYY",
                ),
                "Select": st.column_config.CheckboxColumn(
                    "Select",
                    help="Select one executed call to open the email template.",
                    width="small",
                ),
                "Investor": st.column_config.TextColumn("Investor", width="small"),
                "Fund Name": st.column_config.TextColumn("Fund Name", width="medium"),
                "Amount": st.column_config.TextColumn("Amount", width="small"),
                "Value Date": st.column_config.DateColumn(
                    "Value Date",
                    width="small",
                    format="DD.MM.YYYY",
                ),
                "Executed At": st.column_config.DateColumn(
                    "Executed At",
                    width="small",
                    format="DD.MM.YYYY",
                ),
            },
            key=f"executed_calls_table_{st.session_state.get('executed_calls_table_nonce', 0)}",
        )

        checked_rows = edited_executed_df.index[edited_executed_df["Select"]].tolist()
        action_col1, action_col2 = st.columns([1.2, 4])
        with action_col1:
            if st.button("Open Email Template", use_container_width=True):
                if len(checked_rows) != 1:
                    st.warning("Please select exactly one executed call.")
                elif open_executed_email_for_checked_rows(checked_rows, executed_df):
                    st.rerun()
        with action_col2:
            if sent_notice_ids:
                st.success("Sent emails are marked in the Status column.")

        st.caption(
            f"Executed calls: {len(executed_df)} | Total executed amount: "
            f"{format_currency_display(executed_df['amount'].fillna(0).astype(float).sum(), executed_df['currency'].fillna('EUR').iloc[0] if 'currency' in executed_df.columns and not executed_df.empty else 'EUR')}"
        )
