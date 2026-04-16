from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from src.app_context import UPLOADS_DIR, WORKFLOW_STATE_PATH
from src.workflow import load_workflow_state, save_workflow_state


### Load the persisted workflow JSON file from the managed project path.
###############################################################################
def workflow_state() -> dict:
    return load_workflow_state(WORKFLOW_STATE_PATH)


### Save the current workflow state back to disk.
###############################################################################
def persist_workflow_state(state: dict) -> None:
    save_workflow_state(WORKFLOW_STATE_PATH, state)


### Clear temporary session values used by the approved wires dialogs.
###############################################################################
def clear_approved_wire_state() -> None:
    import streamlit as st

    for key in [
        "approved_wire_show_add_dialog",
        "approved_wire_pending_record",
        "approved_wire_is_duplicate",
        "approved_wire_duplicate_details",
    ]:
        st.session_state.pop(key, None)


### Clear commitment tracker filters and reset-dialog state from the session.
###############################################################################
def clear_commitment_tracker_state() -> None:
    import streamlit as st

    for key in [
        "commitment_tracker_show_reset_dialog",
        "commitment_tracker_search",
        "commitment_tracker_investors",
        "commitment_tracker_funds",
    ]:
        st.session_state.pop(key, None)


### Clear notice-related UI state such as selected rows and feedback banners.
###############################################################################
def clear_uploaded_notice_state() -> None:
    import streamlit as st

    for key in [
        "current_notice_id",
        "upload_notice_feedback",
        "validation_feedback",
        "upcoming_calls_feedback",
        "show_notice_reset_dialog",
        "uploaded_notice_edit_id",
        "executed_email_notice_id",
        "scheduled_call_execute_id",
        "executed_email_sent_ids",
        "executed_email_sent_at",
    ]:
        st.session_state.pop(key, None)


### Remove previously uploaded notice files from the processed uploads directory.
###############################################################################
def clear_uploaded_notice_files() -> None:
    if UPLOADS_DIR.exists():
        shutil.rmtree(UPLOADS_DIR)


### Persist an uploaded PDF file to disk so it remains linked to the workflow record.
###############################################################################
def save_uploaded_notice_file(uploaded_file) -> Path:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    target_path = UPLOADS_DIR / f"{timestamp}_{uploaded_file.name}"
    target_path.write_bytes(uploaded_file.getvalue())
    return target_path


### Ensure approved-wire form state always has sensible defaults before rendering.
###############################################################################
def initialize_approved_wire_form_defaults() -> None:
    import streamlit as st

    defaults = {
        "approved_wire_currency_choice": "EUR",
        "approved_wire_currency_other": "",
        "approved_wire_status": "Active",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


### Reset the approved-wire add-record form to an empty/default state.
###############################################################################
def reset_approved_wire_form() -> None:
    import streamlit as st

    st.session_state["approved_wire_fund_name"] = ""
    st.session_state["approved_wire_beneficiary_bank"] = ""
    st.session_state["approved_wire_swift_bic"] = ""
    st.session_state["approved_wire_iban_account_number"] = ""
    st.session_state["approved_wire_currency_choice"] = "EUR"
    st.session_state["approved_wire_currency_other"] = ""
    st.session_state["approved_wire_status"] = "Active"
