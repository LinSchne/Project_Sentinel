from __future__ import annotations

import streamlit as st

from src.app_context import CAPITAL_CALLS_WORKBOOK, REFERENCE_WORKBOOK
from src.commitment_tracker import (
    dashboard_metrics,
    prepare_commitment_tracker_display,
    prepare_executed_capital_calls_display,
    prepare_upcoming_capital_calls_display,
)
from src.services.dashboard_service import load_dashboard_with_workflow
from src.state import workflow_state
from src.ui.common import build_table_styler, format_currency_display, render_page_hero
from src.ui.dialogs import commitment_tracker_reset_dialog


### Render the commitment tracker dashboard with metrics, filters, tabs, and reset flow.
###############################################################################
def render_commitment_tracker_page() -> None:
    if st.session_state.get("commitment_tracker_show_reset_dialog"):
        commitment_tracker_reset_dialog(REFERENCE_WORKBOOK, CAPITAL_CALLS_WORKBOOK)

    state = workflow_state()
    dashboard_data = load_dashboard_with_workflow(
        REFERENCE_WORKBOOK,
        CAPITAL_CALLS_WORKBOOK,
        state.get("notices", []),
    )
    metrics = dashboard_metrics(dashboard_data)

    tracker_df = dashboard_data.tracker_df.copy()
    upcoming_df = dashboard_data.upcoming_df.copy()
    executed_df = dashboard_data.executed_df.copy()

    render_page_hero(
        "Commitment Tracker",
        "Track commitments, Upcoming Capital Calls, and Executed Capital Calls in one place.",
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
            "Investor / Limited Partner",
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
            placeholder="Investor / Limited Partner or fund name",
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
        st.dataframe(
            build_table_styler(
                tracker_display_df,
                amount_columns=[
                    "Total Commitment",
                    "Total Funded YTD",
                    "Remaining Open Commitment",
                ],
            ),
            use_container_width=True,
            hide_index=True,
        )

    with upcoming_tab:
        st.dataframe(
            build_table_styler(
                upcoming_display_df,
                amount_columns=["Amount"],
                date_columns=["Due Date"],
            ),
            use_container_width=True,
            hide_index=True,
        )
        upcoming_total = upcoming_df["Amount"].sum() if "Amount" in upcoming_df.columns else 0
        st.caption(
            f"Upcoming Capital Calls: {len(upcoming_df)} | Total upcoming amount: {format_currency_display(upcoming_total)} | Next due date: {metrics['Next Due Date']}"
        )

    with executed_tab:
        st.dataframe(
            build_table_styler(
                executed_display_df,
                amount_columns=["Capital Call Amount Paid"],
                date_columns=["Value Date"],
            ),
            use_container_width=True,
            hide_index=True,
        )
        executed_total = (
            executed_df["Capital Call Amount Paid"].sum()
            if "Capital Call Amount Paid" in executed_df.columns
            else 0
        )
        st.caption(
            f"Executed Capital Calls: {len(executed_df)} | Total executed amount: {format_currency_display(executed_total)}"
        )

    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
    reset_col1, reset_col2 = st.columns([1, 5])
    with reset_col1:
        if st.button("Reset to Source", key="commitment_tracker_reset_button", use_container_width=True):
            st.session_state["commitment_tracker_show_reset_dialog"] = True
            st.rerun()
