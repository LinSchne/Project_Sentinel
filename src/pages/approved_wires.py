from __future__ import annotations

import streamlit as st

from src.approved_wires import (
    apply_approved_wires_filters,
    editable_columns_for_ui,
    load_approved_wires,
    save_approved_wires,
    update_editable_fields,
)
from src.app_context import APPROVED_WIRES_WORKBOOK, REFERENCE_WORKBOOK
from src.state import initialize_approved_wire_form_defaults
from src.ui.common import build_approved_wires_display_df, render_page_hero
from src.ui.dialogs import (
    approved_wire_add_dialog,
    approved_wire_confirmation_dialog,
    approved_wires_reset_dialog,
)


### Render the approved-wires administration screen with filters, editing, and dialogs.
###############################################################################
def render_approved_wires_page() -> None:
    render_page_hero(
        "Approved Wires",
        "Maintain and review approved wire instructions used for payment verification.",
        eyebrow="",
    )

    master_df = load_approved_wires(
        source_workbook=REFERENCE_WORKBOOK,
        managed_workbook=APPROVED_WIRES_WORKBOOK,
    )

    if st.session_state.get("approved_wire_pending_record"):
        approved_wire_confirmation_dialog(master_df, APPROVED_WIRES_WORKBOOK)
    if st.session_state.get("approved_wire_show_add_dialog"):
        approved_wire_add_dialog(master_df)
    if st.session_state.get("approved_wire_show_reset_dialog"):
        approved_wires_reset_dialog(REFERENCE_WORKBOOK, APPROVED_WIRES_WORKBOOK)

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

    editable_cols = [col for col in editable_columns_for_ui(filtered_df) if col in display_df.columns]

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
    inactive_count = int(filtered_df["Status"].eq("Inactive").sum()) if "Status" in filtered_df.columns else 0
    st.caption(
        f"Total wires: {len(filtered_df)} | Active: {active_count} | Inactive: {inactive_count}"
    )

    action_col1, action_col2, action_col3, _action_spacer = st.columns([1, 1, 1, 2])

    with action_col1:
        if st.button("Save Changes", use_container_width=True):
            updated_master = update_editable_fields(master_df, edited_df)
            save_approved_wires(updated_master, APPROVED_WIRES_WORKBOOK)
            st.success("Approved wires updated successfully.")
            st.rerun()

    with action_col2:
        if st.button("Add New Record", use_container_width=True):
            st.session_state["approved_wire_show_add_dialog"] = True
            st.rerun()

    with action_col3:
        if st.button("Reset to Source", use_container_width=True):
            st.session_state["approved_wire_show_reset_dialog"] = True
            st.rerun()

    feedback_message = st.session_state.pop("approved_wire_feedback", None)
    if feedback_message:
        st.success(feedback_message)

    initialize_approved_wire_form_defaults()
