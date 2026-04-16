from __future__ import annotations

import pandas as pd
import streamlit as st

from src.approved_wires import load_approved_wires
from src.app_context import APPROVED_WIRES_WORKBOOK, CAPITAL_CALLS_WORKBOOK, REFERENCE_WORKBOOK
from src.commitment_tracker import ensure_commitment_dashboard_workbook, load_commitment_dashboard
from src.state import workflow_state
from src.ui.common import (
    build_table_styler,
    build_executed_email_context,
    enrich_record_with_approved_wire,
    open_executed_email_for_checked_rows,
    render_page_hero,
)
from src.ui.dialogs import executed_email_dialog
from src.workflow import notices_to_dataframe


### Render the executed-calls view and email-confirmation workflow for processed notices.
###############################################################################
def render_executed_calls_page() -> None:
    render_page_hero(
        "Executed Capital Calls",
        "Review historical and workflow payments and generate confirmation emails.",
        eyebrow="",
    )

    state = workflow_state()
    commitment_workbook = ensure_commitment_dashboard_workbook(
        REFERENCE_WORKBOOK,
        CAPITAL_CALLS_WORKBOOK,
    )
    approved_wires_df = load_approved_wires(
        REFERENCE_WORKBOOK,
        APPROVED_WIRES_WORKBOOK,
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

    executed_df = (
        pd.concat(
            [historical_executed_df, workflow_executed_df],
            ignore_index=True,
            sort=False,
        )
        if not historical_executed_df.empty or not workflow_executed_df.empty
        else pd.DataFrame()
    )

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
        st.info("No Executed Capital Calls are available yet.")
        return

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
        executed_display_df["amount"] = pd.to_numeric(
            executed_display_df["amount"], errors="coerce"
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
            "investor": "Investor / Limited Partner",
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
    executed_table_df["Email Status"] = executed_table_df["Email Status"].fillna(False).astype(bool)
    executed_table_df["Select"] = executed_table_df["Select"].fillna(False).astype(bool)

    edited_executed_df = st.data_editor(
        build_table_styler(
            executed_table_df,
            amount_columns=["Amount"],
            date_columns=["Email Sent On", "Value Date", "Executed At"],
        ),
        use_container_width=True,
        hide_index=True,
        disabled=[
            "Email Status",
            "Email Sent On",
            "Investor / Limited Partner",
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
                help="Select one executed capital call to open the email template.",
                width="small",
            ),
            "Investor / Limited Partner": st.column_config.TextColumn("Investor / Limited Partner", width="small"),
            "Fund Name": st.column_config.TextColumn("Fund Name", width="medium"),
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
                st.warning("Please select exactly one Executed Capital Call.")
            elif open_executed_email_for_checked_rows(checked_rows, executed_df):
                st.rerun()
    with action_col2:
        if sent_notice_ids:
            st.success("Sent emails are marked in the Status column.")

    st.caption(
        f"Executed Capital Calls: {len(executed_df)} | Total executed amount: "
        f"EUR {executed_df['amount'].fillna(0).astype(float).sum():,.2f}".replace(",", "'")
    )
