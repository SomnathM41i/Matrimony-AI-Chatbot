# Tasks

## Conversation Flow Enhancement — "Consultant" Track (CF-0..CF-7, 2026-08-02)

Detailed plan: `.agents/modules/conversation-consultant-context.md`.

- [x] CF-0 — MyVivahAI identity + Marathi-first: `ASSISTANT_NAME`/`PLATFORM_NAME` config; identity + language clause in all prompts; new `WELCOME_MESSAGE` (exact copy); branded greetings; persona answer; update greeting-copy tests; add persona/language test
- [x] CF-1 — Identity gate: first message of new conversation without MatriID → `WELCOME_MESSAGE` + chips; `MATRI_ID_GATE_MODE` soft/hard; `matri_id_prompted` metadata flag
- [x] CF-2 — Rich profile load + Marathi summary: expand `_fetch_register_row`; `format_user_profile_summary()` (zero-LLM Marathi); show once after link on first-ever conversation
- [x] CF-3 — Missing-only questionnaire + search-early: `build_nodes(..., missing_only=True)`; `is_viable_search()` per `ONBOARDING_SEARCH_STRATEGY`; search early + refinement chips; onboarding only when zero prior conversations
- [x] CF-4 — Conversation memory + welcome-back: persist/restore `last_topic`/`viewed_profiles`/`compared_pairs`/`last_filters`; Marathi "परत स्वागत!" + contextual chips
- [x] CF-5 — Suggestions engine: deterministic `build_suggestions(context)` in `done` events; `SUGGESTION_ROUTES` click handling; chips in `ChatMessage.jsx` + `useChat.js`; dynamic `EmptyState.jsx`
- [x] CF-6 — Chat-embedded rich biodata: sectioned Marathi biodata + follow-up chips; reuse `resolve_contextual_profile`
- [x] CF-7 — Tests + verification: new tests per phase; update `test_matri_auto_link.py` + `test_chat_questionnaire_flow.py`; verify `test_session_unification_e2e.py`; suite green; docs updated

## Completed Work

### CF-0..CF-4 — Consultant track: identity + gate + summary + missing-only/search-early + memory/welcome-back (2026-08-02) ✅
- [x] CF-0: `ASSISTANT_NAME`/`PLATFORM_NAME` in `config.py` + `.env.example`; MyVivahAI + Marathi-first in `BASE_SYSTEM_PROMPT`/`FORMAT`/`INTENT`; `STRUCTURED_EXTRACTION_PROMPT` kept plain + `_EXTRACTION_IDENTITY` prefix at `extraction_service.py` call site; `format_db_notice` + `language_instruction` Marathi-first; `WELCOME_MESSAGE` exact copy; `IDENTITY_RESPONSES` + `_is_identity_question`; streaming greeting shortcut extended; `MyVivahAIIdentityTests` added
- [x] CF-1: `MATRI_ID_GATE_MODE` soft/hard in `config.py` + `.env.example`; `_apply_identity_gate` in `chat_service.py`; `WELCOME_SUGGESTIONS`; `matri_id_prompted` metadata persisted; `_done_event` carries `suggestions`; `test_identity_gate.py` added
- [x] CF-2: `REGISTER_PROFILE_COLUMNS`; `format_user_profile_summary()` zero-LLM Marathi; `fetch_partner_expectations` returns `profile` + `pe_summary_mr`; auto-link reply prepends summary; tests added
- [x] CF-3: `build_nodes(..., missing_only=True)` (chat drops "कायम ठेवा?" confirm nodes); `is_viable_search()` + `ONBOARDING_SEARCH_STRATEGY` (gender_plus_core default); search-early prepends matches once per session (`questionnaire_searched` flag); onboarding auto-start gated on zero prior conversations (`conv_repo.count_by_user`, conversation_id None); tests: `MissingOnlyBuildTests` + `ViableSearchTests` in `test_questionnaire.py`, search-early + zero-prior tests in `test_chat_questionnaire_flow.py`, updated `test_pe_present_flow_starts_at_first_missing_category`
- [x] CF-4: `_enrich_memory()` annotates assistant metadata with `last_topic`/`viewed_profiles`/`compared_pairs`/`last_filters`; `_load_history` restores them + `questionnaire_searched` (fixes search-early repeat across turns); `handle_profile_comparison` returns `compared_pair`; `_welcome_back()` streams Marathi "परत स्वागत!" prefix + topic-aware chips (`WELCOME_BACK_SUGGESTIONS`/`GENERIC_WELCOME_BACK_SUGGESTIONS`) for a linked returning user on a brand-new conversation; main-flow `done` event now carries metadata via `_done_event`; `test_conversation_memory.py` added (16 tests)
- [x] CF-5: `build_suggestions(context)` deterministic Marathi chips (matri link / `questionnaire_done` → `QUESTIONNAIRE_DONE_SUGGESTIONS` / last_topic / generic); `SUGGESTION_ROUTES` exact-phrase routing skips LLM extraction entirely (profile_search resume/new/next, comparison, first-candidate detail; `reset_filters` clears accumulated filters); chips injected into every `done` event; `ChatMessage.jsx` renders `message.suggestions` chips; `useChat.js` captures `doneEvent.suggestions` + history `meta.suggestions`; `EmptyState.jsx` suggestions now dynamic by `needsMatriId`; `test_suggestions.py` added (10 tests)
- [x] CF-6: `BIODATA_SECTIONS` (8 sections) + `_BIODATA_LABELS_MR`/`_BIODATA_EXTRA_LABELS_MR` in `matri_service.py`; zero-LLM `format_profile_section`/`format_profile_biodata` (header + photo + sections, `_clean` skips empty); `BIODATA_SECTION_ROUTES`/`BIODATA_SECTION_CHIPS`; `SUGGESTION_ROUTES` maps every section chip → `profile_detail` + `biodata_section` on the current profile (no LLM); profile_detail branch in `chat_service.py` renders full biodata for `fields=["all"]` and single sections for section chips (replaces the old `_DETAIL_CATEGORY_QUESTION` bounce, constant removed); replies carry `BIODATA_SECTION_CHIPS` suggestions; `test_biodata.py` added (9 tests)
- [x] CF-7: verified `test_matri_auto_link.py` (link reply = profile/PE summary + missing-only onboarding, not `MATRI_ID_SUCCESS`/confirm-node) + `test_chat_questionnaire_flow.py` (missing-only + search-early) + `test_session_unification_e2e.py` (2 tests green); **strengthened `test_suggestions.py::test_first_candidate_detail_route_resolves_from_candidates`** to assert zero-LLM biodata (LLM formatter must raise; reply contains sectioned biodata; done carries `BIODATA_SECTION_CHIPS`) — this **caught a real bug**: route `selected_index: 0` vs 1-based `resolve_contextual_profile` never resolved a profile; fixed to `1`. Full suite 414 passed / 1 known P9; frontend `npm run build` succeeds
- [x] Backend suite 414 passed / 1 known P9 failure; frontend `npm run build` succeeds

## Resume P8-P11 (post-CF-7)

- [x] P8 — More tests: `tests/test_db_query_formatting.py` (15 tests) for `add_photo_url`/`_photo_url`/`format_filter_summary`/`format_no_matches_notice`/`format_profile_results_markdown`
- [x] P9 — Known-failure fix: `test_register_only_fetch` photo URL now derived from `settings.PHOTO_BASE_URL` (`.in` config) instead of hardcoded `.com`; full suite 430 passed / 0 failed
- [ ] P10 — AI evaluation (live eval harness). Offline harness ✅: `tests/eval_harness.py`, 10 scenarios, `python -m tests.eval_harness` → 10/10
- [ ] P11 — KVM2 deploy (acceptance + rollout). Runbook ✅: `.agents/modules/deployment-runbook.md`; live execution needs server access/secrets

### P7 — Backend hardening + frontend a11y/streaming watchdog (2026-08-01) ✅
- [x] Rate limits: profile PATCH 20/m, matri/link 20/m, preference endpoints 20-60/m; conversations GET 60/m, PATCH/DELETE 30/m; admin + commercial-admin 30/m; auth `/refresh` 10/m
- [x] Schema validation: `profile_schema.py` (name ≤100, profile_image URL/data-image prefix, matri_id ≤15 alphanumeric, questionnaire/filter caps); `chat_schema.py` (message ≤ MAX_MESSAGE_LENGTH, title ≤200)
- [x] `RequestLoggingMiddleware` in `main.py` (X-Request-ID, access log, SSE-safe)
- [x] Frontend: 120s streaming watchdog in `useChat.js`; a11y (aria-labels, role=log/alert/status, Login labels/ids/autoComplete, Sidebar aria-expanded)
- [x] Backend suite 351 passed / 1 known P9 failure; `npm run build` succeeds

## Profile & Partner-Preference Module (2026-07-31) — Phases

Detailed plan: `.agents/PHASES.md`.

- [x] Phase 1 — Backend data layer: `User.matri_id/matri_name/matri_synced_at`, `UserPreference` table, migration, `UserResponse` extension, preference repository
- [x] Phase 2 — `matri_service.py`: MatriID link/validate, PE summary, saved-search fallback
- [x] Phase 3 — `core/questionnaire.py` decision tree + start/next/save flow
- [x] Phase 4 — Chat auto-apply: merge saved preferences as default profile-search filters
- [x] Phase 5 — `api/profile_routes.py` (JWT-guarded) registered in `main.py`
- [x] Phase 6 — Frontend `/app/profile` page, `profileService.js`, Sidebar entry, router, useAuth refresh
- [x] Phase 7 — Tests (`test_matri_service.py`, `test_questionnaire.py`), backend suite, frontend build

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
