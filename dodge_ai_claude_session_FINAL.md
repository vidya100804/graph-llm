# Claude AI Coding Session Log
## Project: Dodge AI FDE — SAP O2C Graph System
## Candidate: Vidya Prasuna | vidyaprasuna11@gmail.com
## GitHub: https://github.com/vidya100804/graph-llm
## Date: March 25, 2026 | Tool: Claude (claude.ai)

---

## Session Overview
Used Claude as primary AI coding assistant throughout the build.
Total focused work: ~4 hours.

---

## Prompt 1 — Data Exploration
Prompt: "I have SAP O2C JSONL files. Help me understand structure and relationships."
Output: Identified 12 entity types, mapped all FK relationships, recommended SQLite.
Key insight: O2C data is relational — SQLite JOINs better than MongoDB for tracing flows.

---

## Prompt 2 — ETL + Database
Prompt: "Load all SAP JSONL files into SQLite with proper indexes."
Output: Python ETL loading 1,331 records across 12 tables with FK indexes.

---

## Prompt 3 — Graph Architecture
Prompt: "Design the graph model — nodes and edges."
Output: 5 node types (SO, DEL, BILL, JE, PAY), edges from FK relationships.

---

## Prompt 4 — D3.js Force Graph
Prompt: "Build D3.js v7 force-directed graph with zoom, drag, inspector, gold highlight."
Output: Full D3 simulation with colored arrows, glow filter, particle animation, glassmorphism.
Debugging: Arrow markers wrong → per-type marker defs. Nodes clustering → adjusted forces.

---

## Prompt 5 — LLM Integration
Prompt: "Integrate OPENROUTER LLM — never hallucinate, only answer from dataset."
Output: Hybrid engine (deterministic + LLM), schema in system prompt, pre-computed context.

---

## Prompt 6 — Built-in Query Engine
Prompt: "Build handlers for all 3 required spec queries plus common O2C questions."
Output: JS engine covering billing aggregation, set difference, chain validation, flow tracing.

---

## Prompt 7 — Guardrails
Prompt: "Block off-topic queries with exact guardrail response string."
Output: 4-layer guardrail (keyword whitelist, regex, LLM prompt, SQL protection).

---

## Prompt 8 — Creative UI
Prompt: "Make the UI impressive enough to wow a Dodge AI recruiter."
Output: Dark cinematic theme, animated particles, gradient UI, glow effects, glassmorphism.

---

## Prompt 9 — Single File Packaging
Prompt: "Package as single HTML file working without any server."
Output: 467KB self-contained HTML with embedded data, D3 from CDN, Groq via browser fetch.

---

## Key Bugs Fixed with Claude Assistance
1. Graph not rendering → container had no height set
2. Arrow markers wrong color → added per-type marker defs
3. Nodes clustering at origin → wrapped init in DOMContentLoaded
4. LLM giving off-topic answers → stricter system prompt
5. Particle canvas blocking clicks → pointer-events:none
6. Inspector not showing props → fixed empty string filter

---

## Architecture Decisions Made with Claude
1. SQLite over MongoDB (relational JOINs for O2C tracing)
2. Hybrid query engine (deterministic + LLM for reliability)
3. Groq over OpenAI (free tier, fastest inference)
4. Single-file HTML (zero infrastructure for demo)
5. Pre-computed context in prompts (prevents hallucination)
6. Per-type D3 arrow markers (correct color inheritance)

Total major prompts: ~25 | Follow-ups: ~40
Code generated: ~800 lines | Bugs fixed: 18
