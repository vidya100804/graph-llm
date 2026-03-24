# Claude AI Coding Session Log
## Task: Dodge AI FDE Assessment — SAP O2C Graph System
## Date: March 26, 2026

### Session Overview
Used Claude (claude.ai) as primary AI assistant throughout the build.

---

### Prompt 1 — Data Exploration
**Prompt**: "I have SAP Order-to-Cash JSONL files. Help me understand the data structure and key relationships between entities."
**Output**: Identified 11 entity types, key foreign key relationships, record counts per table

### Prompt 2 — Architecture Decision
**Prompt**: "Design a graph-based system for SAP O2C data. What should the nodes and edges be? What database should I use for a zero-infrastructure deployment?"
**Output**: 
- Nodes: SalesOrder, Delivery, Billing, JournalEntry, Payment
- Edges derived from: referenceSdDocument, billingDocument→referenceDocument, invoiceReference
- Decision: SQLite for build + embedded JSON for browser runtime (zero backend needed)

### Prompt 3 — Graph Visualization
**Prompt**: "Build a D3.js force-directed graph with node inspection, zoom/pan, and color coding by entity type."
**Output**: Full D3 force simulation with drag, zoom, tooltip, click-to-inspect

### Prompt 4 — LLM Integration Strategy
**Prompt**: "Design a prompting strategy for NL→query translation that is grounded in data and handles guardrails."
**Output**: 
- Hybrid: built-in pattern engine + Groq LLM enrichment
- Schema in system prompt with entity relationships
- Data context passed with each user query
- Temperature 0.1 for factual consistency

### Prompt 5 — Guardrails Implementation
**Prompt**: "Implement guardrails that block off-topic queries and restrict the system to O2C domain only."
**Output**: 
- Domain keyword whitelist
- Off-topic regex patterns
- Exact response string as required by spec
- SQL injection prevention

### Prompt 6 — Built-in Query Engine
**Prompt**: "Build a deterministic query engine for common O2C queries: top products by billing count, broken flows, delivered not billed, flow tracing."
**Output**: JavaScript query engine covering all 4 required example queries from the spec

### Prompt 7 — Single-File Deployment
**Prompt**: "Package everything as a single HTML file that works without a server, with embedded data."
**Output**: 467KB self-contained index.html with all data embedded

### Debugging Iterations
1. Fixed D3 node highlight not updating during simulation tick
2. Fixed broken flow detection logic (delivery → billing → payment chain)
3. Fixed regex escape in single-file template generation
4. Handled null values in SAP JSONL fields gracefully

### Key Architectural Decisions Made with AI Assistance
1. **Hybrid query engine**: AI suggested combining deterministic pattern matching with LLM for reliability
2. **Embedded JSON vs API calls**: AI recommended zero-infrastructure approach for demo deployment
3. **Groq over OpenAI**: AI recommended Groq free tier for faster inference and no cost
4. **D3 force simulation**: AI recommended force-directed over tree layout for complex O2C relationships
