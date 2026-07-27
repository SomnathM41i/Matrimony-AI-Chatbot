# Hybrid RAG Module Context

## Objective

Replace the current Intent Detection → LLM SQL Generation pipeline with a Hybrid RAG pipeline that eliminates hallucinated profiles. The new pipeline uses Structured Extraction (LLM outputs JSON filters only) → Python Query Builder (parameterized SQL) → MySQL (primary) → Qdrant vector search (semantic fallback) → Grounded Generation (LLM formats only, never invents).

## Architecture Overview

```
User Query
  ↓
Structured Extraction (llama-3.3-70b) → JSON filters
  ↓
Python Query Builder → parameterized SQL → MySQL
  ↓
If results found → Grounded Generation → Formatted Response
  ↓
If 0 results → Metadata Filter → Qdrant Vector Search → Grounded Generation
  ↓
If still 0 results → "No matching profiles found." (NO LLM call)
```

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Intent handling | Structured extraction (JSON only) | LLM never generates SQL. Never free-text answers. |
| SQL generation | Python query builder | Parameterized, safe, no LLM involvement. |
| Primary search | MySQL (exact match) | Fast, precise for structured fields (gender, caste, city, age). |
| Fallback search | Qdrant (vector similarity) | Handles approximate/spelling/variant matches. |
| Embedding model | BAAI/bge-m3 (local) | Multilingual, offline, no API cost, 1024d. |
| Vector DB | Qdrant (separate VPS) | Metadata filtering + hybrid search, production-ready. |
| Feature flag | CHAT_ENGINE = legacy|hybrid_rag | Gradual migration, rollback, A/B testing. |
| Examples | Auto-generated from real DB | Never hardcoded, never leaked. |

## New Files

| File | Purpose |
|---|---|
| `backend/app/services/extraction_service.py` | Calls LLM with STRUCTURED_EXTRACTION_PROMPT, returns structured JSON. |
| `backend/app/services/query_builder.py` | Builds parameterized SQL from structured filters. |
| `backend/app/services/embedding_service.py` | BAAI/bge-m3 local embedding model. |
| `backend/app/services/vector_service.py` | Qdrant client: metadata filtering + vector search. |
| `backend/app/services/schema_discovery.py` | Auto-discovers tables, columns, distinct values from MySQL. |
| `backend/app/services/example_generator.py` | Generates multilingual example queries from real data. |
| `backend/app/services/indexing_service.py` | Full re-index + incremental index for Qdrant. |

## Modified Files

| File | Changes |
|---|---|
| `backend/app/core/prompts.py` | Add STRUCTURED_EXTRACTION_PROMPT, GROUNDED_GENERATION_PROMPT. Fix BASE_SYSTEM_PROMPT contradictions. Fix FORMAT_SYSTEM_PROMPT example names. |
| `backend/app/services/chat_service.py` | Add safety gate for profile queries in general path. Add CHAT_ENGINE routing. Add conversation memory (filter accumulation). |
| `backend/app/services/db_query_service.py` | Rewrite: structured extraction → query builder → MySQL → Qdrant fallback → grounded response. |
| `backend/app/config.py` | Add CHAT_ENGINE, QDRANT_HOST, QDRANT_PORT, EMBEDDING_MODEL. |
| `backend/requirements.txt` | Add qdrant-client, sentence-transformers, torch. |

## Removed Files (after validation)

| File | Replacement |
|---|---|
| `backend/app/ai/intent_llm.py` | extraction_service.py (structured JSON, not intent classification) |
| `backend/app/ai/intent_detector.py` | Safety gate in chat_service.py (lightweight, defensive) |
| `backend/app/ai/sql_generator.py` (generate_sql only) | query_builder.py (Python parameterized SQL) |

## Structured Extraction JSON Format

```json
{
  "intent": "profile_search",
  "filters": {
    "gender": "Female",
    "caste": "Maratha",
    "subcaste": "96 Kuli",
    "city": "Kolhapur",
    "age_min": null,
    "age_max": 30,
    "religion": null,
    "marital_status": null,
    "education": "Engineer",
    "occupation": null
  },
  "preferences": [],
  "limit": 4
}
```

## Query Builder Rules

1. Always add `WHERE LOWER(Status) = LOWER('Active')`.
2. Gender, Caste, Religion, Maritalstatus → exact match (`LOWER(col) = LOWER(?)`).
3. City → LIKE match across City, Dist, State.
4. Age → range match (`Age BETWEEN ? AND ?` or `Age <= ?` / `Age >= ?`).
5. Education, Occupation → LIKE match for flexibility.
6. Always `ORDER BY Regdate DESC`.
7. Always `LIMIT ?`.
8. All parameters passed as `?` placeholders (parameterized query).

## Qdrant Collection Schema

```
Collection: "profiles"
Vector size: 1024 (bge-m3)
Distance: Cosine

Payload fields (with indexes):
  - MatriID (keyword)
  - Name (text)
  - Gender (keyword)
  - Age (integer)
  - Caste (keyword)
  - City (keyword)
  - Dist (keyword)
  - State (keyword)
  - Religion (keyword)
  - Maritalstatus (keyword)
  - Education (text)
  - Occupation (text)
  - Photo1 (keyword)
  - PhotoURL (keyword)

Filtering: Apply metadata filters FIRST, then vector similarity search.
```

## Profile Document for Embedding

Generated automatically from ALL non-null meaningful fields:

```
Gender: Female. City: Kolhapur. Caste: 96 Kuli Maratha. 
Education: BE Computer. Occupation: Software Engineer. 
Age: 26. Religion: Hindu. Maritalstatus: Never Married. 
Height: 5'4". Annualincome: 5 Lakh.
```

The `Name` field is intentionally excluded from embedding to prevent name-based bias in semantic search. Names are only shown in the final response.

## Testing Requirements

- Every test case uses REAL database values (cities, castes, occupations).
- No fabricated names or profiles in expected outputs.
- Test languages: English, Marathi, Hindi, Hinglish, mixed-language.
- Test scenarios: exact match, approximate match, no match, follow-up refinement.
- Edge cases: empty query, special characters, very long queries, numeric-only queries.

## Deployment Notes

- bge-m3 model download: ~2.2GB on first run.
- bge-m3 RAM usage: ~4-6GB during CPU inference. If KVM 1 (1GB) is insufficient, options:
  (a) Upgrade to KVM 2 or KVM 4.
  (b) Use a smaller model on the app VPS, use bge-m3 only for offline indexing.
- Qdrant on separate VPS: install as binary (not Docker), ~50MB binary, ~200-500MB RAM for moderate data.
- Firewall: allow only the app server IP to connect to Qdrant (port 6333 for gRPC, 6334 for HTTP).
