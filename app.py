from pathlib import Path
import base64
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
BRANDING_DIR = BASE_DIR / "assets" / "branding"

# Preferred file order:
# 1) SVG if available
# 2) clean transparent PNG
# 3) fallback PNG
LOGO_CANDIDATES = [
    BRANDING_DIR / "calibrium_logo.svg",
    BRANDING_DIR / "calibrium_logo_clean.png",
    BRANDING_DIR / "calibrium_logo.png",
]

LOGO_ICON = BRANDING_DIR / "calibrium_icon.png"

def get_first_existing(paths):
    for path in paths:
        if path.exists():
            return path
    return None

LOGO_FILE = get_first_existing(LOGO_CANDIDATES)

def image_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")

def get_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".svg":
        return "image/svg+xml"
    if suffix == ".png":
        return "image/png"
    if suffix in [".jpg", ".jpeg"]:
        return "image/jpeg"
    return "application/octet-stream"

def render_logo_html(path: Path, max_width_px: int = 250) -> str:
    mime_type = get_mime_type(path)
    encoded = image_to_base64(path)
    return f"""
        <div class="sidebar-logo-wrap">
            <img
                src="data:{mime_type};base64,{encoded}"
                class="sidebar-logo-img"
                style="max-width: {max_width_px}px;"
                alt="Calibrium logo"
            />
        </div>
    """

st.set_page_config(
    page_title="Project Sentinel",
    page_icon=str(LOGO_ICON) if LOGO_ICON.exists() else "C",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container,
        div[data-testid="stAppViewBlockContainer"] {
            padding-top: 2.6rem;
            padding-bottom: 2rem;
            padding-left: 2rem;
            padding-right: 2rem;
            overflow: visible !important;
        }

        section[data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e6e9f2;
        }

        div[data-testid="stSidebarUserContent"] {
            padding-top: 0.8rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .sidebar-logo-wrap {
            display: flex;
            justify-content: center;
            align-items: center;
            padding-top: 0.25rem;
            padding-bottom: 0.5rem;
        }

        .sidebar-logo-img {
            display: block;
            width: 100%;
            height: auto;
            object-fit: contain;
        }

        .sidebar-bottom-line {
            margin-top: 1.5rem;
            padding-top: 1rem;
            border-top: 1px solid #e6e9f2;
            text-align: center;
        }

        .sidebar-office-title {
            color: #3f56a6;
            font-size: 0.98rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
            line-height: 1.3;
            text-align: center;
        }

        .sidebar-office-details {
            color: #5f6b85;
            font-size: 0.83rem;
            line-height: 1.55;
            text-align: center;
        }

        .hero-card {
            background: linear-gradient(135deg, #f8faff 0%, #eef3ff 100%);
            border: 1px solid #dfe7fb;
            border-radius: 18px;
            padding: 28px 30px;
            margin-top: 0.35rem;
            margin-bottom: 1.25rem;
            overflow: visible !important;
        }

        .hero-eyebrow {
            color: #4b5f9e;
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            margin-bottom: 0.4rem;
        }

        .hero-title {
            color: #18233a;
            font-size: 3rem;
            font-weight: 800;
            line-height: 1.05;
            margin-bottom: 0.5rem;
            word-break: normal;
        }

        .hero-subtitle {
            color: #33415c;
            font-size: 1.15rem;
            font-weight: 500;
            margin-bottom: 0.9rem;
            line-height: 1.4;
        }

        .hero-text {
            color: #4a556f;
            font-size: 1rem;
            line-height: 1.7;
            max-width: 900px;
        }

        .section-title {
            color: #1f2a44;
            font-size: 1.35rem;
            font-weight: 700;
            margin-top: 0.2rem;
            margin-bottom: 0.8rem;
        }

        .mini-card {
            background: #ffffff;
            border: 1px solid #e7ebf3;
            border-radius: 16px;
            padding: 20px 18px;
            height: 100%;
        }

        .mini-label {
            color: #6b7280;
            font-size: 0.9rem;
            margin-bottom: 0.35rem;
        }

        .mini-value {
            color: #1f2a44;
            font-size: 1.8rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 0.2rem;
        }

        .mini-note {
            color: #6b7280;
            font-size: 0.92rem;
            line-height: 1.45;
        }

        .content-card {
            background: #ffffff;
            border: 1px solid #e7ebf3;
            border-radius: 18px;
            padding: 22px 24px;
            margin-top: 0.5rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    if LOGO_FILE is not None:
        st.markdown(render_logo_html(LOGO_FILE, max_width_px=260), unsafe_allow_html=True)

    st.divider()

    page = st.radio(
        "Navigation",
        [
            "Overview",
            "Commitment Tracker",
            "Upload Notice",
            "Validation",
            "Executed Calls",
            "Email Template",
        ],
    )

    st.markdown(
        """
        <div class="sidebar-bottom-line">
            <div class="sidebar-office-title">Private Investment Office</div>
            <div class="sidebar-office-details">
                Calibrium AG · Beethovenstrasse 33<br>
                CH-8002 Zürich · +41 55 511 12 22
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

if page == "Overview":
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-eyebrow">Treasury Operations Automation</div>
            <div class="hero-title">Project Sentinel</div>
            <div class="hero-subtitle">
                Private Equity capital call handling with extraction, controls, and approval workflow.
            </div>
            <div class="hero-text">
                This prototype is designed to centralize notice ingestion, validate commitment capacity,
                verify approved wire instructions, and support a clean human in the loop review process.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="mini-card">
                <div class="mini-label">Pipeline Status</div>
                <div class="mini-value">Ready</div>
                <div class="mini-note">Project foundation and navigation are in place.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="mini-card">
                <div class="mini-label">Core Controls</div>
                <div class="mini-value">2</div>
                <div class="mini-note">Commitment validation and wire verification.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
            <div class="mini-card">
                <div class="mini-label">Workflow Model</div>
                <div class="mini-value">4-Eye</div>
                <div class="mini-note">Human review before approval and execution.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Overview</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="content-card">
            The next implementation steps are to connect the Excel source data, ingest PDF notices,
            and surface extracted fields in a review screen before validation and execution.
        </div>
        """,
        unsafe_allow_html=True,
    )

elif page == "Commitment Tracker":
    st.markdown('<div class="section-title">Commitment Tracker</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="content-card">
            This page will display the commitment tracker and historical capital call information from the Excel file.
        </div>
        """,
        unsafe_allow_html=True,
    )

elif page == "Upload Notice":
    st.markdown('<div class="section-title">Upload Notice</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="content-card">
            Upload a capital call notice in PDF format. The extracted fields will appear here after parsing.
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader("Upload PDF notice", type=["pdf"])
    if uploaded_file is not None:
        st.success(f"Uploaded file: {uploaded_file.name}")

elif page == "Validation":
    st.markdown('<div class="section-title">Validation</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="content-card">
            This page will display the commitment check and wire verification results for the uploaded notice.
        </div>
        """,
        unsafe_allow_html=True,
    )

elif page == "Executed Calls":
    st.markdown('<div class="section-title">Executed Calls</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="content-card">
            Approved and executed capital calls will be listed here with timestamps and status history.
        </div>
        """,
        unsafe_allow_html=True,
    )

elif page == "Email Template":
    st.markdown('<div class="section-title">Email Template</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="content-card">
            The automated payment confirmation email will be generated here after approval.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.text_area(
        "Generated confirmation email",
        value="Payment confirmation email will appear here.",
        height=220,
    )