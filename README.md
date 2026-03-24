# Dodge AI - SAP Order to Cash Graph Explorer

A graph-based SAP Order-to-Cash (O2C) explorer with a React frontend, Flask backend, SQLite data processing, and OpenRouter-powered natural language querying.

## Repository Structure

- `src/` - top-level source map for reviewers and collaborators
- `frontend/` - React application source and build tooling
- `backend/` - Flask API, SQLite-backed query engine, and dataset import scripts
- `sessions/` - project session notes and handoff artifacts
- `README.md` - setup, architecture, and deployment instructions

## Setup Instructions

### Prerequisites

- Node.js 18+
- Python 3.10+
- An OpenRouter API key

### Frontend setup

```bash
cd frontend
npm install
npm start
```

The React app runs on `http://localhost:3000` and proxies API calls to the Flask backend.

### Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Set the required environment variables before starting the server:

```powershell
$env:OPENROUTER_API_KEY="your_openrouter_key"
$env:OPENROUTER_MODEL="openai/gpt-4o-mini"
$env:LLM_PROVIDER="openrouter"
python app.py
```

The Flask API runs on `http://localhost:5000`.

### Full local run

Open two terminals:

```bash
cd backend
python app.py
```

```bash
cd frontend
npm install
npm start
```

### Optional environment variables

- `OPENROUTER_API_KEY` - required for OpenRouter access
- `OPENROUTER_MODEL` - defaults to `openai/gpt-4o-mini`
- `OPENROUTER_APP_NAME` - defaults to `Dodge AI O2C Explorer`
- `OPENROUTER_SITE_URL` - defaults to `http://localhost:5000`
- `LLM_PROVIDER` - set to `openrouter` to force OpenRouter
- `GROQ_API_KEY` - optional fallback provider

## Architecture

### Data Layer

- Storage: SQLite (Python build) plus embedded JSON (browser runtime)
- Dataset: SAP O2C JSONL files normalized into relational tables
- Graph: D3 force-directed graph across core O2C entities

### Graph Model

```text
SalesOrder --HAS_DELIVERY--> Delivery
SalesOrder --HAS_BILLING--> BillingDocument --JOURNAL_ENTRY--> JournalEntry
BillingDocument --PAID_BY--> Payment
```

Nodes include SalesOrder, Delivery, Billing, JournalEntry, and Payment.

### LLM Integration

- Provider: OpenRouter (primary), with optional Groq fallback
- Strategy:
  1. Pattern-based logic handles common O2C queries deterministically
  2. OpenRouter enriches and validates responses in natural language
  3. The app falls back gracefully if no API key is provided

### Prompting Strategy

- System prompt includes schema, relationships, and important foreign keys
- User prompts are grounded with pre-computed data context
- Low temperature is used for consistent factual answers

### Guardrails

- Domain keyword whitelist for SAP O2C concepts
- Off-topic blocking for unrelated questions
- Backend only permits safe `SELECT` query generation
- Responses are constrained to the imported dataset domain

## Deployment

### Static single-file demo

Deploy `index.html` to any static host such as GitHub Pages, Netlify, or Vercel.

### Backend version

```bash
cd backend
pip install -r requirements.txt
OPENROUTER_API_KEY=your_key OPENROUTER_MODEL=openai/gpt-4o-mini python app.py
```

### Render deployment

This repository includes `Dockerfile` and `render.yaml` for single-service deployment on Render.

1. Push this repository to GitHub.
2. Create a new Render Blueprint or Web Service.
3. Connect the GitHub repository.
4. Add environment variables such as `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, and `LLM_PROVIDER`.
5. Deploy.

## Key Features

- Interactive graph with zoom, pan, and drag
- Node inspector with metadata
- Natural language chat interface
- Query-driven graph highlighting
- Guardrails for off-topic and unsafe requests
- Responsive query result views

## Dataset

SAP Order-to-Cash JSONL dataset with sales orders, deliveries, billing documents, journal entries, payments, and products.

## Tech Stack

- Frontend: React, D3.js
- Backend: Flask, SQLite
- LLM provider: OpenRouter
