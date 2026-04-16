from __future__ import annotations

import pandas as pd
import streamlit as st

from src.extractor import extract_notice_fields
from src.pdf_reader import extract_text_from_pdf_bytes
from src.state import persist_workflow_state, save_uploaded_notice_file, workflow_state
from src.ui.common import (
    build_table_styler,
    compact_iban_display,
    open_uploaded_notice_editor_for_checked_rows,
    render_page_hero,
)
from src.ui.dialogs import edit_uploaded_notice_dialog, review_notice_dialog, uploaded_notices_reset_dialog
from src.workflow import (
    create_notice_record,
    get_notice_by_id,
    notices_to_dataframe,
    upsert_notice,
)


### Render the PDF upload and notice review screen that starts the workflow.
###############################################################################
def render_upload_notice_page() -> None:
    render_page_hero(
        "Upload Notice",
        "Upload and extract capital call notices before review and validation.",
        eyebrow="",
    )
    st.markdown(
        """
        <div class="content-card">
            Upload a capital call notice PDF. The prototype extracts the core notice fields and stores the notice for validation.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("show_notice_reset_dialog"):
        uploaded_notices_reset_dialog()

    uploaded_file = st.file_uploader("File Dropzone", type=["pdf"])

    if uploaded_file is not None:
        st.info(f"Ready to extract: {uploaded_file.name}")

        if st.button("Extract Notice Data", use_container_width=True):
            with st.spinner("Extracting notice data..."):
                pdf_path = save_uploaded_notice_file(uploaded_file)
                raw_text = extract_text_from_pdf_bytes(uploaded_file.getvalue())
                extracted = extract_notice_fields(raw_text, filename=uploaded_file.name)
                extracted["pdf_path"] = str(pdf_path)

                notice_record = create_notice_record(extracted)
                state = workflow_state()
                upsert_notice(state, notice_record)
                persist_workflow_state(state)

                st.session_state["current_notice_id"] = notice_record["id"]
                st.session_state["upload_notice_feedback"] = (
                    "Notice uploaded and extracted successfully."
                )
                st.rerun()

    upload_feedback = st.session_state.pop("upload_notice_feedback", None)
    if upload_feedback:
        st.success(upload_feedback)

    state = workflow_state()
    review_notices_df = notices_to_dataframe(state.get("notices", []), statuses=["review"])

    if not review_notices_df.empty:
        review_notice = (
            get_notice_by_id(state, st.session_state.get("current_notice_id", ""))
            if st.session_state.get("current_notice_id")
            else None
        )
        if review_notice is None or review_notice.get("status") != "review":
            review_notice = get_notice_by_id(state, review_notices_df.iloc[0]["id"])

        if review_notice:
            review_notice_dialog(review_notice)

    notices_df = notices_to_dataframe(state.get("notices", []), statuses=["uploaded", "validated", "executed"])
    if st.session_state.get("uploaded_notice_edit_id") and not notices_df.empty:
        selected_uploaded_notice = get_notice_by_id(state, st.session_state["uploaded_notice_edit_id"])
        if selected_uploaded_notice:
            edit_uploaded_notice_dialog(selected_uploaded_notice)

    if notices_df.empty:
        return

    upload_display_df = notices_df.copy()
    upload_display_df["Select"] = False
    if "amount" in upload_display_df.columns:
        upload_display_df["amount"] = pd.to_numeric(upload_display_df["amount"], errors="coerce")
    if "due_date" in upload_display_df.columns:
        upload_display_df["due_date"] = pd.to_datetime(
            upload_display_df["due_date"], errors="coerce"
        )
    for source_col, display_col in [
        ("beneficiary_bank", "bank"),
        ("iban", "iban"),
        ("swift", "swift"),
    ]:
        if source_col in upload_display_df.columns:
            upload_display_df[display_col] = upload_display_df[source_col].apply(
                lambda value: "-" if value in (None, "") or pd.isna(value) else str(value)
            )
        else:
            upload_display_df[display_col] = "-"
    upload_display_df["iban_short"] = upload_display_df["iban"].apply(compact_iban_display)
    preview_columns = [
        col
        for col in ["Select", "fund_name", "investor", "amount", "bank", "iban_short", "swift", "due_date", "status"]
        if col in upload_display_df.columns
    ]
    st.markdown("### Uploaded Notices")
    upload_table_df = upload_display_df[preview_columns].rename(
        columns={
            "Select": "Select",
            "fund_name": "Fund Name",
            "investor": "Investor / Limited Partner",
            "amount": "Amount",
            "bank": "Bank",
            "iban_short": "IBAN",
            "swift": "SWIFT",
            "due_date": "Due",
            "status": "Status",
        }
    )
    edited_upload_df = st.data_editor(
        build_table_styler(
            upload_table_df,
            amount_columns=["Amount"],
            date_columns=["Due"],
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", width="small"),
            "Fund Name": st.column_config.TextColumn("Fund Name", disabled=True, width="medium"),
            "Investor / Limited Partner": st.column_config.TextColumn("Investor / Limited Partner", disabled=True, width="medium"),
            "Bank": st.column_config.TextColumn("Bank", disabled=True, width="medium"),
            "IBAN": st.column_config.TextColumn("IBAN", disabled=True, width="medium"),
            "SWIFT": st.column_config.TextColumn("SWIFT", disabled=True, width="small"),
            "Status": st.column_config.TextColumn("Status", disabled=True, width="small"),
        },
        disabled=["Fund Name", "Investor / Limited Partner", "Amount", "Bank", "IBAN", "SWIFT", "Due", "Status"],
        key="uploaded_notices_editor",
    )

    checked_rows = edited_upload_df.index[edited_upload_df["Select"]].tolist()
    table_action_col1, table_action_col2, table_action_col3 = st.columns([1, 1, 3])
    with table_action_col1:
        if st.button("Edit Selected Notice", use_container_width=True):
            if len(checked_rows) != 1:
                st.warning("Please select exactly one notice.")
            elif open_uploaded_notice_editor_for_checked_rows(checked_rows, notices_df.reset_index(drop=True)):
                st.rerun()
    with table_action_col2:
        if st.button("Delete All Notices", use_container_width=True):
            st.session_state["show_notice_reset_dialog"] = True
            st.rerun()
