import streamlit as st

from src.app_context import LOGO_ICON
from src.navigation import render_sidebar
from src.pages import render_page
from src.ui.layout import apply_global_styles


### Configure the overall Streamlit app shell before any UI is rendered.
###############################################################################
st.set_page_config(
    page_title="Project Sentinel",
    page_icon=str(LOGO_ICON) if LOGO_ICON.exists() else "C",
    layout="wide",
    initial_sidebar_state="expanded",
)

### Apply shared CSS, render the navigator, and delegate to the selected page module.
###############################################################################
apply_global_styles()
selected_page = render_sidebar()
render_page(selected_page)
