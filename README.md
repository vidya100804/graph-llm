# Dodge AI — SAP Order to Cash Graph Explorer

A context graph system with LLM-powered query interface for SAP Order-to-Cash (O2C) data.

## Live Demo
Deploy `index.html` to any static host (GitHub Pages, Netlify, Vercel).

## Architecture

### Data Layer
- **Storage**: SQLite (Python build) + embedded JSON (browser runtime)
- **Dataset**: SAP O2C JSONL files → normalized into 11 relational tables
- **Graph**: D3.js force-directed graph with 180 nodes, 50 edges across 5 entity types

### Graph Model
```
SalesOrder ──HAS_DELIVERY──► Delivery
SalesOrder ──HAS_BILLING───► BillingDocument ──JOURNAL_ENTRY──► JournalEntry
                                              ──PAID_BY────────► Payment
```

**Nodes**: SalesOrder, Delivery, Billing, JournalEntry, Payment
**Edges**: derived from foreign key relationships in SAP data

### LLM Integration
- **Provider**: OpenRouter or Groq
- **Strategy**: Hybrid approach
  1. Pattern-based built-in engine handles common O2C queries deterministically
  2. OPENROUTER LLM enriches/validates answers with natural language
  3. Falls back gracefully if no API key

### Prompting Strategy
- System prompt includes full schema + entity relationships + key foreign keys
- User message includes data context (pre-computed results) to ground LLM response
- Temperature=0.1 for consistent factual answers
- Max 300 tokens to keep responses concise

### Guardrails
- Domain keyword whitelist (order, billing, payment, delivery, SAP, etc.)
- Off-topic regex patterns (weather, sports, celebrities, math equations)
- SQL injection protection: only SELECT queries allowed in backend version
- LLM constrained to dataset domain via system prompt
- Exact response string for off-topic: "This system is designed to answer questions related to the SAP Order-to-Cash dataset only."

## Deployment (Single File)
```bash
# Option 1: GitHub Pages
git init && git add . && git commit -m "init"
git push to GitHub → enable Pages → done

# Option 2: Netlify
drag index.html to netlify.com/drop

# Option 3: Python local server
python3 -m http.server 8080
```

## Backend Version (Flask)
```bash
cd backend
pip install flask flask-cors requests
OPENROUTER_API_KEY=your_key OPENROUTER_MODEL=openai/gpt-4o-mini python app.py

# Or with Groq
GROQ_API_KEY=your_key python app.py
```

## Full-Stack Deploy On Render
This repo is prepared for a single-service deployment on Render using the included `Dockerfile` and `render.yaml`.

Steps:
1. Push this repo to GitHub.
2. In Render, choose `New +` -> `Blueprint` or `Web Service`.
3. Connect this GitHub repo.
4. If using `Blueprint`, Render will detect `render.yaml` automatically.
5. Add environment variables if needed:
   - `OPENROUTER_API_KEY`
   - `OPENROUTER_MODEL`
   - `GROQ_API_KEY`
   - `LLM_PROVIDER`
6. Deploy.

The deployed app serves the built React frontend from Flask, so you only need one web service.

## Database Choice: SQLite + JSON
- SQLite for build-time data processing (Python)
- Embedded JSON in HTML for zero-backend browser deployment
- Tradeoff: larger file size vs zero infrastructure requirement

## Key Features
- Interactive D3 force-directed graph with zoom/pan/drag
- Node inspector with full metadata on click
- Natural language chat interface
- Graph node highlighting based on query results
- Built-in query engine for common O2C patterns
- Full guardrail system blocking off-topic queries
- Responsive data table for query results

## Dataset
SAP Order-to-Cash JSONL dataset with:
- 100 Sales Orders | 86 Deliveries | 163 Billing Documents
- 123 Journal Entries | 120 Payments | 69 Products

## Tech Stack
- Frontend: Vanilla JS + D3.js v7
- Backend: Flask + SQLite (Python)
- LLM: OpenRouter or Groq
- No build tools required for single-file version
