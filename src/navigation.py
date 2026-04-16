from __future__ import annotations

import streamlit as st

from src.app_context import LOGO_CANDIDATES
from src.ui.common import get_first_existing, get_sidebar_timestamp, render_logo_html


DASHBOARD_OPTIONS = [
    "overview",
    "approved_wires",
    "commitment_tracker",
    "investments_per_limited_partner",
]
WORKFLOW_OPTIONS = ["upload_notice", "validation", "upcoming_calls", "executed_calls"]
FUTURE_OPTIONS = ["future_next_steps"]

PAGE_LABELS = {
    "overview": "Overview",
    "approved_wires": "Approved Wires",
    "commitment_tracker": "Commitment Tracker",
    "investments_per_limited_partner": "Investments per Investor / LP",
    "upload_notice": "Upload Notice",
    "validation": "Validation",
    "upcoming_calls": "Upcoming Calls",
    "executed_calls": "Executed Calls",
    "future_next_steps": "Next Steps",
}

VALID_PAGES = set(PAGE_LABELS)


### Render the full sidebar navigator and return the currently selected page key.
###############################################################################
def render_sidebar() -> str:
    logo_file = get_first_existing(LOGO_CANDIDATES)

    with st.sidebar:
        if logo_file is not None:
            st.markdown(render_logo_html(logo_file, max_width_px=260), unsafe_allow_html=True)

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

        sidebar_group_options = {
            "sidebar_dashboard_page": DASHBOARD_OPTIONS,
            "sidebar_workflow_page": WORKFLOW_OPTIONS,
            "sidebar_future_page": FUTURE_OPTIONS,
        }

        ### Keep the grouped radio buttons aligned with the canonical page selection.
        ###############################################################################
        def sync_sidebar_group_selection(selected_page: str | None) -> None:
            for key, options in sidebar_group_options.items():
                st.session_state[key] = selected_page if selected_page in options else None

        ### Promote a radio-group selection to the global sidebar page state.
        ###############################################################################
        def set_sidebar_page_from_key(key: str) -> None:
            selected_page = st.session_state.get(key)
            st.session_state["sidebar_page"] = selected_page
            sync_sidebar_group_selection(selected_page)

        page = st.session_state.get("sidebar_page", "overview")
        if page not in VALID_PAGES:
            page = "overview"
        st.session_state["sidebar_page"] = page
        sync_sidebar_group_selection(page)

        st.markdown("**Dashboards**")
        st.radio(
            "Dashboards",
            DASHBOARD_OPTIONS,
            index=None,
            format_func=lambda value: PAGE_LABELS[value],
            key="sidebar_dashboard_page",
            on_change=set_sidebar_page_from_key,
            args=("sidebar_dashboard_page",),
            label_visibility="collapsed",
        )

        st.markdown("**Workflow**")
        st.radio(
            "Workflow",
            WORKFLOW_OPTIONS,
            index=None,
            format_func=lambda value: PAGE_LABELS[value],
            key="sidebar_workflow_page",
            on_change=set_sidebar_page_from_key,
            args=("sidebar_workflow_page",),
            label_visibility="collapsed",
        )

        st.markdown("**Future Updates**")
        st.radio(
            "Future Updates",
            FUTURE_OPTIONS,
            index=None,
            format_func=lambda value: PAGE_LABELS[value],
            key="sidebar_future_page",
            on_change=set_sidebar_page_from_key,
            args=("sidebar_future_page",),
            label_visibility="collapsed",
        )

        page = st.session_state.get("sidebar_page", page)

        st.markdown(
            """
            <div class="sidebar-bottom-line">
                <div class="sidebar-office-title">Private Investment Office</div>
                <div class="sidebar-office-details">
                    Calibrium AG · Beethovenstrasse 33<br>
                    CH-8002 Zürich · +41 55 511 12 22
                </div>
                <div class="sidebar-case-study">Case Study - Linus Schneeberger</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return page
