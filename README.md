# Project Sentinel

Project Sentinel is a Streamlit-based Treasury Operations prototype for handling Private Equity capital calls. The app combines PDF ingestion, notice extraction, validation against commitment and approved wire data, approval handling, and reporting views in one workflow.

## Scope

The project currently covers these workflow steps:

- PDF ingestion of capital call notices
- AI-assisted or rule-based field extraction
- commitment validation against the capital call workbook
- wire instruction verification against approved wires
- approval and execution workflow
- dashboard and reporting views

## Tech Stack

- Python
- Streamlit
- Pandas
- PDF parsing
- optional local LLM integration via Ollama

## App Structure

The app is intentionally split into a small entrypoint and modular page/UI logic:

- `app.py`
  Streamlit entrypoint. Applies global layout, renders the sidebar, and routes to the selected page.
- `src/pages/`
  Contains one module per navigator view.
- `src/ui/`
  Shared UI helpers, layout styling, dialogs, formatting helpers, and small interaction utilities.
- `src/state.py`
  Session-state and workflow-state helpers, plus upload file handling.
- `src/services/`
  Shared service logic. At the moment this contains the cached dashboard-loading path.
- `src/approved_wires.py`
  Approved wire loading, filtering, duplicate detection, schema normalization, and persistence.
- `src/commitment_tracker.py`
  Workbook parsing, dashboard metrics, display preparation, and workflow overlays.
- `src/extractor.py`
  Notice field extraction via heuristics or Ollama.
- `src/validator.py`
  Commitment and wire validation logic.
- `src/workflow.py`
  Workflow state records for uploaded, validated, and executed notices.

## Navigator Views

You can describe the app in screenshots using the following navigator structure.

### Dashboards

- `Overview`
  Landing page with high-level KPIs and an overview of upcoming capital calls.
- `Approved Wires`
  Admin view for reviewing, filtering, editing, resetting, and extending approved wire instructions.
- `Commitment Tracker`
  Main operational dashboard for commitments, upcoming calls, and executed calls with filters and reset support.
- `Investments per Limited Partner`
  Investor / Limited Partner-specific view showing commitments and fund exposure.

### Workflow

- `Upload Notice`
  Upload a PDF, extract notice fields, review the extracted content, and move notices into the workflow.
- `Validation`
  Run commitment and wire checks, inspect validation details, and either execute, schedule, or reject notices.
- `Upcoming Capital Calls`
  Review scheduled capital calls and move them into `Executed Capital Calls` through a confirmation step.
- `Executed Capital Calls`
  Review executed capital calls from historical and workflow data and open payment confirmation email templates.

### Future Updates

- `Next Steps`
  Placeholder page for future ideas, roadmap items, or feature extensions.

## Typical User Flow

The normal end-to-end flow is:

1. Open `Upload Notice` and upload a capital call PDF.
2. Review and accept or edit the extracted notice data.
3. Go to `Validation` and run commitment and wire checks.
4. Either execute the notice immediately or schedule it in `Upcoming Capital Calls`.
5. Move scheduled calls from `Upcoming Capital Calls` to `Executed Capital Calls` when they are confirmed.
6. Review the result in `Executed Capital Calls` and generate the payment confirmation email.
7. Use the dashboard views for monitoring and reporting.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Local LLM with Ollama

The prototype can extract notice fields with a local Ollama model.

Example setup:

```bash
cp .env.example .env
ollama pull llama3.1:8b-instruct-q6_K
ollama serve
streamlit run app.py
```

If Ollama is unavailable, the app falls back to rule-based extraction.

## Screenshots

This README is prepared so you can add screenshots later. A practical pattern would be:

- one screenshot for the sidebar and overall layout
- one screenshot per dashboard view
- one screenshot for the upload/review flow
- one screenshot for the validation screen
- one screenshot for the upcoming-calls scheduling step
- one screenshot for executed calls and email generation

## Contact

Linus V. Schneeberger  
linus.schneeberger@gmail.com
