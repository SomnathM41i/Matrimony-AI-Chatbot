# Tasks

## Completed Work

### Hybrid RAG Pipeline

#### Phase 1 — Hallucination Fixes
- [x] Fix contradictory directives in BASE_SYSTEM_PROMPT
- [x] Add safety gate in chat_service.py
- [x] Replace example names with placeholders

#### Phase 2 — Structured Extraction + Query Builder
- [x] STRUCTURED_EXTRACTION_PROMPT in prompts.py
- [x] extraction_service.py (search + detail intents)
- [x] query_builder.py (search + detail queries, all register columns)

#### Phase 3 — Embedding + Vector Search
- [x] Install qdrant-client, sentence-transformers, torch
- [x] embedding_service.py (BAAI/bge-m3)
- [x] vector_service.py (Qdrant client, metadata filters)
- [x] indexing_service.py (batch reindex)
- [x] Qdrant deployed on VPS

#### Phase 4 — Schema Discovery + Auto-Index
- [x] schema_discovery.py (auto-discover tables/columns/values)
- [x] example_generator.py (dynamic multilingual examples from real data)
- [x] Auto-reindex on startup in main.py lifespan
- [x] docs/qdrant-setup.md

#### Phase 5 — Integration + Conversation Memory
- [x] answer_database_question_hybrid() with MySQL → Qdrant fallback
- [x] CHAT_ENGINE feature flag (hybrid_rag / legacy)
- [x] Conversation memory: filter accumulation + detail context across turns
- [x] profile_detail intent for family/education/horoscope/income etc.
- [x] Multilingual responses for all error/notice messages via format_db_notice()
- [x] Remove legacy modules (intent_llm.py, intent_detector.py, sql_generator.py)

### Anti-Hallucination Hardening (2026-07-27)
- [x] Add pre-formatting guard in db_query_service.py
- [x] Strengthen FORMAT_SYSTEM_PROMPT
- [x] Strengthen BASE_SYSTEM_PROMPT

### Timeout Fixes (2026-07-27)
- [x] Increase frontend API timeout from 30s to 120s (apiClient.js)
- [x] Add greeting shortcut in chat_service.py

### Code Cleanup
- [x] Remove stale myvivahai.md session log from project root
- [x] Remove all __pycache__ directories from app code
- [x] Remove .pytest_cache, frontend/dist, frontend/node_modules/.vite

---

## Bug Fix Phases

### Phase 1 — Security & Critical Bugs (P0) ✅
- [x] `.env` already in `.gitignore`, not tracked by git — confirm no action needed
- [x] **Fix `stream_groq()` crash** — added `import json` in `backend/app/ai/llm_client.py`
- [x] **Fix `hash_id()` non-determinism** — replaced Python `hash()` with `hashlib.md5()` in `backend/app/services/vector_service.py`
- [x] **Fix token invalidation on failed refresh** — removed spurious `token_version` increment before error raise in `backend/app/services/auth_service.py`
- [x] **Fix race condition in `refresh_token`** — added atomic `increment_token_version()` method using conditional `UPDATE ... WHERE token_version = :current` in `backend/app/repositories/user_repository.py`
- [x] **Remove live IP from TODO.md** — replaced with generic text

> **⚠ Note:** Live credentials (Groq API key, MySQL password, Qdrant IP) in `backend/.env` are NOT git-tracked, but you should **rotate them** since the `.env` file exists on disk with live secrets. Generate new credentials and update the file.

### Phase 2 — Code Correctness Bugs (P1) ✅
- [x] **Fix Marathi city regex** — split into English (preposition before city) and Marathi (preposition after city) patterns in `backend/app/services/extraction_service.py`
- [x] **Fix test that documents the bug** — updated assertion to expect `"पुणे"` instead of `"मुलगी"` in `backend/tests/test_extraction_service.py`
- [x] **Fix event loop blocking** — wrapped `SentenceTransformer.encode()` in `asyncio.to_thread()` in `backend/app/services/embedding_service.py`; updated all callers to `await`
- [x] **Fix destructive seed on startup** — skip deletion of `AITaskTarget` rows; create only missing targets idempotently in `backend/app/services/commercial_service.py`
- [x] **Fix circular imports** — extracted `limiter` to new `backend/app/core/limiter.py`; updated `main.py`, `auth_routes.py`, and `chat_routes.py` to import from there
- [x] **Fix broken test import** — changed `backend.app.core.old_prompts` → `app.core.old_prompts` in `backend/tests/test_chat_error_messages.py`
- [x] **Fix timezone-naive datetime** — removed `.replace(tzinfo=None)` in `backend/app/core/auth.py`

### Phase 3 — Robustness & Concurrency (P2) ✅
- [x] **Fix thread-unsafe pool init** — added `threading.Lock()` with double-checked locking around `_pool` in `backend/app/services/db_query_service.py`
- [x] **Fix `get_client()` singleton ignoring args** — added `_client_config` tracking dict to recreate client when host/port changes in `backend/app/services/vector_service.py`
- [x] **Fix metadata loop break condition** — removed early `break` to scan all messages for metadata in `backend/app/services/chat_service.py`
- [x] **Fix hardcoded `VECTOR_SIZE`** — replaced constant with `_get_vector_size()` function that derives from model config; removed stale imports in `indexing_service.py` and tests
- [x] **Fix SQLite ALTER TABLE silent failure** — changed bare `except: pass` to `except Exception as e: logger.debug(...)` in `backend/app/database.py`
- [x] **Fix `validate_select_sql` CTE bypass** — added `(?:with|select)` to subquery regex pattern in `backend/app/services/db_query_service.py`

### Phase 4 — Documentation & Cleanup (P3) ✅
- [x] **Fix test count discrepancy** — Added CHANGELOG entries clarifying: 26 = commercial module tests, 29 = core unit tests, 134 = all tests including end-to-end. Consolidated references to 29 as the canonical unit-test count.
- [x] **Add missing CHANGELOG entries** — Added entries for Hybrid RAG Pipeline (2026-07-26), Anti-Hallucination Hardening & Timeout Fixes (2026-07-27), and Bug Fix Phases 1-3 (2026-07-29).
- [x] **Resolve `sql_generator.py` deletion contradiction** — Clarified across all docs: only `generate_sql` was deleted; `validate_select_sql` was preserved in `db_query_service.py`.
- [x] **Resolve Python 3.14 compatibility status** — Updated ISSUES.md to mark Resolved with confirmation from Phase 3.
- [x] **Fix ARCHITECTURE.md VPS RAM conflict** — Added warning note that bge-m3 requires 4-6GB RAM but main app VPS is only 1GB.
- [x] **Consolidate duplicate ARCHITECTURE.md sections** — Merged "Current Architecture", "Target Architecture (Hybrid RAG)", and "Target Hybrid RAG Architecture" into one section with Query Flow and Subscription/Quota Flow subsections.
- [x] **Update PROJECT_CONTEXT.md workflows** — Updated Important Workflows with Hybrid RAG path, legacy path note, and greeting shortcut.

### Phase 5 — Testing & Verification ✅
- [x] **Add unit tests for anti-hallucination guard** — 14 test cases covering food, diet, family, Marathi queries (blocked) vs age, city, occupation, general queries (allowed) in `test_chat_error_messages.py::AntiHallucinationGuardTests`
- [x] **Add unit tests for greeting shortcut** — 14 test cases covering English/Marathi greetings, punctuation tolerance, case insensitivity, whitespace, and non-greeting rejection in `test_chat_error_messages.py::GreetingShortcutTests`
- [ ] End-to-end tests (manual — require live MySQL + Qdrant):
  - [ ] "96 kuli maratha kolhapur engineer mulgi" → MySQL results
  - [ ] "modern but traditional girl" → Qdrant vector fallback
  - [ ] "mala pune til mulgi dakhav" → Marathi profiles
  - [ ] "tell me about her family" → profile_detail → family fields
  - [ ] "tice shikshan kay aahe" → Marathi detail → education

### Phase 6 — Deployment
- [ ] Run `reindex_profiles.py` one-time to load profiles into Qdrant
- [ ] Restart FastAPI server to pick up latest code
- [ ] Run deployment acceptance tests
- [ ] Install and verify live payment-gateway adapter (blocked — needs business choice)
