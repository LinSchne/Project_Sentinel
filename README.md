# Project Sentinel

Treasury Operations Automation tool for Private Equity Capital Calls.

## Scope
This project automates the handling of capital call notices through:
- PDF ingestion
- AI based data extraction
- commitment validation
- wire instruction verification
- approval workflow
- dashboard reporting

## Tech Stack
- Python
- Streamlit
- Pandas
- PDF parsing
- LLM integration

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py