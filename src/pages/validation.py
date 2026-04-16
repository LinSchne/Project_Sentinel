from __future__ import annotations

import pandas as pd
import streamlit as st

from src.approved_wires import load_approved_wires
from src.app_context import APPROVED_WIRES_WORKBOOK, CAPITAL_CALLS_WORKBOOK, REFERENCE_WORKBOOK
from src.commitment_tracker import ensure_commitment_dashboard_workbook, load_commitment_dashboard
from src.services.dashboard_service import load_dashboard_with_workflow
from src.state import persist_workflow_state, workflow_state
from src.ui.common import (
    build_approved_wire_suggestions,
    format_currency_display,
    render_page_hero,
    render_record_summary,
    render_validation_summary,
)
from src.validator import validate_notice
from src.workflow import (
    approve_notice,
    delete_notice_by_id,
    get_notice_by_id,
    notices_to_dataframe,
    schedule_notice,
    set_notice_validation,
    upsert_notice,
)


### Render the validation page where notices are checked, reviewed, and approved or rejected.
###############################################################################
def render_validation_page() -> None:
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
                "Investor / Limited Partner": selected_notice.get("investor", ""),
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

            dashboard_data = load_dashboard_with_workflow(
                REFERENCE_WORKBOOK,
                CAPITAL_CALLS_WORKBOOK,
                state.get("notices", []),
            )
            commitment_workbook = ensure_commitment_dashboard_workbook(
                REFERENCE_WORKBOOK,
                CAPITAL_CALLS_WORKBOOK,
            )
            source_dashboard_data = load_commitment_dashboard(commitment_workbook)
            approved_wires_df = load_approved_wires(REFERENCE_WORKBOOK, APPROVED_WIRES_WORKBOOK)
            approved_wire_suggestions = build_approved_wire_suggestions(
                selected_notice,
                approved_wires_df,
            )

            validation_result = validate_notice(
                selected_notice,
                dashboard_data.tracker_df,
                approved_wires_df,
                notices=state.get("notices", []),
                historical_upcoming_df=source_dashboard_data.upcoming_df,
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
            investor_check = validation_result["investor_check"]
            wire_check = validation_result["wire_check"]

            detail_col1, detail_col2, detail_col3 = st.columns(3)
            with detail_col1:
                st.markdown("**Commitment Check Details**")
                st.write(f"Matched fund: {commitment_check.get('matched_fund') or '-'}")
                if commitment_check.get("remaining_open_commitment") is not None:
                    st.write(
                        "Remaining open commitment before scheduled calls: "
                        f"{format_currency_display(float(commitment_check['remaining_open_commitment']))}"
                    )
                historical_upcoming_amount = float(
                    commitment_check.get("historical_upcoming_amount", 0) or 0
                )
                if historical_upcoming_amount > 0:
                    st.warning(
                        "Already pending in historical Upcoming Capital Calls: "
                        f"{format_currency_display(historical_upcoming_amount)}"
                    )
                    st.caption(
                        "Historical upcoming capital calls already reserving commitment: "
                        f"{len(commitment_check.get('historical_upcoming_entries', []))}"
                    )
                workflow_scheduled_amount = float(
                    commitment_check.get("workflow_scheduled_amount", 0) or 0
                )
                if workflow_scheduled_amount > 0:
                    st.info(
                        "Already scheduled in workflow Upcoming Capital Calls: "
                        f"{format_currency_display(workflow_scheduled_amount)}"
                    )
                    st.caption(
                        "Workflow-scheduled capital calls already reserving commitment: "
                        f"{len(commitment_check.get('workflow_scheduled_entries', []))}"
                    )
                scheduled_amount = float(commitment_check.get("scheduled_amount", 0) or 0)
                if scheduled_amount > 0:
                    st.write(
                        "Total reserved by Upcoming Capital Calls: "
                        f"{format_currency_display(scheduled_amount)}"
                    )
                if commitment_check.get("adjusted_remaining_open_commitment") is not None:
                    st.write(
                        "Remaining open commitment after scheduled calls: "
                        f"{format_currency_display(float(commitment_check['adjusted_remaining_open_commitment']))}"
                    )
            with detail_col2:
                st.markdown("**Investor Check Details**")
                st.write(f"Extracted Investor / Limited Partner: {selected_notice.get('investor') or '-'}")
                st.write(f"Matched Investor / Limited Partner: {investor_check.get('matched_investor') or '-'}")
            with detail_col3:
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

            action_col1, action_col2, action_col3, action_col4 = st.columns([1, 1, 1, 2])
            with action_col1:
                if st.button(
                    "Approve and Move to Executed Capital Calls",
                    use_container_width=True,
                    disabled=not approval_allowed,
                ):
                    selected_notice["investor"] = investor_check.get("matched_investor") or selected_notice.get("investor", "")
                    selected_notice = set_notice_validation(selected_notice, validation_result)
                    selected_notice = approve_notice(selected_notice)
                    upsert_notice(state, selected_notice)
                    persist_workflow_state(state)
                    st.session_state["current_notice_id"] = selected_notice["id"]
                    st.session_state["validation_feedback"] = (
                        "Notice approved and moved to Executed Capital Calls."
                    )
                    st.rerun()
            with action_col2:
                if st.button(
                    "Schedule Upcoming Capital Call",
                    use_container_width=True,
                    disabled=not approval_allowed,
                ):
                    selected_notice["investor"] = investor_check.get("matched_investor") or selected_notice.get("investor", "")
                    selected_notice = set_notice_validation(selected_notice, validation_result)
                    selected_notice = schedule_notice(selected_notice)
                    upsert_notice(state, selected_notice)
                    persist_workflow_state(state)
                    st.session_state["validation_feedback"] = (
                        "Notice scheduled and moved to Upcoming Capital Calls."
                    )
                    st.rerun()
            with action_col3:
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
