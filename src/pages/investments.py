from __future__ import annotations

import streamlit as st

from src.app_context import CAPITAL_CALLS_WORKBOOK, REFERENCE_WORKBOOK
from src.commitment_tracker import (
    prepare_investor_fund_detail_display,
    prepare_investor_summary_display,
)
from src.services.dashboard_service import load_dashboard_with_workflow
from src.state import workflow_state
from src.ui.common import build_table_styler, format_currency_display, render_page_hero


### Render the investor-focused limited-partner view with summary and fund detail tables.
###############################################################################
def render_investments_per_limited_partner_page() -> None:
    state = workflow_state()
    dashboard_data = load_dashboard_with_workflow(
        REFERENCE_WORKBOOK,
        CAPITAL_CALLS_WORKBOOK,
        state.get("notices", []),
    )
    tracker_df = dashboard_data.tracker_df.copy()

    render_page_hero(
        "Investments per Investor / Limited Partner",
        "Review commitments and fund exposures by Investor / Limited Partner.",
        eyebrow="",
    )

    investor_options = sorted(tracker_df["Investor"].dropna().astype(str).unique().tolist())
    selected_investor = st.selectbox(
        "Investor / Limited Partner",
        options=investor_options,
        index=0 if investor_options else None,
        placeholder="Select an Investor / Limited Partner",
    )

    if not selected_investor:
        st.info("No investors are available.")
        return

    investor_filtered_df = tracker_df[tracker_df["Investor"].astype(str).eq(selected_investor)].copy()
    investor_summary_df = prepare_investor_summary_display(investor_filtered_df)
    investor_detail_df = prepare_investor_fund_detail_display(investor_filtered_df)

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    with metric_col1:
        st.markdown(
            f"""
            <div class="mini-card">
                <div class="mini-label">Investor / Limited Partner</div>
                <div class="mini-value" style="font-size:1.25rem;">{selected_investor}</div>
                <div class="mini-note">Selected Investor / Limited Partner view.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with metric_col2:
        st.markdown(
            f"""
            <div class="mini-card">
                <div class="mini-label">Funds</div>
                <div class="mini-value">{len(investor_filtered_df)}</div>
                <div class="mini-note">Funds in which this Investor / Limited Partner is invested.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with metric_col3:
        total_commitment = float(investor_filtered_df["Total Commitment"].sum()) if "Total Commitment" in investor_filtered_df.columns else 0
        st.markdown(
            f"""
                <div class="mini-card">
                <div class="mini-label">Total Commitment</div>
                <div class="mini-value" style="font-size:1.55rem;">{format_currency_display(total_commitment)}</div>
                <div class="mini-note">Aggregate commitment for this Investor / Limited Partner.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with metric_col4:
        remaining_open = float(investor_filtered_df["Remaining Open Commitment"].sum()) if "Remaining Open Commitment" in investor_filtered_df.columns else 0
        st.markdown(
            f"""
                <div class="mini-card mini-card-muted">
                <div class="mini-label">Remaining Open</div>
                <div class="mini-value" style="font-size:1.55rem;">{format_currency_display(remaining_open)}</div>
                <div class="mini-note">Open commitment still available for this Investor / Limited Partner.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Investor / Limited Partner Summary</div>', unsafe_allow_html=True)
    st.dataframe(
        build_table_styler(
            investor_summary_df,
            amount_columns=[
                "Total Commitment",
                "Total Funded YTD",
                "Remaining Open Commitment",
            ],
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown('<div class="section-title">Funds and Amounts</div>', unsafe_allow_html=True)
    st.dataframe(
        build_table_styler(
            investor_detail_df,
            amount_columns=[
                "Total Commitment",
                "Total Funded YTD",
                "Remaining Open Commitment",
            ],
        ),
        use_container_width=True,
        hide_index=True,
    )
