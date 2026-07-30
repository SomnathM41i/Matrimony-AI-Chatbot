# Project Context

## Purpose

`myvivahai` is an AI matrimony chatbot. Authenticated users can converse with an assistant, search an external matrimonial MySQL database, inspect profiles and plans, and retain conversation history. Administrators can monitor users, profiles, conversations, and platform statistics.

## Technology Stack

- Backend: Python, FastAPI, SQLAlchemy async ORM, Pydantic, HTTPX, SlowAPI.
- Local application database: SQLite via `DATABASE_URL`; stores chatbot users, conversations, and messages.
- Business/profile database: external MySQL; queried through `mysql.connector` using a strict read-only SQL validation layer.
- AI: currently Groq's OpenAI-compatible chat-completions endpoint.
- Frontend: React, Vite, React Router, TanStack Query, Zustand, Tailwind CSS, Framer Motion.
- Authentication: JWT access and refresh tokens stored in HTTP-only cookies.

## Business Requirements

- Preserve existing chat, history, authentication, database search, and admin workflows.
- Add versioned Free, Basic, and Silver subscription plans with dynamic prices, validity, contacts, AI credits, and daily limits.
- Initial intended catalogue: Free (50 credits/month, 10/day), Basic (INR 2,499/30 days, 500 credits, 200/day, 30 contacts), Silver (INR 4,999/60 days, 1,500 credits, 200/day, 60 contacts).
- Default charging: one credit for normal chat and two credits for database/profile requests; failed AI responses must not consume credits.
- Allow 2-3 hour paid-user sessions while applying fair-use and credit controls.
- Make AI providers, models, prices, task routes, and fallbacks dynamic and manageable through the admin panel.
- AI service changes must not affect subscription/payment business logic.
- Payment integration must use server-authoritative prices, signature/webhook verification, idempotency, and a provider abstraction.

## Important Workflows

- Chat: `/api/chat` authenticates, validates a message, calls `ChatService`, stores user/assistant messages, commits, and returns usage.
- **Current (Hybrid RAG) database path**: `extraction_service.py` extracts structured JSON filters (no SQL) → `query_builder.py` builds parameterized SQL → MySQL exact search → Qdrant vector search fallback on zero results → grounded generation.
- **Legacy database path** (CHAT_ENGINE=legacy): intent classifier decides general vs database → LLM generates SQL → `validate_select_sql` checks it → executes against MySQL → LLM formats results.
- Authentication: login/register set access and refresh cookies; `/api/auth/refresh` rotates both tokens.
- Frontend protected routes live under `/app`; admin routes live under `/admin`.
- Greeting shortcut: simple greetings ("hi", "hello", "namaste") are handled without any LLM call.

## Database Context

- SQLite application tables: `users`, `conversations`, `chat_messages`.
- MySQL business tables include `register`, `membershipplan`, `siteconfig`, content/success tables, and agent-related tables.
- Financial, subscription, payment, provider-secret, and internal usage tables must never be exposed through `ALLOWED_SQL_TABLES`.
- Production subscription and payment mutations must be transactional and concurrency-safe.

## Existing Conventions and Important Files

### Hybrid RAG Module (2026-07-26)

- `backend/app/services/extraction_service.py` — Structured extraction: LLM outputs only JSON filters, never SQL.
- `backend/app/services/query_builder.py` — Python query builder: builds parameterized SQL from structured filters.
- `backend/app/services/embedding_service.py` — Local multilingual embeddings via BAAI/bge-m3 (1024d, 100+ languages).
- `backend/app/services/vector_service.py` — Qdrant client wrapper: metadata filtering + vector search.
- `backend/app/services/indexing_service.py` — Automatic profile re-indexing on schema change.
- `backend/app/services/schema_discovery.py` — Auto-discovers tables, columns, distinct values from MySQL.
- `backend/app/services/example_generator.py` — Generates multilingual example queries from real data.
- `backend/app/core/prompts.py` — Contains all system prompts: `BASE_SYSTEM_PROMPT`, `FORMAT_SYSTEM_PROMPT`, `INTENT_SYSTEM_PROMPT`, `SQL_GENERATION_SYSTEM_TEMPLATE`, `DB_SCHEMA_HINT`, `STRUCTURED_EXTRACTION_PROMPT`.
- `backend/app/config.py` — Added: `CHAT_ENGINE` (legacy|hybrid_rag), embedding model config, Qdrant URL.
- `backend/app/services/db_query_service.py` — Added anti-hallucination pre-formatting guard blocks LLM formatting for unavailable personal attributes (favorite food, appetite, etc.).
- `backend/app/services/chat_service.py` — Added greeting shortcut (handles hello/hi/namaste without LLM call).

### Current Module Layout

| Layer | Key Files |
|---|---|
| AI/LLM | `backend/app/ai/gateway.py`, `backend/app/ai/llm_client.py` |
| Extraction | `backend/app/services/extraction_service.py` |
| Query Building | `backend/app/services/query_builder.py` |
| DB Query | `backend/app/services/db_query_service.py` |
| LLM Formatting | `backend/app/services/llm_service.py` |
| Chat | `backend/app/services/chat_service.py` |
| Embedding | `backend/app/services/embedding_service.py` |
| Vector Search | `backend/app/services/vector_service.py` |
| Indexing | `backend/app/services/indexing_service.py` |
| Schema Discovery | `backend/app/services/schema_discovery.py` |
| Example Gen | `backend/app/services/example_generator.py` |
| Prompts | `backend/app/core/prompts.py` |

## Session Variables

- HTTP-only cookies: `access_token`, `refresh_token`.
- Zustand authentication state: `token` boolean and `user` object.
- Legacy browser usage key: `token_usage`; informational only and never authoritative for billing.

## Routes and Redirects

- `/chat` and `/chat/:conversationId` redirect to `/app/chat...`.
- `/history` redirects to `/app/history`.
- `/register` currently redirects to `/login` even though a registration API exists.
- Protected user routes use `/app/*`; administrators use `/admin/*`.

## Restrictions and Non-negotiable Rules

- Preserve existing APIs and flows where practical; additions should be backward-compatible.
- Do not trust plan prices, credit balances, provider costs, or payment status supplied by the browser.
- Do not expose provider/payment secrets in API responses or logs.
- Do not charge credits for failed AI operations.
- All administrative mutations require the existing admin authorization guard plus server-side role checks.
- Store money as integer minor units (paise or provider currency minor units), never floating point.
- Keep provider token cost separate from user-facing credits.
- Use versioned plan/model-rate records so history remains reproducible.

## Previously Completed Work

- Existing authenticated chatbot, history, MySQL query assistant, Groq integration, token fields, and admin monitoring were present before `.agents` documentation was initialized.
- On 2026-07-23 the commercial AI module was added: versioned plans, subscriptions, atomic credit reservations, daily limits, normalized per-call usage/cost events, dynamic AI providers/models/task routing/fallbacks, manual payment orders, provider-neutral payment contract, customer plans UI, and the Commerce & AI admin console.
- On 2026-07-26 Hybrid RAG pipeline implemented: structured extraction + Python query builder + Qdrant vector search fallback.
- On 2026-07-27 anti-hallucination hardening: pre-formatting guard for unavailable personal attributes, strengthened FORMAT_SYSTEM_PROMPT and BASE_SYSTEM_PROMPT.
- On 2026-07-27 timeout fixes: frontend API timeout increased 30s→120s, greeting shortcut added.
- On 2026-07-27 legacy modules removed: `intent_llm.py`, `intent_detector.py` deleted entirely. `sql_generator.py` — only `generate_sql` deleted; `validate_select_sql` preserved in `db_query_service.py`.
- All project caches cleaned: `__pycache__`, `.pytest_cache`, `frontend/dist`, `node_modules/.vite` removed.
- Application startup now seeds Groq provider/models, five task routes, the Free/Basic/Silver catalogue, and a manual verification gateway only when those records do not already exist.
- Current paid checkout state is manual administrator verification; no external gateway adapter is installed.

## Commercial Routes

- Customer: `/api/commercial/plans`, `/me`, `/usage`, `/orders`.
- Administration: `/api/admin/commercial/*` for plans, providers, models, routes, subscriptions, orders, gateways, usage, summary, and audit.
- Frontend: `/app/plans` and `/admin/commercial-ai`.
