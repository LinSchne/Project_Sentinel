from __future__ import annotations

from pathlib import Path


### Central project paths used across pages, services, and UI helpers.
###############################################################################
BASE_DIR = Path(__file__).resolve().parent.parent
BRANDING_DIR = BASE_DIR / "assets" / "branding"

### Branding asset lookup order for the sidebar logo.
###############################################################################
LOGO_CANDIDATES = [
    BRANDING_DIR / "calibrium_logo.svg",
    BRANDING_DIR / "calibrium_logo_clean.png",
    BRANDING_DIR / "calibrium_logo.png",
]

### Common file locations for persisted workflow data and managed workbooks.
###############################################################################
LOGO_ICON = BRANDING_DIR / "calibrium_icon.png"
WORKFLOW_STATE_PATH = BASE_DIR / "data" / "processed" / "workflow_state.json"
UPLOADS_DIR = BASE_DIR / "data" / "processed" / "uploads"

REFERENCE_WORKBOOK = BASE_DIR / "data" / "reference" / "IO_Case_study_Capital_Calls.xlsx"
CAPITAL_CALLS_WORKBOOK = BASE_DIR / "data" / "processed" / "capital_calls_master.xlsx"
APPROVED_WIRES_WORKBOOK = BASE_DIR / "data" / "processed" / "approved_wires_master.xlsx"

### Shared UI constants for approved wire display and form choices.
###############################################################################
APPROVED_WIRES_HIDDEN_COLUMNS = {"Comment", "Created at", "Created At"}
COMMON_CURRENCY_CODES = [
    "EUR",
    "USD",
    "GBP",
    "CHF",
    "JPY",
    "CAD",
    "AUD",
    "NZD",
    "SEK",
    "NOK",
    "DKK",
    "CZK",
    "PLN",
    "HUF",
    "RON",
    "TRY",
    "AED",
    "SAR",
    "QAR",
    "KWD",
    "BHD",
    "SGD",
    "HKD",
    "CNY",
    "CNH",
    "INR",
    "KRW",
    "TWD",
    "ZAR",
    "BRL",
    "MXN",
    "ILS",
    "Other",
]
