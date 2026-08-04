# Architecture

## Legacy Architecture (Intent → SQL generation)

```text
User Message
  -> Intent Classifier (llama-3.1-8b, 10 tokens) -> "database" or "general"
    -> "database": SQL Generator (llama-3.3-70b) -> raw SQL -> MySQL -> Formatter -> Response
    -> "general": BASE_SYSTEM_PROMPT -> LLM -> Response (HALLUCINATION RISK)
```

## Current Architecture (Hybrid RAG)

### Query Flow

```text
User Message (English / Marathi / Hindi / Hinglish / mixed)
  |
  | [Feature Flag: CHAT_ENGINE = legacy | hybrid_rag]
  |
  v
extraction_service.py — STRUCTURED EXTRACTION (llama-3.3-70b)
  |                     outputs structured JSON filters only (NO SQL)
  v
query_builder.py — PYTHON QUERY BUILDER -> parameterized SQL -> MySQL
  |
  +-- Results found? --> llm_service.py — GROUNDED GENERATION -> Formatted Response
  |
  +-- No results? ----> vector_service.py — Metadata Filtering -> Qdrant Vector Search
                            |               (bge-m3 embeddings, 1024d)
                            v
                        GROUNDED GENERATION -> "No matching profiles found."
```

### Subscription / Quota Flow

```text
Chat route
  -> Subscription/quota reservation
  -> Task-oriented AI orchestrator (gateway.py)
     -> published routing configuration
     -> provider adapter (Groq/Ollama/OpenAI-compatible)
     -> primary/fallback model
     -> normalized response and usage
  -> finalize/release credits atomically
  -> usage/cost ledger
  -> existing chat persistence
```

### Qdrant Vector Database (Separate Instance)

```text
                    +---------------------------+
                    |   Qdrant VPS              |
                    |  (KVM 1, 1GB)             |
                    |  Host: 187.127.170.116    |
                    +---------------------------+
                           |
                    gRPC/REST API (ports 6333/6334)
                           |
                    +---------------------------+
                    |   Main App VPS            |
                    |  (KVM 1, 1GB)             |
                    |  ** Cannot run bge-m3! ** |
                    |  Needs upgrade to 4-6GB   |
                    +---------------------------+

                    Profiles indexed as:
                    - Vector: bge-m3 embedding (1024d)
                    - Payload: Gender, Age, Caste, City, Religion,
                               Education, Occupation, Maritalstatus, Photo1
                    - Filters applied BEFORE vector search
```

> **⚠ bge-m3 RAM constraint:** The bge-m3 model requires ~4-6GB RAM for inference. The main app VPS (KVM 1, 1GB) is insufficient. The model is loaded lazily and used only during re-indexing and vector search fallback. Options: (1) upgrade main VPS to KVM 2 (2GB) or KVM 4 (4GB), (2) use a smaller model on the app VPS, (3) run embeddings on a separate instance.

## Folder Responsibilities

- `backend/app/api/`: HTTP validation, authentication dependencies, response contracts.
- `backend/app/services/`: business workflows and external database orchestration.
- `backend/app/ai/`: prompts, AI task execution, provider adapters, routing.
- `backend/app/models/`: SQLAlchemy persistence models.
- `backend/app/repositories/`: persistence access.
- `backend/app/schemas/`: Pydantic request/response types.
- `frontend/src/pages/`: customer and admin screens.
- `frontend/src/services/`: backend API clients.
- `frontend/src/hooks/`: query/mutation state.

## Profile & Partner-Preference Flow (2026-07-31)

```text
/app/profile (Edit Profile)
  |-- PATCH /api/profile            name / profile_image / MatriID
  |-- POST /api/profile/matri/link  validate MatriID -> read-only MySQL:
  |                                   register.PE_* (primary)
  |                                   -> advance_saveandsearch / basic_saveandsearch (fallback)
  |-- POST /api/profile/preference/start|next   rule-based decision tree (ZERO LLM calls)
  |-- GET|DELETE /api/profile/preference       saved filters
  v
user_preferences (SQLite: filter_key/value/source)
  v
Chat profile_search: saved preferences merge into accumulated_filters as defaults
  -> fewer LLM extraction calls, more relevant results
```

- Preferences live in the app SQLite DB; the matrimony MySQL DB is never written to.
- Decision-tree questions/options map directly to `DEFAULT_FILTERS` keys so answers become
  `build_profile_query` filters with no LLM involved.
- Known PE values are shown as "Keep / Change / Skip" confirm steps; only "Any"/empty
  categories get fresh questions.

## Data Relationships (Target)

- User 1 -> many Subscriptions.
- SubscriptionPlan 1 -> many immutable PlanVersions.
- User/Subscription 1 -> many AIUsageEvents and UsageReservations.
- Order 1 -> many PaymentAttempts; verified payment activates one Subscription.
- AIProvider 1 -> many AIModels.
- AITaskRoute maps a task key to ordered RouteTargets (model/fallback).
- ModelRate versions store effective input/output prices.
- AdminAuditEvent records configuration and entitlement changes.

These relationships are now implemented in `backend/app/models/commercial_model.py` with the following tables: `ai_providers`, `ai_models`, `ai_task_routes`, `ai_task_targets`, `subscription_plans`, `subscriptions`, `usage_reservations`, `ai_usage_events`, `payment_gateways`, `payment_orders`, and `admin_audit_events`.

## Authentication and Session Flow

JWT access and refresh tokens remain in HTTP-only cookies. Protected endpoints resolve the current `User`; admin endpoints additionally require `role == admin`. Subscription state is not embedded in JWTs, preventing stale entitlements after expiry/cancellation.

## External Integrations

- AI providers through adapters returning normalized content, token usage, request ID, and latency.
- MySQL remains read-only for the AI database assistant.
- Payment providers through an adapter supporting order creation, client verification, webhook verification, and refunds where supported.

## Dependency Rules

- Subscription services depend on normalized AI usage, never on Groq-specific code.
- AI task modules request task keys, never hard-coded provider/model IDs.
- Provider adapters do not know subscription rules.
- Payment adapters do not directly activate plans; verified events call the subscription service.
- Frontend displays server-provided balances and prices but cannot calculate authoritative entitlements.

## Implemented Request Flow

1. `ChatService` creates a request ID and atomically reserves the larger possible credit charge.
2. The reservation is committed before external AI work so concurrent requests observe it.
3. `intent_detection` selects normal or database processing through the published AI route.
4. General, SQL, formatting, and notice tasks call `app.ai.gateway.call_ai` by task key.
5. The gateway loads ordered enabled targets, checks context capacity, calls an OpenAI-compatible adapter, and falls back only for timeouts/rate limits/server failures.
6. Successful provider responses are normalized into usage/cost events; all task calls, including intent detection, are accumulated.
7. Successful chat finalization charges one or two configurable credits and releases the unused reservation. Failure releases all credits and the daily-message count.
8. Finalization is idempotent and usage events are stored server-side.

## Administrative Publication

- Plans are published as new versions; older purchases keep snapshots.
- AI providers reference environment-secret names rather than returning secret contents.
- Models store capability flags, context/output limits, and INR paise-per-million estimates.
- Task routes store ordered primary/fallback targets and reject disabled or incompatible models.
- Model and route health tests are explicit admin actions.
- Subscription assignments, credit adjustments, extensions, cancellation, and payment confirmation create audit events.
