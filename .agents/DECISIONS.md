# Decisions

## 2026-08-02 — CF-7: first-candidate detail route is 1-based like resolve_contextual_profile

- Decision: SUGGESTION_ROUTES that address a candidate use the same 1-based
  `selected_index` convention as `resolve_contextual_profile` (`int(x) - 1`).
  "आधी पाहिलेले प्रोफाइल पुन्हा पाहा" was `selected_index: 0` → never matched → the
  branch replied "तुम्हाला कोणत्या प्रोफाइलची माहिती हवी आहे?" instead of the profile.
- Reason: an index can't silently mean "off by one"; the LLM-extraction path also emits
  1-based indexes ("प्रोफाइल 1"). The old test passed because it only asserted
  `done["type"] == "done"` — CF-7's strengthened test (LLM formatter must raise, reply
  must contain sectioned biodata) caught it.
- Impact: route now `selected_index: 1`; first candidate wins, falling back to
  `current_selected` from memory when no candidate list exists.

## 2026-08-02 — CF-6 biodata renders embedded in chat, zero-LLM, section chips routed

- Decision: rich profile biodata is rendered **inside the chat stream** (sectioned Marathi
  markdown + photo) with **no modal**, and is **zero-LLM** (`format_profile_biodata` /
  `format_profile_section`). Every section chip (`"{emoji} {title}"`) click-routes through
  `SUGGESTION_ROUTES` → `profile_detail` + `biodata_section` against the currently viewed
  profile (`current_selected` from memory), skipping `extract_search_params` and the LLM
  formatter entirely.
- Reason: deterministic, instant, offline-safe detail; section chips give a "consultant"
  drill-down UX consistent with CF-5 routing. This supersedes the old
  `_DETAIL_CATEGORY_QUESTION` bounce (the "which category?" question is no longer asked;
  the constant was removed from `chat_service.py`).
- Impact: `BIODATA_SECTIONS`/`_BIODATA_LABELS_MR`/routes in `matri_service.py`; profile_detail
  branch restructured in `chat_service.py`; `BIODATA_SECTION_CHIPS` on full/section replies.
  Legacy non-streaming `db_query_service.handle_profile_detail` keeps its own category
  question (unchanged path).

## 2026-08-02 — MyVivahAI identity: professional matrimonial consultant

- Decision: the assistant is branded **MyVivahAI — a professional matrimonial
  consultant, currently assigned to the Dishavadhuvar Matrimony platform**. It never
  self-identifies as "Dishavadhuvar AI" or "chatbot". Branding is parametric via config
  `ASSISTANT_NAME` / `PLATFORM_NAME` (`.env`-configurable), so the persona is reusable
  on future platforms without code edits.
- Reason: the product brief centres the assistant as a personal consultant; a
  generic-chatbot identity and hardcoded brand names hurt trust and portability.
- Impact: new `WELCOME_MESSAGE` (exact user-supplied Marathi copy), branded
  `GREETING_RESPONSES`, identity clause in all prompts and `format_db_notice`.

## 2026-08-02 — Marathi-first: ALL replies default to Marathi

- Decision: every assistant reply defaults to Marathi — including profile
  search/detail/comparison content replies even when the user types English/Hinglish.
  Hindi/English is used only when the user clearly writes in or requests that language.
- Reason: user explicitly chose "All replies default Marathi" over onboarding-only.
- Impact: prompts gain a language rule; `format_db_notice` and content formatting stay
  Marathi-first; supersedes the earlier assumption that only onboarding/greeting had to
  be Marathi.

## 2026-08-02 — MatriID gate: soft default, hard behind config

- Decision: the MatriID gate is **soft** by default — the welcome asks for the ID once
  (`matri_id_prompted` metadata flag), then proceeds with guest browsing. A **hard**
  mode (must link before any service) exists behind `MATRI_ID_GATE_MODE=hard`.
- Reason: matches the live demo experience (guest browsing works) while supporting
  strict mode per platform.
- Impact: first message of a brand-new conversation without a MatriID shows the
  `WELCOME_MESSAGE` + chips (CF-1).

## 2026-08-02 — Known DB preferences auto-apply, never re-ask

- Decision: in the **chat onboarding** path, known preferences from the linked
  MatriID are silently applied; only missing/"Any" categories are asked. The
  "कायम ठेवा?" confirm steps are dropped from chat onboarding.
- Reason: user chose "Auto-apply, never ask"; fewer steps, less friction.
- Impact: `core/questionnaire.py` gains a `missing_only` mode; the Profile-page
  questionnaire path (`start_questionnaire`/`advance_questionnaire`) is unchanged.

## 2026-08-02 — Search-early before full questionnaire

- Decision: chat shows matches as soon as the profile is "viable to search" instead of
  waiting for the full questionnaire. All strategies stay in code behind
  `ONBOARDING_SEARCH_STRATEGY`: `gender_plus_core` (**default**: gender + one of
  age/city/education), `gender_only`, `full_only`. User can flip via a short config
  change.
- Reason: user asked to keep all strategies in code and start with the first; early
  matches improve perceived speed and let users refine via chips.
- Impact: `is_viable_search()` gates search-early in `chat_service.py` (CF-3).

## 2026-08-02 — Onboarding runs only with zero prior conversations

- Decision: full onboarding (welcome + gate + questionnaire + summary) runs only when
  the MatriID is linked AND the user has **zero prior conversations anywhere**. Any
  prior conversation skips onboarding and restores context / welcome-back instead.
- Reason: returning users should not re-enter onboarding; matches "welcome-back"
  memory requirement.
- Impact: `chat_service.py` checks prior-conversation count before onboarding (CF-3).

## 2026-08-02 — Rich biodata embedded in chat

- Decision: profile detail renders as **chat-embedded rich biodata** (sectioned
  Marathi biodata + follow-up chips); no modal.
- Reason: user chose chat-embedded rich biodata for the consultant experience.
- Impact: CF-6 formats biodata inline in the chat stream.

## 2026-08-02 — Memory persisted in assistant metadata; welcome-back for returning users

- Decision: conversation memory (`last_topic`, `viewed_profiles`, `compared_pairs`,
  `last_filters`) is persisted as explicit keys in each assistant message's
  `metadata_json` (derived by `_enrich_memory` from existing metadata), and restored
  by `_load_history` (first non-None wins, newest-first). A linked user starting a
  **brand-new** conversation who already has prior conversations gets a Marathi
  "परत स्वागत!" prefix + topic-aware chips (profile_search/profile_detail/comparison/
  questionnaire → `WELCOME_BACK_SUGGESTIONS`, else generic). Guests, continuing
  conversations, and first-ever chats get no welcome-back.
- Reason: no new tables needed — reuses the existing metadata column; "welcome-back"
  restores context across conversations without re-entering onboarding (CF-3).
- Impact: `_enrich_memory` + `_load_history` + `_welcome_back`/
  `_last_topic_across_conversations` in `chat_service.py`; `handle_profile_comparison`
  returns `compared_pair`; `_load_history` also restores `questionnaire_searched`
  (fixes search-early repeating across turns). CF-4.

## 2026-08-02 — Suggestion chips are deterministic; routed without LLM

- Decision: follow-up suggestion chips are generated deterministically by
  `build_suggestions(context)` (matri link → `questionnaire_done` → `last_topic` →
  generic) and clicks on the actionable chips match `SUGGESTION_ROUTES` by exact
  phrase, skipping `extract_search_params` entirely (resume/new/next search,
  comparison, first-candidate detail; `reset_filters` clears accumulated filters).
  No LLM is used to generate or route them. Non-routed chips still fall through to
  the normal chat pipeline.
- Reason: zero-cost, deterministic UX; the doc decision #8 ("chips click through
  SUGGESTION_ROUTES phrase matching, no LLM") and the frontend chips drive the
  consultant flow without burning tokens.
- Impact: `build_suggestions` + `SUGGESTION_ROUTES` in `chat_service.py`; every
  `done` event carries chips; `ChatMessage.jsx`/`useChat.js`/`EmptyState.jsx` render
  and persist them. CF-5.

## 2026-08-02 — `.agents/` updates explicitly requested

- Decision: the user asked to update the `.agents/` folder so all decisions and the
  plan are remembered ("update agents folder according so will remmber all the things
  and start step by step"). This reverses the earlier "forget about agents folder"
  instruction; docs are the source of truth again per `.agents/README.md`.

## 2026-07-31 — Partner preferences stored in app SQLite, matrimony DB stays read-only

- Decision: collected partner-preference answers are stored in the app's SQLite
  `user_preferences` table; the live matrimony MySQL DB is never written to.
- Reason: the existing MySQL layer is deliberately read-only (`validate_select_sql` blocks
  non-SELECT; PROJECT_CONTEXT restriction). Writing `PE_*` columns would touch production
  data and require a new write path with no safety precedent.
- Alternatives considered: write back to `register.PE_*`; rejected as risky and against the
  read-only policy.
- Impact: `register` and `basic/advance_saveandsearch` remain read-only lookup sources.

## 2026-07-31 — Saved preferences auto-apply as chat search defaults

- Decision: once a user has linked a MatriID and/or answered the questionnaire, the stored
  preference filters merge into `accumulated_filters` for `profile_search` intents so
  messages like "find me a bride" resolve from saved preferences with minimal LLM extraction.
- Reason: reduces LLM extraction/formatting calls and improves result relevance — the core
  cost-effectiveness goal.
- Impact: `chat_service.py` / `db_query_service.py` load `UserPreference` rows and merge as
  defaults before extraction merges message filters.

## 2026-07-31 — Preference source priority: PE_* columns, then saved searches

- Decision: when linking a MatriID, partner expectations come from `register.PE_*` columns
  first; a category is filled from the latest `advance_saveandsearch` row, then
  `basic_saveandsearch`, only when the PE value is empty or "Any".
- Reason: PE_* is the canonical partner-expectation source; saved searches are filters users
  used at least once and are a good fallback.
- Impact: `matri_service.fetch_partner_expectations()` implements the cascade.

## 2026-07-31 — Questionnaire pre-fills and confirms known values

- Decision: the questionnaire shows known preferences as "Keep X / Change / Skip" confirm
  steps and only asks fresh questions for "Any"/empty categories.
- Reason: fewer steps, less user effort, no LLM needed to personalize ordering.
- Impact: `core/questionnaire.py` builds the question flow from the PE summary; branching is
  pure code (zero LLM calls per question).

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
