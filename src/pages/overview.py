from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from src.app_context import CAPITAL_CALLS_WORKBOOK, REFERENCE_WORKBOOK
from src.commitment_tracker import dashboard_metrics, prepare_upcoming_capital_calls_display
from src.services.dashboard_service import load_dashboard_with_workflow
from src.state import workflow_state
from src.ui.common import build_table_styler, format_currency_display, render_page_hero


### Render the landing dashboard with KPIs and upcoming capital call overview data.
###############################################################################
def render_overview_page() -> None:
    state = workflow_state()
    dashboard_data = load_dashboard_with_workflow(
        REFERENCE_WORKBOOK,
        CAPITAL_CALLS_WORKBOOK,
        state.get("notices", []),
    )
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
        return

    if "Due Date" in upcoming_overview_df.columns:
        upcoming_overview_df["Due Date"] = pd.to_datetime(
            upcoming_overview_df["Due Date"], errors="coerce"
        )
        today = pd.Timestamp(datetime.now(ZoneInfo("Europe/Zurich")).date())
        upcoming_overview_df["Due In Days"] = upcoming_overview_df["Due Date"].apply(
            lambda value: int((value.normalize() - today).days) if pd.notna(value) else None
        )
        upcoming_overview_df = upcoming_overview_df.sort_values(
            by=["Due Date", "Investor", "Fund Name"],
            na_position="last",
        )

    overview_slice_df = upcoming_overview_df.head(4).copy()
    overview_display_df = prepare_upcoming_capital_calls_display(overview_slice_df)
    if "Due In Days" in overview_slice_df.columns:
        overview_display_df["Due In Days"] = (
            overview_slice_df["Due In Days"].round().astype("Int64")
        )

    overview_columns = [
        col
        for col in ["Investor / Limited Partner", "Fund Name", "Amount", "Due Date", "Due In Days"]
        if col in overview_display_df.columns
    ]
    st.dataframe(
        build_table_styler(
            overview_display_df[overview_columns],
            amount_columns=["Amount"],
            date_columns=["Due Date"],
        ),
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

    upcoming_total = float(overview_slice_df["Amount"].fillna(0).sum()) if "Amount" in overview_slice_df.columns else 0.0
    next_due_date = (
        overview_slice_df["Due Date"].dropna().min().strftime("%d.%m.%Y")
        if "Due Date" in overview_slice_df.columns
        and not overview_slice_df["Due Date"].dropna().empty
        else "-"
    )
    st.caption(
        f"Upcoming Capital Calls: {len(overview_slice_df)} | Total upcoming amount: "
        f"{format_currency_display(upcoming_total)} | Next due date: {next_due_date}"
    )
