from __future__ import annotations

import re
import pandas as pd
import streamlit as st

from src.approved_wires import (
    add_approved_wire_record,
    find_duplicate_record,
    reset_approved_wires_to_source,
    save_approved_wires,
)
from src.app_context import COMMON_CURRENCY_CODES, WORKFLOW_STATE_PATH
from src.commitment_tracker import reset_commitment_dashboard_to_source
from src.email_templates import generate_payment_confirmation_email
from src.state import (
    clear_approved_wire_state,
    clear_commitment_tracker_state,
    clear_uploaded_notice_files,
    clear_uploaded_notice_state,
    persist_workflow_state,
    reset_approved_wire_form,
    workflow_state,
)
from src.ui.common import (
    build_approved_wire_suggestions,
    enrich_record_with_approved_wire,
    editable_notice_payload,
    format_amount_input,
    format_currency_display,
    mark_executed_email_as_sent,
    parse_amount_input,
    render_record_summary,
)
from src.workflow import (
    accept_notice_record,
    approve_notice,
    create_notice_record,
    delete_notice_by_id,
    reset_workflow_state,
    schedule_notice,
    upsert_notice,
)


### Confirm adding a pending approved-wire record after duplicate detection.
###############################################################################
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


### Collect a new approved-wire record from the user before duplicate review.
###############################################################################
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
                currency_other.strip().upper() if currency_choice == "Other" else currency_choice
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


### Confirm resetting the managed approved-wires workbook back to the source.
###############################################################################
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


### Confirm resetting the managed commitment workbook and clearing related workflow data.
###############################################################################
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


### Confirm deleting all uploaded workflow notices from the prototype state.
###############################################################################
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


### Show the generated payment confirmation email for a selected executed notice.
###############################################################################
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
        if st.button("Mark as Sent", use_container_width=True, type="primary"):
            mark_executed_email_as_sent(notice.get("id", ""))
            st.rerun()
    with action_col2:
        if st.button("Close", use_container_width=True):
            st.session_state.pop("executed_email_notice_id", None)
            st.rerun()


### Confirm moving a scheduled upcoming call into the executed workflow state.
###############################################################################
@st.dialog("Execute Scheduled Capital Call")
def execute_scheduled_call_dialog(notice, approved_wires_df):
    enriched_notice = enrich_record_with_approved_wire(notice, approved_wires_df)
    wire_suggestions = build_approved_wire_suggestions(notice, approved_wires_df)

    st.caption("Please review the scheduled capital call details before moving it to Executed Capital Calls.")
    if wire_suggestions:
        suggestion_lines = [
            f"{field}: {value}" for field, value in wire_suggestions.items() if str(value).strip()
        ]
        if suggestion_lines:
            st.info("Suggested from Approved Wires: " + " | ".join(suggestion_lines))

    due_date_value = pd.to_datetime(enriched_notice.get("due_date"), errors="coerce")
    due_date_default = due_date_value.strftime("%d.%m.%Y") if pd.notna(due_date_value) else ""

    st.markdown("**Scheduled Capital Call**")
    st.caption("All fields can be edited here. Suggested wire details are prefilled from Approved Wires when available.")

    with st.form(f"execute_scheduled_call_form_{notice.get('id', 'notice')}", clear_on_submit=False):
        review_col1, review_col2 = st.columns(2)

        with review_col1:
            fund_name_input = st.text_input("Fund Name", value=enriched_notice.get("fund_name", ""))
            investor_input = st.text_input(
                "Investor / Limited Partner",
                value=enriched_notice.get("investor", ""),
            )
            amount_input = st.text_input(
                "Amount",
                value=format_currency_display(
                    float(enriched_notice.get("amount", 0) or 0),
                    enriched_notice.get("currency", "EUR"),
                ),
            )
            currency_input = st.text_input("Currency", value=enriched_notice.get("currency", ""))
            due_date_input = st.text_input("Due Date", value=due_date_default)

        with review_col2:
            beneficiary_bank_input = st.text_input(
                "Beneficiary Bank",
                value=enriched_notice.get("beneficiary_bank", ""),
            )
            iban_input = st.text_input("IBAN", value=enriched_notice.get("iban", ""))
            swift_input = st.text_input("SWIFT/BIC", value=enriched_notice.get("swift", ""))

        parsed_due_date = pd.to_datetime(due_date_input, dayfirst=True, errors="coerce")
        parsed_amount = None
        amount_text = str(amount_input).strip()
        if amount_text:
            amount_cleaned = amount_text
            currency_prefix = str(currency_input or "").strip().upper()
            if currency_prefix:
                amount_cleaned = re.sub(
                    rf"^\s*{re.escape(currency_prefix)}\s+",
                    "",
                    amount_cleaned,
                    flags=re.IGNORECASE,
                )
            try:
                parsed_amount = parse_amount_input(amount_cleaned)
            except ValueError:
                parsed_amount = None

        required_fields_complete = all(
            [
                str(fund_name_input).strip(),
                str(investor_input).strip(),
                parsed_amount is not None,
                str(currency_input).strip(),
                pd.notna(parsed_due_date),
                str(beneficiary_bank_input).strip(),
                str(iban_input).strip(),
                str(swift_input).strip(),
            ]
        )

        if not required_fields_complete:
            st.warning(
                "Execution is only possible when all fields are filled correctly, including a valid amount and due date."
            )

        action_col1, action_col2, action_col3 = st.columns(3)
        save_clicked = action_col1.form_submit_button("Save Settings", use_container_width=True)
        confirm_clicked = action_col2.form_submit_button(
            "Confirm and Move to Executed",
            use_container_width=True,
            type="primary",
            disabled=not required_fields_complete,
        )
        cancel_clicked = action_col3.form_submit_button("Cancel", use_container_width=True)

        if save_clicked or confirm_clicked:
            state = workflow_state()
            current_notice = next(
                (entry for entry in state.get("notices", []) if entry.get("id") == notice.get("id")),
                None,
            )

            payload = {
                "fund_name": fund_name_input.strip(),
                "investor": investor_input.strip(),
                "amount": parsed_amount,
                "currency": currency_input.strip().upper(),
                "due_date": parsed_due_date,
                "beneficiary_bank": beneficiary_bank_input.strip(),
                "iban": iban_input.strip(),
                "swift": swift_input.strip(),
            }

            if current_notice is not None:
                updated_notice = dict(current_notice)
                updated_notice.update(payload)
                updated_notice["status"] = "scheduled"
            else:
                updated_notice = create_notice_record(
                    {
                        "source_filename": "Historical Upcoming Capital Calls",
                        **payload,
                    }
                )
                updated_notice["source"] = "Historical Upcoming Capital Calls"
                updated_notice["source_upcoming_id"] = notice.get("id", "")
                updated_notice = schedule_notice(updated_notice)

            if save_clicked:
                if not pd.notna(parsed_due_date):
                    st.warning("Please enter a valid Due Date before saving.")
                    return
                upsert_notice(state, updated_notice)
                persist_workflow_state(state)
                st.session_state["upcoming_calls_feedback"] = (
                    "Scheduled capital call settings saved successfully."
                )
                st.session_state.pop("scheduled_call_execute_id", None)
                st.rerun()

            if confirm_clicked:
                updated_notice = approve_notice(updated_notice)
                upsert_notice(state, updated_notice)
                persist_workflow_state(state)
                st.session_state["upcoming_calls_feedback"] = (
                    "Scheduled capital call moved to Executed Capital Calls successfully."
                )
                st.session_state.pop("scheduled_call_execute_id", None)
                st.rerun()

        if cancel_clicked:
            st.session_state.pop("scheduled_call_execute_id", None)
            st.rerun()


### Review extracted notice data before moving a notice into the validation workflow.
###############################################################################
@st.dialog("Review Extracted Data")
def review_notice_dialog(review_notice, fund_name_hint=None):
    st.info(
        "Please verify the extracted data. If everything is correct, accept it. If something is wrong, edit the fields below and then accept."
    )

    if fund_name_hint:
        st.warning(
            "Fund-name number format check: the extracted fund name may use Arabic numbers "
            "where the Commitment Tracker uses Roman numerals, or vice versa. "
            f"Please verify the fund name against the tracker entry: {fund_name_hint.get('matched_fund', '-')}"
        )

    editable = editable_notice_payload(review_notice)

    with st.form("notice_review_form", clear_on_submit=False):
        review_col1, review_col2 = st.columns(2)

        with review_col1:
            reviewed_fund_name = st.text_input("Fund Name", value=editable["fund_name"])
            reviewed_investor = st.text_input("Investor / Limited Partner", value=editable["investor"])
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
                    "investor": reviewed_investor,
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


### Edit a previously accepted uploaded notice before validation/execution.
###############################################################################
@st.dialog("Edit Uploaded Notice")
def edit_uploaded_notice_dialog(notice):
    editable = editable_notice_payload(notice)

    with st.form("edit_uploaded_notice_form", clear_on_submit=False):
        edit_col1, edit_col2 = st.columns(2)

        with edit_col1:
            edited_fund_name = st.text_input("Fund Name", value=editable["fund_name"])
            edited_investor = st.text_input("Investor / Limited Partner", value=editable["investor"])
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
                    "investor": edited_investor,
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
