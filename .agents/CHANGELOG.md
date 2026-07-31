# Changelog

## 2026-07-31 — Performance & Stability Fixes (no feature changes)

Analysis: `.agents/PERFORMANCE_ANALYSIS.md`. No prompts, schema, API contracts,
search behaviour or UI behaviour were changed.

### Fixed
- **WatchFiles restart loop** — added `backend/run_dev.py` with `reload_dirs=["app"]`,
  so the watcher never walks `venv/`, `site-packages/`, model caches or `.git`.
  Loading the embedding model no longer restarts the server mid-request.
  README start command updated.
- **`NameError: name 'db' is not defined`** — `chat_service.py` line 380 used a bare
  `db` inside `ChatService` (session is `self.db`), and passed 5 positional args to the
  4-parameter `format_db_notice()`. Replaced with `_format_notice_safe(...)`, which
  already has that exact signature. Reproduced the reported log before the fix and
  confirmed it is gone after.
- **Misleading fallback log** — the enclosing `except` reported "Vector search fallback
  failed" for errors after a *successful* vector search. Now `logger.exception` so the
  real cause and traceback are recorded (`chat_service.py`, `db_query_service.py`).
- **Embedding model loaded more than once** — `get_embedding_model()` had no lock, so
  concurrent misses each built a ~2.2 GB model. Added double-checked locking and keyed
  `DEFAULT_MODEL` off `settings.EMBEDDING_MODEL` so callers passing the setting and
  callers using the default share one instance instead of evicting each other.
- **Event loop blocked by Qdrant** — `search_with_filters()` is synchronous with a 120 s
  timeout and was awaited directly from async handlers. Now called via `asyncio.to_thread`
  at both call sites. Measured: 3 → 52 heartbeat ticks during a 0.5 s Qdrant call.

### Optimized
- Embedding model warmed once at startup in a background thread (`main.py`), moving the
  cold-load cost out of the first user request without delaying startup or `/health`.
- `build_schema_context()` memoized; invalidated by `refresh_cache()`. Output verified
  byte-identical. Was re-rendered on every LLM call at 5 call sites.
- `_load_history()` stops scanning once all four metadata keys are resolved instead of
  JSON-parsing every message in the conversation. Result verified identical.
- Removed a redundant `get_client()` warm-up call before `search_with_filters()`, which
  already resolves the client itself.

### Diagnostics
- `logger.propagate = False` — every log line was previously emitted twice under uvicorn.
- `StepTimer` accepts a `request_id` and refuses to log twice; timings are now emitted on
  the error path as well as on success.
- `process_message()` (non-streaming) had no instrumentation at all; now timed.
- LLM latency and prompt size logged per call in `gateway.py`; intent-resolution path and
  duration logged in `extraction_service.py`.

### Files Modified
- `backend/run_dev.py` (new), `backend/tests/test_performance_fixes.py` (new, 10 tests),
  `.agents/PERFORMANCE_ANALYSIS.md` (new)
- `backend/app/services/chat_service.py`, `backend/app/services/db_query_service.py`,
  `backend/app/services/embedding_service.py`, `backend/app/services/schema_discovery.py`,
  `backend/app/services/extraction_service.py`, `backend/app/ai/gateway.py`,
  `backend/app/core/logger.py`, `backend/app/main.py`, `README.md`

### Verification
174 tests pass (164 pre-existing + 10 new). Each new test was confirmed to fail when its
fix is reverted. `pyflakes` reports no undefined names.

### Known, deliberately not changed
- `build_profile_query()` wraps every predicate in `LOWER(col) = LOWER(%s)`, which is
  non-sargable and prevents index use on `register`. Fixing it requires functional indexes
  or a collation change — a schema/DDL change, out of scope.
- Intent extraction routes to `sql_generation` (70B model) and sends untruncated history;
  `INTENT_MODEL` is configured but unused on this path. Both are routing/behaviour
  decisions, left untouched.

## 2026-07-29 — Bug Fix Phases 1-3 (Security, Correctness, Robustness)

### Phase 1 — Security & Critical Bugs
- Added `import json` to `llm_client.py` — fixed `stream_groq()` NameError crash.
- Replaced Python `hash()` with `hashlib.md5()` in `vector_service.py` — deterministic Qdrant point IDs across restarts.
- Fixed `auth_service.py` token invalidation on failed refresh — removed spurious `token_version` increment.
- Fixed `refresh_token` race condition — added atomic conditional `UPDATE` with `increment_token_version()` in `user_repository.py`.
- Confirmed `.env` already gitignored and not tracked.

### Phase 2 — Code Correctness
- Fixed Marathi city regex in `extraction_service.py` — prepositions come AFTER place names in Marathi; split into English and Marathi patterns.
- Fixed `embedding_service.py` event loop blocking — wrapped `SentenceTransformer.encode()` in `asyncio.to_thread()`.
- Fixed destructive seed in `commercial_service.py` — skip `AITaskTarget` deletion; create only missing targets.
- Fixed circular imports — extracted `limiter` to `app/core/limiter.py`.
- Fixed broken test import in `test_chat_error_messages.py`.
- Fixed timezone-naive datetime in `auth.py`.

### Phase 3 — Robustness & Concurrency
- Added `threading.Lock()` with double-checked locking for thread-safe MySQL pool init.
- Fixed `get_client()` singleton — now recreates client when host/port changes.
- Fixed `_load_history()` early break — now scans all messages for metadata.
- Replaced hardcoded `VECTOR_SIZE=1024` with dynamic `_get_vector_size()` from model config.
- Added `\bwith\b` to subquery regex to block CTE bypass.
- Replaced bare `except: pass` with `logger.debug()` for ALTER TABLE failures.

### Files Modified
- `backend/app/ai/llm_client.py`, `backend/app/services/vector_service.py`, `backend/app/services/auth_service.py`, `backend/app/repositories/user_repository.py`, `backend/app/services/extraction_service.py`, `backend/app/services/embedding_service.py`, `backend/app/services/chat_service.py`, `backend/app/services/db_query_service.py`, `backend/app/services/commercial_service.py`, `backend/app/services/indexing_service.py`, `backend/app/core/auth.py`, `backend/app/core/limiter.py` (new), `backend/app/main.py`, `backend/app/api/auth_routes.py`, `backend/app/api/chat_routes.py`, `backend/app/database.py`, `backend/tests/test_extraction_service.py`, `backend/tests/test_embedding_service.py`, `backend/tests/test_chat_error_messages.py`, `backend/tests/test_vector_service.py`, `.agents/TODO.md`, `.agents/CHANGELOG.md`

### Validation
- All modified Python files compile successfully.

## 2026-07-27 — Anti-Hallucination Hardening & Timeout Fixes

### Anti-Hallucination Hardening
- Added pre-formatting guard in `db_query_service.py` — blocks LLM formatting for questions about unavailable personal attributes (favorite food, appetite, eating habits, etc.).
- Strengthened `FORMAT_SYSTEM_PROMPT` with explicit anti-hallucination rules and examples of forbidden fabrications.
- Strengthened `BASE_SYSTEM_PROMPT` with "not available in the database" instruction.

### Timeout Fixes
- Increased frontend API timeout from 30s to 120s (`apiClient.js`).
- Added greeting shortcut in `chat_service.py` — handles "hello"/"hi"/"namaste" etc. without calling any LLM.

### Code Cleanup
- Removed stale `myvivahai.md` session log from project root.
- Removed all `__pycache__` directories, `.pytest_cache`, `frontend/dist`, `frontend/node_modules/.vite`.

### Files Changed
- `backend/app/services/db_query_service.py`, `backend/app/services/chat_service.py`, `backend/app/core/prompts.py`, `frontend/src/services/apiClient.js`
- Tests updated accordingly.

### Validation
- All 29 backend tests passing.

## 2026-07-26 — Hybrid RAG Pipeline (Phases 1-5)

### Phase 1 — Hallucination Fixes (Critical)
- Removed contradictory "NEVER say you don't have access" directive from `BASE_SYSTEM_PROMPT`.
- Replaced "Sneha Patil" / "Priya Sharma" example names with obfuscated placeholders.
- Added `_is_profile_query()` safety gate in `chat_service.py` — profile-keyword queries in general path return "No matching profiles found" without LLM call.
- Added `CHAT_ENGINE` feature flag (`hybrid_rag` / `legacy`) to `config.py`.

### Phase 2 — Structured Extraction + Query Builder
- Added `STRUCTURED_EXTRACTION_PROMPT` to `prompts.py` — LLM outputs only JSON filters, never SQL.
- Created `extraction_service.py` — calls LLM with extraction prompt, parses JSON, validates filters, includes keyword fallback.
- Created `query_builder.py` — Python parameterized SQL builder from structured filters. No LLM involvement.
- Updated `db_query_service.py` — added `answer_database_question_hybrid()` using extraction + query builder.

### Phase 3 — Embedding + Vector Search
- Installed dependencies: `qdrant-client`, `sentence-transformers`, `torch`.
- Created `embedding_service.py` — BAAI/bge-m3 local embedding model (1024-d, lazy-loaded singleton).
- Created `vector_service.py` — Qdrant client wrapper with metadata filtering (Gender, Caste, City, Religion, Maritalstatus, Age).
- Created `indexing_service.py` — Full re-index pipeline with batch upserts of 100.

### Phase 4 — Schema Discovery + Dynamic Examples + Auto-Index
- Created `schema_discovery.py` — auto-discovers tables, columns, distinct values from MySQL.
- Created `example_generator.py` — generates multilingual example queries from real data.
- Auto-reindex on startup in `main.py` lifespan.
- Added `docs/qdrant-setup.md`.

### Phase 5 — Integration + Conversation Memory
- `answer_database_question_hybrid()` with MySQL → Qdrant vector search fallback.
- Conversation memory: filter accumulation + detail context across turns.
- `profile_detail` intent for family/education/horoscope/income etc.
- Multilingual responses via `format_db_notice()`.
- Legacy modules (`intent_llm.py`, `intent_detector.py`) removed; `sql_generator.py` partially removed (only `generate_sql` deleted; `validate_select_sql` kept in `db_query_service.py`).

### Files Created
- `backend/app/services/extraction_service.py`, `query_builder.py`, `embedding_service.py`, `vector_service.py`, `indexing_service.py`, `schema_discovery.py`, `example_generator.py`
- `backend/docs/qdrant-setup.md`

### Files Modified
- `backend/app/core/prompts.py`, `backend/app/services/db_query_service.py`, `backend/app/services/chat_service.py`, `backend/app/config.py`, `backend/requirements.txt`

### Validation
- 29/29 backend tests passing.

## 2026-07-23 02:20 — Dynamic Commercial AI Module

### Request
Implement versioned plans and subscriptions with dynamic admin management, provider/model-independent AI routing, usage/cost controls, and a design that continues to work when the AI model or service changes.

### Before
The chatbot called Groq directly through hard-coded settings. It had no commercial plans tied to chatbot users, no quotas, no payment/order lifecycle, no full intent-token accounting, no provider routing, and no commercial admin interface.

### Changes Made
- Added versioned Free, Basic, and Silver plans with credits, daily limits, duration, contacts, and configurable request weights.
- Added active subscriptions, atomic reservations, idempotent finalization, automatic Free entitlements, and failure refunds.
- Added normalized per-call token/cost events including intent detection.
- Added dynamic AI providers, models, capabilities, prices, task routes, health tests, context validation, and transient fallback.
- Added payment orders, gateway secret references, provider-neutral adapter contract, and audited manual payment confirmation.
- Added commercial and AI administration for plans, providers, models, routing, subscriptions, payments, usage, and audit history.
- Added customer plan cards, order creation, current-plan balance, and sidebar credit status.
- Added startup schema compatibility and idempotent seed records.

### Files Modified
- `backend/app/ai/gateway.py`, `intent_llm.py`, `sql_generator.py`
- `backend/app/models/commercial_model.py`, `models/__init__.py`
- `backend/app/services/commercial_service.py`, `payment_gateway.py`, `chat_service.py`, `db_query_service.py`, `llm_service.py`
- `backend/app/api/commercial_routes.py`, `commercial_admin_routes.py`, `chat_routes.py`, `admin_routes.py`
- `backend/app/schemas/commercial_schema.py`, `chat_schema.py`
- `backend/app/database.py`, `main.py`
- `backend/tests/test_commercial_service.py`
- `frontend/src/pages/Plans.jsx`, `pages/admin/CommercialAI.jsx`
- `frontend/src/services/commercialService.js`, `adminService.js`
- `frontend/src/app/router.jsx`, `components/ui/Sidebar.jsx`, `layouts/AdminLayout.jsx`, `hooks/useChat.js`
- `.agents/*`

### After
Commercial rules are server-authoritative and independent of AI vendors. Administrators can publish plans and AI routing without code edits; chats reserve and charge credits safely; actual usage/cost is auditable; customer balances and plans are visible. Payments operate through safe pending orders and manual verification until a live adapter is selected.

### Validation
- Python syntax compiled.
- 26 backend unit/integration tests passed.
- Frontend Vite production build passed.
- FastAPI startup/schema/seed and public plan endpoint smoke test passed.
- All expected commercial routes registered.
- `git diff --check` passed.

### Remaining Issues
- Install and sandbox-test a selected live payment adapter before online checkout.
- Run admin model/route health tests with deployed provider secrets and staging MySQL before production rollout.

## 2026-07-23 — General response quality

### Before
General chat appended parenthesized explanations of its reasoning and redirected unrelated questions toward matchmaking.

### After
General chat answers clear harmless questions directly, preserves matchmaking behavior for domain requests, and asks one concise clarification for unclear input without exposing internal processing.

### Files Changed
- `backend/app/core/prompts.py`
- `backend/tests/test_chat_error_messages.py`
- `.agents/TODO.md`
- `.agents/ISSUES.md`
- `.agents/WORK_LOG.md`
- `.agents/CHANGELOG.md`
- `.agents/DECISIONS.md`

### Validation
- 29 backend tests passed.

## 2026-07-23 — Safe chat error rendering

### Before
A structured backend quota error such as `{code, message}` was passed directly to React and react-hot-toast, crashing the chat route with “Objects are not valid as a React child.”

### After
Chat API errors are normalized to a human-readable string before entering UI state. The chat message renderer also tolerates unexpected object content without crashing. Quota enforcement and structured backend error codes are unchanged.

### Files Changed
- `frontend/src/utils/apiError.js`
- `frontend/src/hooks/useChat.js`
- `frontend/src/components/ui/ChatMessage.jsx`
- `.agents/TODO.md`
- `.agents/ISSUES.md`
- `.agents/WORK_LOG.md`
- `.agents/CHANGELOG.md`

### Validation
- Structured error normalization check passed.
- Frontend Vite production build passed with 2,577 modules transformed.
- `git diff --check` passed.
