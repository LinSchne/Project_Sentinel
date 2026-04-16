from __future__ import annotations

from src.pages.approved_wires import render_approved_wires_page
from src.pages.commitment_tracker import render_commitment_tracker_page
from src.pages.executed_calls import render_executed_calls_page
from src.pages.future import render_future_next_steps_page
from src.pages.investments import render_investments_per_limited_partner_page
from src.pages.overview import render_overview_page
from src.pages.upcoming_calls import render_upcoming_calls_page
from src.pages.upload_notice import render_upload_notice_page
from src.pages.validation import render_validation_page


### Central mapping from navigator page keys to page render functions.
###############################################################################
PAGE_RENDERERS = {
    "overview": render_overview_page,
    "approved_wires": render_approved_wires_page,
    "commitment_tracker": render_commitment_tracker_page,
    "investments_per_limited_partner": render_investments_per_limited_partner_page,
    "upload_notice": render_upload_notice_page,
    "validation": render_validation_page,
    "upcoming_calls": render_upcoming_calls_page,
    "executed_calls": render_executed_calls_page,
    "future_next_steps": render_future_next_steps_page,
}


### Route the selected page key to the correct page-rendering function.
###############################################################################
def render_page(page: str) -> None:
    renderer = PAGE_RENDERERS.get(page, render_overview_page)
    renderer()
