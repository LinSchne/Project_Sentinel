from __future__ import annotations

import streamlit as st

from src.ui.common import render_page_hero


### Render the placeholder page reserved for future product ideas and roadmap items.
###############################################################################
def render_future_next_steps_page() -> None:
    render_page_hero(
        "Next Steps",
        "Proposed extensions that could evolve the prototype into a more scalable production solution.",
        eyebrow="",
    )

    roadmap_items = [
        (
            "1. User Profiles and Role Based Validation",
            "Introduce secure user profiles with username and password access. "
            "Validation should be executable by multiple users instead of relying on a single person. "
            "Beyond timestamps and last-edited information, the application should maintain a clear audit trail showing who performed which action and when.",
        ),
        (
            "2. Database Integration",
            "Extend the application with a database such as MongoDB to store and structure data in a more scalable and reliable way. "
            "This would move the prototype beyond file-based handling and support cleaner data organization, better consistency, and easier future development.",
        ),
        (
            "3. Transition from a Local LLM to an Enterprise Grade Azure OpenAI Setup",
            "Replace the current local Ollama-based setup with a larger deployed OpenAI model through Azure. "
            "This would provide a more scalable and production-ready AI foundation, with stronger performance, better maintainability, and easier enterprise integration.",
        ),
        (
            "4. Application Deployment",
            "Deploy the application in a stable and accessible environment so it can be used beyond a purely local prototype setup. "
            "This would improve accessibility for multiple users and create a stronger base for scaling, maintenance, and integration into existing business processes.",
        ),
        (
            "5. Full Private Equity Investment Cycle Tracking",
            "Expand the prototype so it does not only track capital calls, but also distributions back to us. "
            "This would allow the system to reflect the full private equity investment cycle for each Investor / Limited Partner, "
            "including the development of contributions and distributions over time and the visualisation of the J-curve.",
        ),
        (
            "6. Continuous Improvement Through User Feedback",
            "Establish a structured process to collect user feedback on a regular basis. "
            "That feedback should then be used to continuously improve, refine, and expand the prototype based on practical needs and real user experience.",
        ),
    ]

    for title, description in roadmap_items:
        st.markdown(
            f"""
            <div class="content-card" style="margin-bottom: 1rem;">
                <div style="font-size: 1.15rem; font-weight: 700; color: #1b2743; margin-bottom: 0.45rem;">
                    {title}
                </div>
                <div style="font-size: 1rem; line-height: 1.6; color: #44506a;">
                    {description}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
