from __future__ import annotations

import streamlit as st

from src.ui.common import render_page_hero


### Render the placeholder page reserved for future product ideas and roadmap items.
###############################################################################
def render_future_next_steps_page() -> None:
    render_page_hero(
        "Next Steps",
        "Placeholder area for future enhancements and product expansion ideas.",
        eyebrow="",
    )
    st.markdown(
        """
        <div class="content-card">
            This section is intentionally left empty for now. You can later use it for suggested next steps, roadmap ideas, and future feature extensions for the tool.
        </div>
        """,
        unsafe_allow_html=True,
    )
