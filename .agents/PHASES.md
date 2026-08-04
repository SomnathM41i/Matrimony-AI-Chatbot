# Phases

This file holds phase plans. See `modules/profile-preferences-context.md` for the
partner-preference contract and `modules/conversation-consultant-context.md` for the
Consultant track (CF-0..CF-7).

---

## Conversation Flow Enhancement — "Consultant" Track (CF-0..CF-7)

Full plan + decisions: `.agents/modules/conversation-consultant-context.md`.

| Phase | Scope | Files (primary) | Done |
|---|---|---|---|
| CF-0 | MyVivahAI identity + Marathi-first: `ASSISTANT_NAME`/`PLATFORM_NAME` config; identity + language clause in all prompts; new `WELCOME_MESSAGE` (exact copy); branded greetings; persona answer; update greeting-copy tests; add persona/language test | `config.py`, `.env.example`, `core/prompts.py`, `services/llm_service.py`, `services/chat_service.py`, `tests/test_chat_error_messages.py` | ✅ |
| CF-1 | Identity gate: first message of new conversation without MatriID → `WELCOME_MESSAGE` + chips; `MATRI_ID_GATE_MODE` soft/hard; `matri_id_prompted` metadata flag | `services/chat_service.py`, `config.py` | ✅ |
| CF-2 | Rich profile load + Marathi summary: expand `_fetch_register_row`; `format_user_profile_summary()` (zero-LLM Marathi); show once after link on first-ever conversation | `services/matri_service.py`, `services/chat_service.py` | ✅ |
| CF-3 | Missing-only questionnaire + search-early: `build_nodes(..., missing_only=True)`; `is_viable_search()` per `ONBOARDING_SEARCH_STRATEGY`; search early + refinement chips; onboarding only when zero prior conversations | `core/questionnaire.py`, `services/chat_service.py`, `config.py` | ✅ |
| CF-4 | Conversation memory + welcome-back: persist/restore `last_topic`/`viewed_profiles`/`compared_pairs`/`last_filters`; Marathi "परत स्वागत!" + contextual chips | `services/chat_service.py` | ✅ |
| CF-5 | Suggestions engine: deterministic `build_suggestions(context)` in `done` events; `SUGGESTION_ROUTES` click handling; chips in `ChatMessage.jsx` + `useChat.js`; dynamic `EmptyState.jsx` | `services/chat_service.py`, `frontend/src/components/ui/ChatMessage.jsx`, `frontend/src/hooks/useChat.js`, `frontend/src/components/ui/EmptyState.jsx` | ✅ |
| CF-6 | Chat-embedded rich biodata: sectioned Marathi biodata + follow-up chips; reuse `resolve_contextual_profile` | `services/chat_service.py`, `services/matri_service.py`, `services/db_query_service.py`, `frontend/src/components/ui/ChatMessage.jsx` | ✅ |
| CF-7 | Tests + verification: new tests per phase; update `test_matri_auto_link.py` + `test_chat_questionnaire_flow.py`; suite green; docs updated | `tests/` | ✅ |

Key decisions (2026-08-02): MyVivahAI identity, Marathi-first (ALL replies),
MatriID gate soft-default / hard-behind-config, known prefs auto-apply, search-early
`gender_plus_core` default, onboarding only when zero prior conversations, chat-embedded
biodata. `.agents/` updates explicitly requested by user (reverses earlier constraint).

---

## Post-Consultant Track — P8-P11

| Phase | Scope | Files (primary) | Done |
|---|---|---|---|
| P8 | More tests: unit tests for the deterministic zero-LLM formatting helpers (`add_photo_url`/`_photo_url`/`format_filter_summary`/`format_no_matches_notice`/`format_profile_results_markdown`) | `tests/test_db_query_formatting.py` | ✅ |
| P9 | Known-failure fix: `test_register_only_fetch` photo URL derived from `settings.PHOTO_BASE_URL` (`.in`) instead of hardcoded `.com`; suite fully green | `tests/test_matri_service.py` | ✅ |
| P10 | AI evaluation: offline rubric harness (Marathi-first, no-hallucination, routing, deterministic, suggestions, identity) — 10 scenarios, `python -m tests.eval_harness` → 10/10 | `tests/eval_harness.py` | ✅ (harness; live eval pending deployment) |
| P11 | KVM2 deploy: acceptance tests + rollout on target VPS — runbook written; live execution needs server access/secrets | `.agents/modules/deployment-runbook.md`, `tests/test_acceptance.py` | Runbook ✅ / live steps pending |

---

# Profile Edit, MatriID Linking & Cost-Effective Partner-Preference Questionnaire

Feature: give authenticated users an **Edit Profile** option, allow them to link their
**matrimony website user ID (`MatriID`)**, fetch their existing **partner expectations**
(`register.PE_*` + saved-search tables) from the live matrimony MySQL DB, and then run a
**rule-based decision-tree questionnaire** (zero LLM calls) that refines/captures their
partner preferences. Those structured preferences then **auto-apply as default filters** in
chat profile searches — reducing LLM extraction/formatting cost and increasing result relevance.

## Confirmed Decisions (2026-07-31)

1. **Storage**: collected preferences live in the app's SQLite DB (`user_preferences` table).
   The matrimony MySQL DB stays strictly read-only.
2. **Chat auto-apply**: saved questionnaire preferences merge into profile-search filters as
   defaults (`accumulated_filters`) so phrases like "find me a bride" resolve from saved
   preferences with minimal extraction.
3. **Preference source priority**: `register.PE_*` columns first; fall back to the latest
   `advance_saveandsearch` then `basic_saveandsearch` row for the linked `MatriID` when PE
   fields are empty / "Any".
4. **Questionnaire UX**: pre-fill & confirm known values ("Keep Hindu?" / Change), only ask
   fresh questions for "Any"/empty categories — fewer steps, no LLM.

## Phase Plan

| Phase | Scope | Files (primary) | Done |
|---|---|---|---|
| 1 | Backend data layer: `User` gains `matri_id`/`matri_name`/`matri_synced_at`; new `UserPreference` table; migration; `UserResponse` extension; preference repository | `models/user_model.py`, `models/user_preference_model.py`, `models/__init__.py`, `database.py`, `schemas/auth_schema.py`, `repositories/user_repository.py` (+ `preference_repository.py`) | In progress |
| 2 | MatriID sync service: validate `MatriID` against `register`, build structured PE summary, saved-search fallback | `services/matri_service.py` | |
| 3 | Decision-tree questionnaire engine + JSON question tree; `start`/`next`/`save` flow | `core/questionnaire.py`, `services/matri_service.py` | |
| 4 | Chat auto-apply: merge saved preferences as default filters in `profile_search` | `services/chat_service.py`, `services/db_query_service.py`, `services/extraction_service.py` | |
| 5 | Profile API routes (JWT-guarded) registered in `main.py` | `api/profile_routes.py`, `main.py` | |
| 6 | Frontend: `/app/profile` page, `profileService.js`, Sidebar entry, router, `useAuth` refresh | `pages/Profile.jsx`, `services/profileService.js`, `components/ui/Sidebar.jsx`, `app/router.jsx`, `hooks/useAuth.js` | |
| 7 | Tests + verification: unit tests for matri service + questionnaire branching; backend suite; frontend build | `tests/test_matri_service.py`, `tests/test_questionnaire.py` | |

## Definition of Done (per phase)

- Backend: phase code compiles; existing test suite stays green; new tests added where feasible.
- Frontend: `npm run build` passes; new page reaches routes under `/app`.
- Docs: `WORK_LOG.md`, `CHANGELOG.md`, `TODO.md`, and affected context docs updated.
- No writes to the matrimony MySQL DB; no changes to commercial/subscription logic.

## Security / Constraints

- MatriID lookups use server-built parameterized queries only (via `execute_param_query`).
- Profile/preference endpoints require `get_authenticated_user`.
- Never expose `PE_*`/profile data beyond what the member's own ID legitimately permits.
- MySQL read-only policy from `PROJECT_CONTEXT.md` remains non-negotiable.
