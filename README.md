# Project Sentinel

Project Sentinel is a web based Treasury Operations tool built to automate the handling of Private Equity capital calls.

## Scope
The project covers the core steps of the capital call workflow:
- PDF ingestion
- AI driven data extraction
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

## Contact
Linus V. Schneeberger  
linus.schneeberger@gmail.com
