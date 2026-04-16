from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.commitment_tracker import (
    CommitmentDashboardData,
    apply_workflow_updates,
    ensure_commitment_dashboard_workbook,
    load_commitment_dashboard,
)


### Cache dashboard workbook parsing so repeated page renders stay responsive.
###############################################################################
@st.cache_data(show_spinner=False)
def get_commitment_dashboard(source_workbook_path: str, source_workbook_mtime: float):
    _ = source_workbook_mtime
    return load_commitment_dashboard(Path(source_workbook_path))


### Load the dashboard data and overlay current workflow notices on top of it.
###############################################################################
def load_dashboard_with_workflow(
    source_workbook: Path,
    managed_workbook: Path,
    notices: list[dict],
) -> CommitmentDashboardData:
    active_workbook = ensure_commitment_dashboard_workbook(source_workbook, managed_workbook)
    dashboard_data = get_commitment_dashboard(
        str(active_workbook),
        active_workbook.stat().st_mtime,
    )
    return apply_workflow_updates(dashboard_data, notices)
