# Hybrid RAG Pipeline — Implementation Summary

Created: 2026-07-26
Status: Phases 1-3 Complete, 29/29 tests passing

---

## Completed Phases

### Phase 1 — Hallucination Fixes (Critical)

**Problem:** `BASE_SYSTEM_PROMPT` had contradictory directives — "NEVER say you don't have access" + "NEVER invent profile details" — forcing the LLM to fabricate when intent classification failed.

**Changes:**
- `backend/app/core/prompts.py` — Removed contradictory directives. New rule: "If no matching profiles found, honestly say 'No matching profiles found'."
- `backend/app/core/prompts.py` — Replaced "Sneha Patil" / "Priya Sharma" example names with obfuscated placeholders to prevent leak.
- `backend/app/services/chat_service.py` — Added `_is_profile_query()` safety gate. Blocks profile-related queries from reaching the LLM if misclassified as "general".
- `backend/app/config.py` — Added `CHAT_ENGINE` feature flag (default: `"hybrid_rag"`, can be `"legacy"`).

### Phase 2 — Structured Extraction + Query Builder

**Problem:** Intent classification (llama-3.1-8b, 10 tokens) frequently misclassified Marathi/mixed-language subcaste queries. LLM-generated SQL produced wrong queries for variants like "96 Kuli Maratha".

**Changes:**
- `backend/app/core/prompts.py` — Added `STRUCTURED_EXTRACTION_PROMPT`: LLM outputs ONLY structured JSON filters, never SQL.
- `backend/app/services/extraction_service.py` — Calls LLM with extraction prompt, parses JSON, validates filters. Includes keyword-based fallback for reliability. Supports English, Marathi, Hindi, Hinglish, mixed-language.
- `backend/app/services/query_builder.py` — Python parameterized SQL builder. Maps filter fields (gender, caste, city, age, etc.) to column names. No LLM involvement in SQL generation.
- `backend/app/services/db_query_service.py` — Added `answer_database_question_hybrid()`: uses extraction + query builder instead of LLM SQL generation. Returns "No matching profiles found." for empty results (no LLM call).
- `backend/app/services/chat_service.py` — Routes to hybrid pipeline when `CHAT_ENGINE == "hybrid_rag"`. Falls back to legacy when `"legacy"`.

### Phase 3 — Embedding + Qdrant Vector Search

**Problem:** Exact SQL matching fails for caste name variations ("Maratha (96 Kuli)" vs "96K Maratha"), misspelled cities, or semantic queries like "modern but traditional girl".

**Changes:**
- `backend/requirements.txt` — Added `qdrant-client>=1.9.0`, `sentence-transformers>=3.0.0`, `torch>=2.1.0`
- `backend/app/services/embedding_service.py` — BAAI/bge-m3 local embedding model (1024-d, 100+ languages). Lazy-loaded singleton (loaded on first use, not at startup). Supports `embed_text()`, `embed_batch()`, `build_profile_document()`. Automatically skips system fields (MatriID, Photo1, Status, etc.).
- `backend/app/services/vector_service.py` — Qdrant client wrapper. Collection: `"profiles"`, vector size: 1024, distance: Cosine. Metadata payload indexes on: Gender, Caste, City, Religion, Maritalstatus, Age. Score threshold: >= 0.5.
- `backend/app/services/indexing_service.py` — Full re-index pipeline: fetches all active profiles from MySQL, builds embedding documents, generates embeddings in batches of 100, upserts to Qdrant.
- `backend/app/config.py` — Added `QDRANT_HOST`, `QDRANT_PORT`, `EMBEDDING_MODEL`, `EMBEDDING_BATCH_SIZE`.
- `backend/app/services/db_query_service.py` — Vector search fallback in `answer_database_question_hybrid()`: when MySQL returns 0 results, embeds the query, filters by metadata (gender/caste/city), searches Qdrant. Extracted `_add_photo_url()` as reusable helper.

---

## Current Complete Flow

```
User Message (English / Marathi / Hindi / Hinglish / mixed)
  │
  ▼
CHAT_ENGINE check
  │
  ├── "hybrid_rag" (default):
  │     │
  │     ▼
  │   answer_database_question_hybrid()
  │     │
  │     ├── extract_search_params() → LLM → JSON filters only
  │     │     Supports multilingual, maps "mulgi"→Female, "96 kuli"→subcaste
  │     │     Falls back to keyword extraction if LLM fails
  │     │
  │     ├── If not profile_search → returns is_profile_search=False
  │     │     → chat_service falls through to get_general_response() or safety gate
  │     │
  │     ├── build_profile_query() → Python → parameterized SQL
  │     │     No LLM involvement. Safe parameterized queries.
  │     │
  │     ├── MySQL execution
  │     │     ├── Results? → format_db_result() → response ✅
  │     │     └── 0 results? → Vector Search Fallback:
  │     │          1. build_profile_document(filters) → text
  │     │          2. embed_text("query: message + text") → 1024-d vector
  │     │          3. Metadata filter (Gender, Caste, City, Age)
  │     │          4. Qdrant similarity search (cosine, threshold >= 0.5)
  │     │          5. Results? → format_db_result() → response ✅
  │     │          6. No results? → "No matching profiles found."
  │     │
  │     └── response returned
  │
  └── "legacy":
        └── intent_llm → sql_generator → MySQL → format → response
```

---

## Key Files Reference

| File | Lines | Purpose |
|---|---|---|
| `backend/app/core/prompts.py` | 396 | BASE_SYSTEM_PROMPT, FORMAT_SYSTEM_PROMPT, STRUCTURED_EXTRACTION_PROMPT, SQL_GENERATION_SYSTEM_TEMPLATE, DB_SCHEMA_HINT, INTENT_SYSTEM_PROMPT |
| `backend/app/services/extraction_service.py` | 130 | `extract_search_params()`, `is_likely_profile_message()`, `_keyword_fallback()`, `validate_filters()` |
| `backend/app/services/query_builder.py` | 65 | `build_profile_query()` — maps filters to safe parameterized SQL |
| `backend/app/services/embedding_service.py` | 52 | `embed_text()`, `embed_batch()`, `build_profile_document()`, `get_embedding_model()` |
| `backend/app/services/vector_service.py` | 130 | `get_client()`, `upsert_profile()`, `upsert_batch()`, `search_with_filters()`, `delete_collection()` |
| `backend/app/services/indexing_service.py` | 85 | `reindex_all()` — batch re-index all active profiles |
| `backend/app/services/db_query_service.py` | 344 | `answer_database_question_hybrid()`, `answer_database_question()`, `execute_param_query()`, `_add_photo_url()` |
| `backend/app/services/chat_service.py` | ~280 | `process_message()` — routes based on CHAT_ENGINE, `_is_profile_query()` safety gate |
| `backend/app/config.py` | 107 | CHAT_ENGINE, QDRANT_HOST, QDRANT_PORT, EMBEDDING_MODEL |

---

## Configuration (.env)

```env
# Chat Engine
CHAT_ENGINE=hybrid_rag           # "hybrid_rag" or "legacy"

# Qdrant (vector database)
QDRANT_HOST=localhost            # IP of Qdrant server
QDRANT_PORT=6333                 # gRPC port

# Embedding model
EMBEDDING_MODEL=BAAI/bge-m3      # or intfloat/multilingual-e5-small
EMBEDDING_BATCH_SIZE=100
```

---

## Dependencies Added (Phase 3)

```
qdrant-client>=1.9.0
sentence-transformers>=3.0.0
torch>=2.1.0
```

Installed versions (laptop):
- qdrant-client 1.18.0
- sentence-transformers 5.6.1
- torch 2.13.0+cpu (Python 3.14.6 compatible! Windows x64)

---

## Deployment Checklist

- [ ] Install Qdrant on VPS (native binary, not Docker — saves ~200MB RAM)
- [ ] Set `QDRANT_HOST` in `.env` to Qdrant VPS IP
- [ ] Firewall: allow only app server IP on port 6333
- [ ] Run `reindex_all()` to load profiles into Qdrant (one-time, ~2-5 min)
- [ ] Verify bge-m3 model downloads (~2.2GB) on first embedding call
- [ ] Test with: "96 kuli maratha kolhapur engineer mulgi"
- [ ] Test with: "modern but traditional girl" (semantic, no exact match)
- [ ] Test with: "hi" (should still get greeting, not profile search)
- [ ] Set `CHAT_ENGINE=legacy` in `.env` if rollback needed

---

## Phase 4 — Schema Discovery + Dynamic Examples + Auto-Index

### Changes:
- `backend/app/services/schema_discovery.py` — Auto-discovers tables/columns/distinct values from MySQL INFORMATION_SCHEMA. Fetches lookup table values (caste, religion, education, occupation) and distinct column values from `register`. Cached with thread-safe lazy loading. Provides `build_schema_context()`, `get_all_castes()`, `get_all_religions()`, etc.
- `backend/app/services/example_generator.py` — Dynamically generates multilingual example queries using real values from schema_discovery. Cached, refreshed on demand. Never hardcodes values. Generates 6 example pairs in English/Marathi with real caste/city/education/occupation values.
- `backend/app/services/extraction_service.py` — Now appends dynamic examples from `generate_examples()` to `STRUCTURED_EXTRACTION_PROMPT` at runtime.
- `backend/app/main.py` — Lifespan now: (1) refreshes schema cache on startup, (2) auto-triggers reindex_all() when Qdrant collection is empty/reachable. Graceful skip if Qdrant unreachable.
- `backend/app/services/indexing_service.py` — No changes needed (already correct).
- `backend/docs/qdrant-setup.md` — Step-by-step Qdrant installation guide for Hostinger KVM 1 VPS.
- `backend/reindex_profiles.py` — Standalone one-time re-index script.
- `.env` — Added QDRANT_HOST, QDRANT_PORT, EMBEDDING_MODEL vars.

### Still Planned (future):
- `conversation_memory.py` — Filter accumulation across conversation turns
- Phase 5: Remove legacy modules (intent_llm.py, intent_detector.py, sql_generator.py)
