# Tasks

## Hybrid RAG Pipeline

### Phase 1 — Hallucination Fixes
- [x] Fix contradictory directives in BASE_SYSTEM_PROMPT
- [x] Add safety gate in chat_service.py
- [x] Replace example names with placeholders

### Phase 2 — Structured Extraction + Query Builder
- [x] STRUCTURED_EXTRACTION_PROMPT in prompts.py
- [x] extraction_service.py (search + detail intents)
- [x] query_builder.py (search + detail queries, all register columns)

### Phase 3 — Embedding + Vector Search
- [x] Install qdrant-client, sentence-transformers, torch
- [x] embedding_service.py (BAAI/bge-m3)
- [x] vector_service.py (Qdrant client, metadata filters)
- [x] indexing_service.py (batch reindex)
- [x] Qdrant deployed on VPS (187.127.170.116:6333)

### Phase 4 — Schema Discovery + Auto-Index
- [x] schema_discovery.py (auto-discover tables/columns/values)
- [x] example_generator.py (dynamic multilingual examples from real data)
- [x] Auto-reindex on startup in main.py lifespan
- [x] docs/qdrant-setup.md

### Phase 5 — Integration + Conversation Memory
- [x] answer_database_question_hybrid() with MySQL → Qdrant fallback
- [x] CHAT_ENGINE feature flag (hybrid_rag / legacy)
- [x] Conversation memory: filter accumulation + detail context across turns
- [x] profile_detail intent for family/education/horoscope/income etc.
- [x] Multilingual responses for all error/notice messages via format_db_notice()
- [x] Remove legacy modules (intent_llm.py, intent_detector.py, sql_generator.py) — already deleted

## Anti-Hallucination Hardening (2026-07-27)
- [x] Add pre-formatting guard in db_query_service.py — blocks LLM formatting for questions about unavailable personal attributes (favorite food, appetite, etc.)
- [x] Strengthen FORMAT_SYSTEM_PROMPT — strict anti-hallucination rules with explicit examples of forbidden fabrications
- [x] Strengthen BASE_SYSTEM_PROMPT — added "not available in the database" instruction

## Timeout Fixes (2026-07-27)
- [x] Increase frontend API timeout from 30s to 120s (apiClient.js)
- [x] Add greeting shortcut in chat_service.py — handles "hello"/"hi"/"namaste" etc. without calling any LLM

## Code Cleanup
- [x] Remove stale myvivahai.md session log from project root
- [x] Remove all __pycache__ directories from app code
- [x] Remove .pytest_cache, frontend/dist, frontend/node_modules/.vite

## Testing
- [x] Unit tests for extraction_service.py
- [x] Unit tests for query_builder.py
- [x] Unit tests for embedding_service.py
- [x] Integration tests for vector_service.py
- [x] End-to-end tests for hybrid RAG pipeline
- [ ] Add unit tests for anti-hallucination guard (_message_asks_about_unavailable_attribute)
- [ ] Add unit tests for greeting shortcut (_is_greeting_only)

## Deployment
- [ ] Run `reindex_profiles.py` one-time to load 5105 profiles into Qdrant (~11 min)
- [ ] Restart FastAPI server to pick up latest code
- [ ] Run deployment acceptance tests
- [ ] Install and verify live payment-gateway adapter (blocked — needs business choice)

## Verification
- [x] 134/134 backend tests passing
- [ ] Test end-to-end: "96 kuli maratha kolhapur engineer mulgi" → MySQL results
- [ ] Test end-to-end: "modern but traditional girl" → Qdrant vector fallback
- [ ] Test: "mala pune til mulgi dakhav" → Marathi profiles
- [ ] Test: "tell me about her family" → profile_detail → family fields
- [ ] Test: "tice shikshan kay aahe" → Marathi detail → education
