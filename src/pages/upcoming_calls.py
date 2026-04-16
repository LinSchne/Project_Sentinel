from __future__ import annotations

import pandas as pd
import streamlit as st

from src.approved_wires import load_approved_wires
from src.app_context import APPROVED_WIRES_WORKBOOK, CAPITAL_CALLS_WORKBOOK, REFERENCE_WORKBOOK
from src.commitment_tracker import (
    capital_call_match_key,
    ensure_commitment_dashboard_workbook,
    load_commitment_dashboard,
)
from src.state import workflow_state
from src.ui.common import build_table_styler, compact_iban_display, render_page_hero
from src.ui.dialogs import execute_scheduled_call_dialog
from src.workflow import notices_to_dataframe


### Convert workflow-scheduled notices into the shared upcoming-calls table format.
###############################################################################
def _scheduled_workflow_calls_df(state: dict) -> pd.DataFrame:
    scheduled_df = notices_to_dataframe(state.get("notices", []), statuses=["scheduled"])
    if scheduled_df.empty:
        return pd.DataFrame()

    scheduled_df = scheduled_df.copy()
    scheduled_df["source"] = "Workflow"
    scheduled_df["match_key"] = scheduled_df.apply(
        lambda row: capital_call_match_key(
            row.get("investor", ""),
            row.get("fund_name", ""),
            row.get("amount", 0),
            row.get("due_date", ""),
        ),
        axis=1,
    )
    return scheduled_df


### Convert the workbook's historical upcoming sheet into the same list schema.
###############################################################################
def _historical_upcoming_calls_df(state: dict) -> pd.DataFrame:
    overridden_source_ids = {
        str(notice.get("source_upcoming_id", "")).strip()
        for notice in state.get("notices", [])
        if str(notice.get("source_upcoming_id", "")).strip()
    }
    executed_keys = {
        capital_call_match_key(
            notice.get("investor", ""),
            notice.get("fund_name", ""),
            notice.get("amount", 0),
            notice.get("due_date", ""),
        )
        for notice in state.get("notices", [])
        if str(notice.get("status", "")).strip().lower() == "executed"
    }

    managed_workbook = ensure_commitment_dashboard_workbook(
        REFERENCE_WORKBOOK,
        CAPITAL_CALLS_WORKBOOK,
    )
    dashboard_data = load_commitment_dashboard(managed_workbook)
    historical_df = dashboard_data.upcoming_df.copy()
    if historical_df.empty:
        return pd.DataFrame()

    historical_df = historical_df.rename(
        columns={
            "Investor": "investor",
            "Fund Name": "fund_name",
            "Amount": "amount",
            "Due Date": "due_date",
        }
    )
    historical_df["currency"] = "EUR"
    historical_df["beneficiary_bank"] = ""
    historical_df["iban"] = ""
    historical_df["swift"] = ""
    historical_df["status"] = "scheduled"
    historical_df["source"] = "Excel"
    historical_df["id"] = [
        f"historical_upcoming_{index}" for index in historical_df.reset_index(drop=True).index
    ]
    historical_df["match_key"] = historical_df.apply(
        lambda row: capital_call_match_key(
            row.get("investor", ""),
            row.get("fund_name", ""),
            row.get("amount", 0),
            row.get("due_date", ""),
        ),
        axis=1,
    )

    if executed_keys:
        historical_df = historical_df[~historical_df["match_key"].isin(executed_keys)]
    if overridden_source_ids:
        historical_df = historical_df[
            ~historical_df["id"].astype(str).isin(overridden_source_ids)
        ]

    return historical_df.reset_index(drop=True)


### Merge workbook and workflow upcoming calls into one reviewable execution queue.
###############################################################################
def _combined_upcoming_calls_df(state: dict) -> pd.DataFrame:
    workflow_df = _scheduled_workflow_calls_df(state)
    historical_df = _historical_upcoming_calls_df(state)

    if not workflow_df.empty and not historical_df.empty:
        historical_df = historical_df[~historical_df["match_key"].isin(set(workflow_df["match_key"]))]

    combined_df = pd.concat(
        [workflow_df, historical_df],
        ignore_index=True,
        sort=False,
    )
    if combined_df.empty:
        return combined_df

    combined_df["due_date"] = pd.to_datetime(combined_df["due_date"], errors="coerce")
    combined_df = combined_df.sort_values(
        by=["due_date", "source", "investor", "fund_name"],
        na_position="last",
    )
    return combined_df.reset_index(drop=True)


### Render the workflow page for scheduled upcoming calls awaiting execution.
###############################################################################
def render_upcoming_calls_page() -> None:
    render_page_hero(
        "Upcoming Capital Calls",
        "Review scheduled capital calls and move them to Executed Capital Calls when payment is confirmed.",
        eyebrow="",
    )

    feedback_message = st.session_state.pop("upcoming_calls_feedback", None)
    if feedback_message:
        st.success(feedback_message)

    state = workflow_state()
    approved_wires_df = load_approved_wires(
        REFERENCE_WORKBOOK,
        APPROVED_WIRES_WORKBOOK,
    )
    combined_df = _combined_upcoming_calls_df(state)

    if st.session_state.get("scheduled_call_execute_id") and not combined_df.empty:
        selected_notice = combined_df[
            combined_df["id"].astype(str).eq(st.session_state["scheduled_call_execute_id"])
        ]
        if not selected_notice.empty:
            execute_scheduled_call_dialog(selected_notice.iloc[0].to_dict(), approved_wires_df)

    if combined_df.empty:
        st.info("No scheduled Upcoming Capital Calls are currently waiting for execution.")
        return

    display_df = combined_df.copy()
    display_df["Select"] = False
    if "amount" in display_df.columns:
        display_df["amount"] = pd.to_numeric(display_df["amount"], errors="coerce")
    if "due_date" in display_df.columns:
        display_df["due_date"] = pd.to_datetime(display_df["due_date"], errors="coerce")
    if "iban" in display_df.columns:
        display_df["iban_short"] = display_df["iban"].apply(compact_iban_display)

    preview_columns = [
        col
        for col in [
            "Select",
            "source",
            "fund_name",
            "investor",
            "amount",
            "due_date",
            "iban_short",
            "status",
        ]
        if col in display_df.columns
    ]

    table_df = display_df[preview_columns].rename(
        columns={
            "Select": "Select",
            "source": "Source",
            "fund_name": "Fund Name",
            "investor": "Investor / Limited Partner",
            "amount": "Amount",
            "due_date": "Due Date",
            "iban_short": "IBAN",
            "status": "Status",
        }
    )

    edited_df = st.data_editor(
        build_table_styler(
            table_df,
            amount_columns=["Amount"],
            date_columns=["Due Date"],
        ),
        use_container_width=True,
        hide_index=True,
        disabled=["Source", "Fund Name", "Investor / Limited Partner", "Amount", "Due Date", "IBAN", "Status"],
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", width="small"),
            "Source": st.column_config.TextColumn("Source", width="small"),
            "Fund Name": st.column_config.TextColumn("Fund Name", width="medium"),
            "Investor / Limited Partner": st.column_config.TextColumn("Investor / Limited Partner", width="medium"),
            "IBAN": st.column_config.TextColumn("IBAN", width="medium"),
            "Status": st.column_config.TextColumn("Status", width="small"),
        },
        key="upcoming_calls_editor",
    )

    checked_rows = edited_df.index[edited_df["Select"]].tolist()
    action_col1, action_col2 = st.columns([1.3, 4])
    with action_col1:
        if st.button("Move to Executed", use_container_width=True):
            if len(checked_rows) != 1:
                st.warning("Please select exactly one scheduled Upcoming Capital Call.")
            else:
                row_position = checked_rows[0]
                if row_position < len(combined_df):
                    st.session_state["scheduled_call_execute_id"] = str(
                        combined_df.reset_index(drop=True).iloc[row_position]["id"]
                    )
                    st.rerun()
