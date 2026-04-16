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

<details>
  <summary><strong>Overview</strong></summary>
  <br>
  <img width="1488" height="728" alt="Overview" src="https://github.com/user-attachments/assets/b69bced6-600b-4f56-a803-79187066c8d8" />
</details>

<details>
  <summary><strong>Approved Wires</strong></summary>
  <br>
  <img width="1488" height="725" alt="Approved Wires 1" src="https://github.com/user-attachments/assets/cbf39808-de04-4da5-85e0-8893f53dd9c6" />
  <br><br>
  <img width="1488" height="558" alt="Approved Wires 2" src="https://github.com/user-attachments/assets/9eac7104-c2a5-4bd5-ac25-6a21626e45ba" />
</details>

<details>
  <summary><strong>Commitment Tracker</strong></summary>
  <br>
  <img width="1488" height="713" alt="Commitment Tracker" src="https://github.com/user-attachments/assets/862d17c9-3391-437b-a4a1-9dea07236017" />
</details>

<details>
  <summary><strong>Investments per Investor / Limited Partner</strong></summary>
  <br>
  <img width="1488" height="747" alt="Investments per Investor / Limited Partner" src="https://github.com/user-attachments/assets/e72019b8-a379-4f06-9359-17053b76e74e" />
</details>

<details>
  <summary><strong>Upload Notice</strong></summary>
  <br>
  <img width="1488" height="719" alt="Upload Notice" src="https://github.com/user-attachments/assets/fbbbfc55-a71d-45f7-87ab-69ff583974e8" />
</details>

<details>
  <summary><strong>Validation</strong></summary>
  <br>
  <img width="1488" height="745" alt="Validation 1" src="https://github.com/user-attachments/assets/4a0b8368-d75b-4246-945d-27526c1e9e1e" />
  <br><br>
  <img width="1488" height="736" alt="Validation 2" src="https://github.com/user-attachments/assets/97889138-0143-4d62-a438-20444e8a413e" />
</details>

<details>
  <summary><strong>Upcoming Calls</strong></summary>
  <br>
  <img width="1488" height="736" alt="Upcoming Calls 1" src="https://github.com/user-attachments/assets/98b403d2-bd38-4f9b-8873-c2bdb0276f49" />
  <br><br>
  <img width="1007" height="592" alt="Upcoming Calls 2" src="https://github.com/user-attachments/assets/8f0f8624-8426-4bbc-b462-04e84d47904f" />
</details>

<details>
  <summary><strong>Executed Capital Calls</strong></summary>
  <br>
  <img width="1470" height="712" alt="Executed Capital Calls 1" src="https://github.com/user-attachments/assets/b25d7cc1-eb6e-48d5-840c-f5c4b06ac881" />
  <br><br>
  <img width="1001" height="429" alt="Executed Capital Calls 2" src="https://github.com/user-attachments/assets/cc9e9ccf-6858-4380-b4ad-5651a99696a3" />
  <br><br>
  <img width="1473" height="711" alt="Executed Capital Calls 3" src="https://github.com/user-attachments/assets/287755c7-ef86-420b-b2ae-3f783d6ea50f" />
</details>

## Contact

Linus V. Schneeberger  
linus.schneeberger@gmail.com
