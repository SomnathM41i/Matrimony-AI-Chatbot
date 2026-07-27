# Decisions

## 2026-07-23 — Provider-independent AI and subscription boundaries

- Decision: AI tasks will use a router and normalized provider interface; subscription logic will use normalized usage and user-facing credits rather than provider-specific APIs.
- Reason: providers, models, endpoints, token prices, and availability can change without invalidating subscriptions.
- Alternatives considered: keep direct Groq calls and add plan checks around them; rejected because it hard-couples commercial logic to one provider.
- Impact: current Groq client will become an adapter and all task modules will select routes by task key.

## 2026-07-23 — Versioned plans and rates

- Decision: plan benefits and model rates will be versioned/snapshotted.
- Reason: later administrative edits must not rewrite historical payments, entitlements, or costs.
- Impact: additional persistence and admin publication workflow are required.

## 2026-07-23 — Server-authoritative commercial state

- Decision: prices, credits, subscription status, token cost, and payment verification are authoritative only on the backend.
- Reason: browser state is user-controlled and cannot safely enforce billing.
- Impact: existing local-storage token display remains informational only.

## 2026-07-23 — Environment-referenced provider secrets

- Decision: provider and payment configuration stores environment-variable names, not readable secret values.
- Reason: administrators need dynamic routing/configuration without exposing credentials through APIs, browser storage, database exports, or logs.
- Alternatives considered: encrypted secret contents in the application database; deferred because safe key management and rotation require a separate deployment secret.
- Impact: adding a provider requires setting its secret in the server environment and entering only that variable name in the admin panel.

## 2026-07-23 — Manual payments before live gateway selection

- Decision: implement provider-neutral payment contracts, server-authored pending orders, and audited manual confirmation; do not simulate online checkout.
- Reason: no gateway or sandbox credentials were supplied, and falsely activating client-reported payments would be unsafe.
- Alternatives considered: assume a gateway and hard-code it; rejected as contrary to provider independence and payment security.
- Impact: live payment integration is an explicit blocked follow-up; subscriptions can be fully tested and operated manually meanwhile.

## 2026-07-23 — Atomic maximum-credit reservation

- Decision: reserve the maximum of normal/database credit cost with a conditional database update, then finalize idempotently.
- Reason: the request type is known only after intent detection and concurrent messages must not overspend a balance.
- Impact: long-running provider calls do not leave an open write transaction, failures release credits, and duplicate finalization cannot double-charge.

## 2026-07-23 — Domain persona without forced redirection

- Decision: keep matchmaking as the assistant's primary persona while answering harmless general questions directly.
- Reason: forcing coding, mathematics, or unclear input back into matchmaking creates irrelevant replies and a poor user experience.
- Impact: provider/model changes inherit the same behavior through the centrally managed general-chat system prompt; internal reasoning and language-detection notes must never be shown to users.

## 2026-07-26 — Hybrid RAG pipeline replaces intent → SQL generation

- Decision: Replace the current Intent Detection → LLM SQL Generation pipeline with a Hybrid RAG pipeline using Structured Extraction → Python Query Builder → MySQL + Qdrant fallback.
- Reason: The intent classifier (llama-3.1-8b, 10 tokens) frequently misclassifies Marathi/mixed-language and subcaste queries, causing the general response path to hallucinate fabricated profiles. LLM-generated SQL also produces wrong queries when caste names or locations don't match database values exactly.
- Alternatives considered: (1) Fixing the intent classifier with more examples — rejected because it's a brittle band-aid. (2) Pure semantic search without structured filters — rejected because matrimonial search requires exact gender/caste/age matching. (3) Keeping the current system with better prompts — rejected because the fundamental contradiction between "never refuse" and "never fabricate" cannot be resolved within the same prompt.
- Impact: New modules: extraction_service.py, query_builder.py, embedding_service.py, vector_service.py, indexing_service.py, schema_discovery.py, example_generator.py. Removed modules (after validation): intent_llm.py, intent_detector.py, sql_generator.py (generate_sql only; validate_select_sql kept). Feature flag CHAT_ENGINE allows gradual migration.

## 2026-07-26 — Local multilingual embedding model (BAAI/bge-m3)

- Decision: Use BAAI/bge-m3 as the local embedding model for semantic search, installed directly on the application server.
- Reason: No API dependency, no per-request cost, user profile data never leaves the server, supports 100+ languages including Marathi and Hindi, 1024-dimensional embeddings for high-quality cross-lingual retrieval.
- Alternatives considered: all-MiniLM-L6-v2 — rejected because it is primarily English-focused. multilingual-e5-large — kept as fallback. OpenAI embeddings — rejected due to API cost and data privacy concerns. API-based embedding services — rejected due to latency, cost, and offline requirement.
- Impact: Requires ~2.2GB disk for model download, ~4-6GB RAM during inference on CPU. Adds sentence-transformers and torch to requirements.txt. Model is loaded at application startup (or on first query).

## 2026-07-26 — Qdrant on separate VPS instance

- Decision: Deploy Qdrant vector database on a separate KVM 1 VPS instance, accessed via gRPC/REST API from the main application server.
- Reason: Docker is too heavy for the existing KVM 1 Hostinger VPS (1 vCPU, 1GB RAM). A separate lightweight instance for Qdrant keeps the main app server unburdened.
- Alternatives considered: Qdrant on the same VPS without Docker — rejected because 1GB RAM is insufficient to run both the Python app (with bge-m3) and Qdrant reliably. ChromaDB — rejected in favor of Qdrant's production-ready metadata filtering and hybrid search support. pgvector in MySQL — rejected because embeddings should not be co-located with the OLTP MySQL database.
- Impact: Additional VPS cost (~$5-10/month). Qdrant binary deployment (not Docker) to minimize resource usage. Network latency between servers (~1-5ms on same provider). Firewall rules to allow only the app server IP.

## 2026-07-26 — No hardcoded examples; everything auto-discovered

- Decision: All search examples, synonym mappings, and multilingual variations are generated dynamically from actual database values — never hardcoded in prompts or code.
- Reason: Hardcoded examples become stale as data changes, leak into LLM output as hallucinations (e.g., "Sneha Patil" and "Priya Sharma" from FORMAT_SYSTEM_PROMPT examples), and miss real database variations like "96 Kuli Maratha" vs "Maratha (96 Kuli)" vs "96K Maratha".
- Impact: New schema_discovery.py and example_generator.py modules introspect the MySQL database at startup to discover real cities, castes, occupations, and subcastes. The indexing service auto-re-indexes when schema changes are detected.

## 2026-07-26 — Feature flag for gradual migration

- Decision: Implement the entire Hybrid RAG pipeline behind a CHAT_ENGINE feature flag (values: "legacy" or "hybrid_rag").
- Reason: Allows gradual deployment, instant rollback, A/B comparison testing, and debugging without downtime.
- Impact: Config.py gains CHAT_ENGINE setting. Chat_service.py has a decision point at process_message that routes to either the legacy or new pipeline. After thorough testing, the legacy path and its modules (intent_llm, intent_detector, sql_generator LLM parts) are removed.

## 2026-07-26 — Phase 1 priority: Stop hallucinations before adding new features

- Decision: Fix the contradictory BASE_SYSTEM_PROMPT directives and add a safety gate for profile queries in the general path as the very first implementation step.
- Reason: Hallucinating fake profiles is the most severe user-facing bug. Every other improvement (embeddings, Qdrant, conversation memory) is meaningless if the system continues to fabricate data.
- Impact: Prompt changes + safety gate can be deployed independently of the full RAG pipeline, providing immediate relief while the rest is built and tested.
