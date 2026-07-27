# Work Log

## 2026-07-23 — Chat error-rendering investigation started

- Reviewed the supplied frontend and backend logs.
- Confirmed the backend recovered from the earlier proxy reset and returned healthy HTTP 200 responses, followed by an intentional structured HTTP 429 quota response.
- The browser crash indicates that an object with `{code, message}` reached JSX as a React child.
- Expected modifications: normalize API failures at the frontend boundary, add focused regression coverage where practical, run the frontend production build, and update project records.

## 2026-07-23 — Chat error-rendering fix completed

- Added a reusable API-error formatter that extracts string details, structured `detail.message`, native error messages, or a safe fallback.
- Updated `useChat` so both toast and chat state receive a string instead of the backend error object.
- Added a defensive content normalization in `ChatMessage` to prevent malformed or legacy object content from becoming a React child.
- Confirmed the supplied backend log's final failure was an intentional HTTP 429 quota response; earlier Vite proxy resets occurred while the backend was unavailable/restarting.
- Validation completed: structured `{code, message}` conversion check passed, Vite production build passed (2,577 modules), and `git diff --check` passed.

## 2026-07-23 — General-response quality work started

- Reviewed user examples showing unnecessary language-detection/reasoning commentary and forced matchmaking redirects after general questions.
- Confirmed the root cause in `BASE_SYSTEM_PROMPT`: it mandates a parenthesized explanation after every response and examples reinforce the behavior.
- Expected modifications: `backend/app/core/prompts.py`, focused prompt-regression tests, and `.agents` records.
- Risk: a broad persona change could weaken the intended matrimony experience; the correction will be limited to directness, domain relevance, and non-disclosure of internal reasoning.

## 2026-07-23 — General-response quality completed

- Removed the instruction and examples that exposed parenthesized internal reasoning.
- Kept the warm matchmaker persona for matrimony requests while allowing direct answers to harmless general questions.
- Added explicit behavior for unclear/random input: request one concise clarification without guessing.
- Added direct programming and unclear-input examples to the general system prompt.
- Added three regression tests covering internal-reasoning suppression, direct off-topic assistance, and concise clarification.
- Validation completed: all 29 backend tests passed.

## 2026-07-23 02:00 +05:30 — Work started

- Read the user-supplied mandatory documentation workflow.
- Confirmed that `.agents/` existed but contained no files.
- Initialized permanent project context, architecture, decisions, issues, task tracking, and module context before application code changes.
- Started the dynamic provider/model, subscription, quota, payment, and administration implementation.
- Expected modifications: relevant backend AI/model/schema/service/API/database files; frontend router/services/hooks/pages/admin components; tests; `.agents` records.
- Primary risks: schema migration safety, incomplete historical token accounting, concurrent credit spending, provider capability differences, secret handling, and unavailable live payment credentials.

## 2026-07-26 15:30 +05:30 — Phase 3: Embedding + Qdrant vector search implemented

- Installed dependencies: qdrant-client, sentence-transformers, torch (torch 2.13.0+cpu, works with Python 3.14.6).
- Created `embedding_service.py`: BAAI/bge-m3 local embedding model (1024-d, lazy-loaded singleton). Supports `embed_text()`, `embed_batch()`, `build_profile_document()`.
- Created `vector_service.py`: Qdrant client wrapper with metadata filtering (Gender, Caste, City, Religion, Maritalstatus, Age). Auto-creates collection on first use. Cosine distance, score threshold >= 0.5.
- Created `indexing_service.py`: Full re-index pipeline — fetches all active profiles from MySQL, builds documents, generates embeddings in batches of 100, upserts to Qdrant.
- Updated `config.py`: Added QDRANT_HOST, QDRANT_PORT, EMBEDDING_MODEL, EMBEDDING_BATCH_SIZE.
- Updated `db_query_service.py`: `answer_database_question_hybrid()` now falls back to Qdrant vector search when MySQL returns 0 results. Extracted `_add_photo_url()` as reusable helper.
- All 29 tests pass. No regressions.

## 2026-07-26 15:00 +05:30 — Phase 2: Structured extraction + query builder implemented

- Added `STRUCTURED_EXTRACTION_PROMPT` to `prompts.py`: LLM outputs only JSON filters, never SQL.
- Created `extraction_service.py`: Calls LLM with extraction prompt, parses JSON, validates filters, includes keyword fallback.
- Created `query_builder.py`: Python parameterized SQL builder from structured filters. No LLM involvement.
- Updated `db_query_service.py`: Added `answer_database_question_hybrid()` — uses extraction + query builder instead of LLM SQL generation. Returns "No matching profiles found." for empty results instead of calling LLM.
- Updated `chat_service.py`: Routes to `answer_database_question_hybrid` when `CHAT_ENGINE == "hybrid_rag"`. Falls back to legacy intent+SQL path when `CHAT_ENGINE == "legacy"`.
- Default `CHAT_ENGINE` is `"hybrid_rag"` — new pipeline active by default.
- Pending: Run tests to verify no regressions.

## 2026-07-26 14:45 +05:30 — Phase 1: Hallucination fixes implemented

- Executed Phase 1 changes:
  - **Change A** — Fixed `BASE_SYSTEM_PROMPT` contradictions (lines 19-22): Removed "NEVER say you don't have access" directive. Replaced with "If no matching profiles found, honestly say 'No matching profiles found'."
  - **Change B** — Fixed `FORMAT_SYSTEM_PROMPT` example names (lines 72-73): Replaced "Sneha Patil" and "Priya Sharma" with obfuscated placeholders.
  - **Change C** — Added `_is_profile_query()` safety gate in `chat_service.py`: Before calling `get_general_response()`, checks if message contains profile-related keywords. If yes, returns "No matching profiles found" without calling any LLM.
  - **Change D** — Added `CHAT_ENGINE` feature flag to `config.py` (default: "hybrid_rag", can be "legacy").
- File changes: `prompts.py`, `chat_service.py`, `config.py`.
- No dependencies added. No new packages required.
- Pending: Run tests to verify no regressions.

## 2026-07-26 14:30 +05:30 — Hybrid RAG pipeline discovery and planning

- User reported that the chatbot is hallucinating fake matrimonial profiles (names, ages, photos, locations) in response to profile queries.
- Traced the root cause to three compounding issues:
  1. Contradictory `BASE_SYSTEM_PROMPT` directives forcing fabrication (lines 19-22).
  2. Intent classifier (llama-3.1-8b, 10 tokens) misclassifying Marathi/mixed-language subcaste queries.
  3. `FORMAT_SYSTEM_PROMPT` example names leaking into LLM output.
- Proposed a full Hybrid RAG pipeline replacement: Structured Extraction → Python Query Builder → MySQL + Qdrant fallback.
- User approved the approach and provided detailed requirements:
  - Local embedding model: BAAI/bge-m3 (multilingual, offline, no API cost).
  - Vector DB: Qdrant on a separate VPS (not Docker on main VPS).
  - Feature flag: CHAT_ENGINE = legacy|hybrid_rag for gradual migration.
  - No hardcoded examples — all generated dynamically from real database values.
  - Phase 1 priority: Stop hallucinations immediately (prompt fix + safety gate).
- Explored the laptop environment and VPS constraints:
  - Laptop: 16GB RAM, 474GB disk (283GB free), Python 3.14.x, no GPU.
  - VPS: Hostinger KVM 1 (1 vCPU, 1GB RAM, ~25GB SSD).
  - bge-m3 requires ~4-6GB RAM for CPU inference — may need KVM upgrade.
  - Qdrant requires ~200MB-500MB RAM — fits on separate KVM 1.
- Updated all `.agents/` documentation with the new architecture plan.

## 2026-07-23 02:20 +05:30 — Commercial AI module completed

- Added dynamic AI provider/model registry, task routes, ordered fallback, context checks, direct health tests, and normalized response/usage handling.
- Re-routed intent, general chat, SQL generation, database formatting, and notices through task keys while preserving legacy call compatibility for existing tests.
- Added versioned subscription plans, subscriptions, atomic/idempotent credit reservation, daily limits, usage ledger, cost estimation, payment orders, gateway configuration references, and audit records.
- Seeded Free, Basic, Silver, Groq models/routes, and the manual payment adapter safely and idempotently at startup.
- Added customer plans/subscription UI and sidebar credit display.
- Added a consolidated admin console for commercial summary, plan publication, provider/model configuration, routing/testing, subscription assignment/adjustment/cancellation, payments, gateway references, usage, and audits.
- Added six commercial quota/cost/chat integration tests; total suite now has 26 passing tests.
- Validation completed: Python compile, 26 backend tests, frontend production build, FastAPI startup/public plan smoke test, route registration inspection, and `git diff --check`.
- External limitation: live gateway payment and live AI-provider acceptance tests require deployment credentials and remain explicitly tracked.
