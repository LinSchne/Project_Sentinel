from __future__ import annotations

import streamlit as st


### Shared CSS for layout, cards, sidebar, dialogs, and visual consistency across pages.
###############################################################################
GLOBAL_STYLES = """
    <style>
        .block-container,
        div[data-testid="stAppViewBlockContainer"] {
            padding-top: 2.6rem;
            padding-bottom: 2rem;
            padding-left: 2rem;
            padding-right: 2rem;
            overflow: visible !important;
        }

        div[data-testid="stDialog"] div[role="dialog"] {
            width: min(1100px, 92vw);
        }

        div[data-testid="stFileUploader"] > section {
            padding: 0.95rem 1rem;
            min-height: 5.25rem;
            border-radius: 18px;
        }

        div[data-testid="stFileUploaderDropzone"] {
            padding: 0.7rem 0.85rem;
            min-height: 3.9rem;
            display: flex;
            align-items: center;
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

        .sidebar-timestamp {
            text-align: center;
            margin-top: 0.15rem;
            margin-bottom: 0.85rem;
        }

        .sidebar-timestamp-label {
            color: #7a8499;
            font-size: 0.76rem;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.2rem;
        }

        .sidebar-timestamp-date {
            color: #1f2a44;
            font-size: 1rem;
            font-weight: 700;
            line-height: 1.25;
        }

        .sidebar-timestamp-time {
            color: #4b5f9e;
            font-size: 0.92rem;
            font-weight: 600;
            line-height: 1.3;
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

        .sidebar-case-study {
            color: #3f56a6;
            font-size: 0.82rem;
            font-weight: 600;
            line-height: 1.45;
            text-align: center;
            margin-top: 0.55rem;
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

        .page-title {
            color: #1f2a44;
            font-size: 2.9rem;
            font-weight: 800;
            line-height: 1.05;
            margin-top: 0.1rem;
            margin-bottom: 1.1rem;
        }

        .mini-card {
            background: #ffffff;
            border: 1px solid #e7ebf3;
            border-radius: 16px;
            padding: 18px 18px;
            min-height: 180px;
            height: 100%;
            display: flex;
            flex-direction: column;
        }

        .mini-card-muted {
            background: #f5f6f8;
            border-color: #dde2eb;
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
            margin-bottom: 0.4rem;
        }

        .mini-note {
            color: #6b7280;
            font-size: 0.92rem;
            line-height: 1.45;
            margin-top: auto;
        }

        .content-card {
            background: #ffffff;
            border: 1px solid #e7ebf3;
            border-radius: 18px;
            padding: 22px 24px;
            margin-top: 0.5rem;
        }
    </style>
"""


### Inject the shared CSS rules into the active Streamlit app.
###############################################################################
def apply_global_styles() -> None:
    st.markdown(GLOBAL_STYLES, unsafe_allow_html=True)
