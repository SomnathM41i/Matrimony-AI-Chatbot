# Changelog

## 2026-08-02 — P10 offline AI-eval harness + P11 deployment runbook

### Added
- **P10 — `tests/eval_harness.py`**: offline rubric harness (pytest-invisible, no
  `test_`-prefixed functions). Runs 10 scenarios through the real stream pipeline with
  mocked DB/LLM boundaries and scores the rubric: marathi_first, no_hallucination,
  routing, deterministic rendering, suggestions, identity. Covers guest welcome gate,
  branded greeting, persona question, resume-search route, no-match honesty, first-
  candidate + section biodata, welcome-back, LLM-extraction Marathi search, comparison.
  Run: `python -m tests.eval_harness` → **10/10 pass**. Note: harness scenarios must
  keep `gender` out of `default_filters` (or the CF-3 questionnaire auto-start hijacks
  chip messages) — a documented harness-setup rule, not a product bug.
- **P11 — `.agents/modules/deployment-runbook.md`**: full Hostinger KVM2 deploy runbook
  (env reference incl. CF vars, Qdrant, schema boot + reindex, 2GB bge-m3 memory plan,
  uvicorn systemd + nginx SSE, acceptance + eval verification, manual smoke, rollback,
  post-deploy checklist, open constraints). Live execution needs server access/secrets.

## 2026-08-02 — P11 prep: acceptance smoke script fixed (ISSUES.md)

### Fixed
- **`tests/test_acceptance.py`** (ISSUES.md "permanently green" item): the function was
  a bare `test_acceptance()` that swallowed every exception, returned a bool, and made
  pytest report "1 passed" even against a dead server. Now renamed `run_acceptance()`
  (no `test_` prefix → pytest collects **0** tests from the file) and every check uses a
  real `_assert` that raises on failure; `__main__` exits non-zero on failure. Manual run:
  `python -m tests.test_acceptance` against a running server.
- The documented `--ignore=tests/test_acceptance.py` flag is no longer required.

### Verification
- Backend suite: `python -m pytest tests -q` → **430 passed / 0 failed** (first run
  without the ignore flag). Frontend `npm run build` succeeds.

## 2026-08-02 — P8 more tests + P9 known-failure fix (suite fully green)

### Fixed
- **P9**: `test_register_only_fetch` hardcoded `https://dishavadhuvar.com/gallary/...`
  while config default + `.env` pin `https://dishavadhuvar.in/gallary/` (hcdn CDN; both
  domains verified serving). The assertion now derives the expected photo URL from
  `settings.PHOTO_BASE_URL`, so it can no longer drift from the active config.

### Added
- **P8**: `tests/test_db_query_formatting.py` (15 tests) covering the deterministic
  zero-LLM formatters used by the CF-5/CF-6 routes: `add_photo_url` / `_photo_url`
  (base-URL join, leading-slash strip, `nophoto.jpg` → `""`, missing → `""`),
  `format_filter_summary` (age range, gender word, Marathi labels, manglik/complexion
  value mappings, empty), `format_no_matches_notice` (personalized head + सल्ला),
  `format_profile_results_markdown` (context header, numbered `![Name](PhotoURL)` cards,
  no-photo dash fallback, empty rows).

### Verification
- Backend suite: **430 passed / 0 failed** (first fully-green run; previously
  414 + 1 known P9). Frontend `npm run build` succeeds.
- Remaining phases: P10 (AI eval), P11 (KVM2 deploy) — require live infra/credentials.

## 2026-08-02 — CF-7 verification + first-candidate detail route fix

### Fixed
- **`SUGGESTION_ROUTES["आधी पाहिलेले प्रोफाइल पुन्हा पाहा"]`** (`chat_service.py`):
  `selected_index` was `0`, but `resolve_contextual_profile` resolves 1-based
  (`int(x) - 1`), so the chip never resolved a profile and replied
  "तुम्हाला कोणत्या प्रोफाइलची माहिती हवी आहे?" instead of rendering the profile.
  Now `selected_index: 1` → first candidate, falling back to `current_selected`
  from memory when no candidates exist.

### Tests
- `test_suggestions.py::test_first_candidate_detail_route_resolves_from_candidates`
  strengthened: patches `stream_format_db_result` to raise (proving CF-6 detail is
  zero-LLM), asserts the reply contains the sectioned biodata and that the done event
  carries `BIODATA_SECTION_CHIPS`. Removed the now-unused `_detail_stream` helper.

### Verified
- `test_matri_auto_link.py` (CF-2/CF-3 link reply = summary + missing-only) and
  `test_chat_questionnaire_flow.py` (missing-only + search-early) already reflect the
  final flow; `test_session_unification_e2e.py` green (2 tests).
- Backend suite: **414 passed / 1 known P9 failure** (`test_register_only_fetch`,
  .com vs .in — scheduled P9). Frontend `npm run build` succeeds.
- Consultant track CF-0..CF-7 complete ✅.

## 2026-08-02 — CF-6 chat-embedded rich biodata + section chips

### Added
- **`BIODATA_SECTIONS`** (`matri_service.py`): 8 Marathi sections — basic, education,
  family, physical, lifestyle, horoscope, partner expectations, location — each with
  `key`/`emoji`/`title`/`fields`.
- **Zero-LLM formatters**: `format_profile_biodata(row)` (header + photo + non-empty
  sections in order) and `format_profile_section(row, key)` (single-section drill-down);
  `_BIODATA_LABELS_MR` (= profile labels + `_BIODATA_EXTRA_LABELS_MR`), `_clean()` skips
  empty/legacy values, `_PE_LABELS_MR` fallback for partner fields.
- **`test_biodata.py`** (9 tests): formatter units, chip↔route coverage, and two stream
  tests (full biodata renders deterministically with `BIODATA_SECTION_CHIPS`; a section
  chip click renders only that section and skips LLM extraction + formatting).

### Changed
- **`SUGGESTION_ROUTES`** (`chat_service.py`): every biodata chip routes to
  `profile_detail` with a `biodata_section` key against the currently viewed profile
  (`current_selected` from memory) — no LLM.
- **profile_detail branch**: `fields=["all"]` (biodata) now renders the full sectioned
  biodata instead of the old `_DETAIL_CATEGORY_QUESTION` bounce; a section chip renders
  just that section (or "या प्रोफाइलसाठी ही माहिती उपलब्ध नाही."). Full row is fetched
  once and cached on MatriID match; full/section replies carry `BIODATA_SECTION_CHIPS`.
- Removed the now-unused `_DETAIL_CATEGORY_QUESTION` constant from `chat_service.py`
  (the `db_query_service.py` copy is still used by the legacy non-streaming path).

### Verification
- Backend suite: **414 passed / 1 known P9 failure**
  (`test_register_only_fetch`, .com vs .in — scheduled P9).
- Frontend: `npm run build` succeeds.

## 2026-08-02 — CF-5 deterministic suggestions engine + click routing

### Changed
- **`build_suggestions(context)`** (`chat_service.py`): deterministic Marathi
  follow-up chips injected into every `done` event (no LLM). Order of precedence:
  no MatriID → `WELCOME_SUGGESTIONS`; `questionnaire_done` →
  `QUESTIONNAIRE_DONE_SUGGESTIONS`; known `last_topic` → `WELCOME_BACK_SUGGESTIONS`;
  otherwise `GENERIC_WELCOME_BACK_SUGGESTIONS`. Chips already set by the identity gate
  or welcome-back are never overwritten.
- **`SUGGESTION_ROUTES`**: exact-phrase click routing that skips
  `extract_search_params` entirely — resume / new (resets accumulated filters) /
  next profile-search (deterministic, from memory filters), comparison, and
  first-candidate profile detail. No LLM call for these chips.
- **Chip sets**: `WELCOME_BACK_SUGGESTIONS["questionnaire"]` now fully routed
  ("माझ्या जोडीदाराच्या पसंती बदला" → "मागील सर्च चालू ठेवा").
- **Frontend**: `useChat.js` captures `doneEvent.suggestions` + history
  `meta.suggestions`; `ChatMessage.jsx` renders suggestion pills calling `onSend`;
  `EmptyState.jsx` suggestions are now dynamic by `needsMatriId`
  (`SUGGESTIONS_NO_ID` vs `SUGGESTIONS_LINKED`).

### Tests
- New `test_suggestions.py` (10 tests): `build_suggestions` precedence matrix,
  every actionable chip has a route, and three stream tests proving routes skip the
  LLM extraction (resume search, new-search resets filters, first-candidate detail).
- `test_conversation_memory.py`: `test_first_ever_user_gets_no_prefix` now expects
  generic chips (CF-5 adds suggestions to every reply).

### Verification
- Backend suite: **405 passed / 1 known P9 failure**
  (`test_register_only_fetch`, .com vs .in — scheduled P9).
- Frontend: `npm run build` succeeds.

## 2026-08-02 — CF-4 conversation memory + welcome-back

### Changed
- **Explicit memory fields** (`chat_service.py`): new `_enrich_memory(metadata,
  intent_label)` annotates each assistant message's metadata with `last_topic`
  (from the resolved intent), `viewed_profiles` (derived from
  `profile_candidates`), `compared_pairs` (from the new `compared_pair` in
  `handle_profile_comparison`'s metadata), and `last_filters` (copy of
  `accumulated_filters`). Existing explicit keys are never overwritten.
- **`_load_history` restore**: now restores those fields plus the previously
  unrestored `questionnaire_searched` flag — fixing a latent CF-3 issue where
  search-early could fire again on later turns of the same conversation.
- **Welcome-back**: `_welcome_back(user, user_id, conversation_id)` + 
  `_last_topic_across_conversations(user_id)` greet a linked returning user who
  starts a brand-new conversation with "परत स्वागत, {name}! 🙏" streamed as the
  first token plus topic-aware chips (`WELCOME_BACK_SUGGESTIONS` with a
  `GENERIC_WELCOME_BACK_SUGGESTIONS` fallback), carried in the `done` event via
  `_done_event`. The main-flow `done` event now goes through `_done_event` so
  metadata actually reaches the client. Questionnaire-flow metadata is enriched
  with `_enrich_memory(..., "questionnaire")`.

### Tests
- New `test_conversation_memory.py` (16 tests): `_enrich_memory` derivation +
  no-overwrite, `_load_history` restore (incl. `questionnaire_searched`),
  `_welcome_back` guards + topic/generic chips + AsyncMock tolerance,
  `_last_topic_across_conversations` newest-first scan, and two stream tests
  (returning user gets prefix + done suggestions + persisted memory; first-ever
  user gets neither).

### Verification
- Backend suite: **395 passed / 1 known P9 failure**
  (`test_register_only_fetch`, .com vs .in — scheduled P9).

## 2026-08-02 — CF-3 missing-only questionnaire + search-early

### Changed
- **`build_nodes(..., missing_only=True)`** (`core/questionnaire.py`): chat onboarding
  auto-applies known preferences silently and asks only missing categories — the
  "कायम ठेवा?" confirm steps no longer appear in chat. The profile-page path
  (`start_questionnaire`/`advance_questionnaire`) keeps the default confirm flow.
- **Search-early**: new `is_viable_search(filters, strategy)` + config
  `ONBOARDING_SEARCH_STRATEGY` (`gender_plus_core` default, `gender_only`, `full_only`).
  `_process_questionnaire` runs `handle_profile_search` once per session once the
  accumulated filters are viable and prepends the matches above the next question
  (persisted `questionnaire_searched` flag).
- **Zero-prior onboarding**: questionnaire auto-start (in `_process_questionnaire` and
  `_try_auto_link_matri`) only fires when the user has no prior conversations
  (`conv_repo.count_by_user`); known values no longer block auto-start — it asks the
  missing categories (`_questionnaire_start(prefs, missing_only=True)`).

### Tests
- `test_questionnaire.py`: `MissingOnlyBuildTests` + `ViableSearchTests`.
- `test_chat_questionnaire_flow.py`: search-early prepends matches, once-per-session,
  zero-prior skip; `test_reask_on_unparsed_answer` assertion fixed to "वयोगट".
- `test_matri_auto_link.py`: `test_pe_present_flow_starts_at_first_missing_category`
  (no confirm node; starts at marital status).

### Verification
- Backend suite: **379 passed / 1 known P9 failure**
  (`test_register_only_fetch`, .com vs .in — scheduled P9).

## 2026-08-02 — CF-2 rich profile load + Marathi summary

### Added
- **Rich register fetch** (`matri_service.py`): `REGISTER_PROFILE_COLUMNS`
  (personal profile columns + PE columns, all verified against the live DB via
  `INFORMATION_SCHEMA`); `_fetch_register_row` selects them.
- **Zero-LLM Marathi summary** (`matri_service.py`): `_PROFILE_LABELS_MR`
  (28 Marathi field labels), `_PE_LABELS_MR` (18 partner-preference labels),
  `_extract_profile_summary`, `_extract_pe_summary_mr`, and
  `format_user_profile_summary()` → "📋 **तुमचे प्रोफाइल:**" +
  "🎯 **तुमच्या जोडीदाराच्या पसंती:**" bullet lists; returns "" when empty.
- `fetch_partner_expectations` returns `profile` + `pe_summary_mr` (additive);
  the chat auto-link success reply (`_try_auto_link_matri`) now prepends the
  summary before `MATRI_ID_SUCCESS` / the questionnaire opener.
- **Tests**: `test_matri_service.py` (profile/PE-Marathi extraction +
  `format_user_profile_summary` + register-only-fetch asserts),
  `test_matri_auto_link.py` (link reply prepends summary).

### Verification
- PHOTO_BASE_URL discrepancy checked: `.env` pins `.in`; a real photo returns 200
  on BOTH `dishavadhuvar.com` (origin) and `dishavadhuvar.in` (CDN) — not a bug;
  the `.com` test assertion stays the known P9 failure.
- Backend suite: **370 passed / 1 known P9 failure**
  (`test_register_only_fetch`, .com vs .in — scheduled P9).
- Live smoke: `link_matri_id('ES92669')` renders the Marathi summary correctly.

## 2026-08-02 — CF-0 MyVivahAI identity + CF-1 identity gate

### Added
- **Identity/branding** (`config.py`, `.env.example`): `ASSISTANT_NAME="MyVivahAI"`,
  `PLATFORM_NAME="Dishavadhuvar"` under `# === Identity / Branding ===`.
- **Identity gate** (`config.py`, `.env.example`): `MATRI_ID_GATE_MODE` — `"soft"`
  (default: welcome + ask for the MatriID once, then guest browsing) or `"hard"`
  (block all service until a MatriID is linked).
- **`WELCOME_MESSAGE`** (exact user-approved copy) + `WELCOME_SUGGESTIONS` chip texts
  in `chat_service.py`.
- **`ChatService._apply_identity_gate`**: fires on the first message of a brand-new
  conversation (or every message in hard mode) for a user with no linked MatriID and a
  non-ID, non-greeting message; replies `WELCOME_MESSAGE`, persists `matri_id_prompted`
  in message `metadata_json`. ID-looking messages still fall through to auto-link.
- **Streaming `done` event** now carries `suggestions` when present in metadata
  (`_done_event`), mirroring the existing `questionnaire` payload.
- **Persona + Marathi-first prompts** (`prompts.py`, `llm_service.py`, `chat_service.py`):
  `BASE_SYSTEM_PROMPT`/`FORMAT`/`INTENT` (f-strings) rebranded; `_EXTRACTION_IDENTITY`
  prefix prepended to the plain-string `STRUCTURED_EXTRACTION_PROMPT` at the
  `extraction_service` call site; `format_db_notice` + `language_instruction` Marathi-first;
  `IDENTITY_RESPONSES` + `_is_identity_question()`; greeting shortcut extended; Marathi
  `GREETING_RESPONSES`/`MATRI_ID_PROMPT`.
- **Tests**: `tests/test_identity_gate.py` (6 unit + 2 stream); `MyVivahAIIdentityTests`
  in `test_chat_error_messages.py`.

### Verification
- Affected suites (identity gate + questionnaire flow + session e2e + auto-link):
  **49 passed**.
- Backend suite: **365 passed / 1 known P9 failure**
  (`test_register_only_fetch`, .com vs .in — scheduled P9).

## 2026-08-01 — P7 Backend hardening + frontend a11y/streaming watchdog

### Added
- **Rate limits** (`app/api/profile_routes.py`, `chat_routes.py`, `auth_routes.py`,
  `commercial_routes.py`, `commercial_admin_routes.py`): profile PATCH 20/m,
  matri/link 20/m, preference endpoints 20-60/m, conversations GET 60/m & PATCH/DELETE
  30/m, admin + commercial-admin 30/m, auth `/refresh` 10/m. (Pre-existing: login 10/m,
  register 5/m, chat 30/m.)
- **Schema validation** (`schemas/profile_schema.py`, `schemas/chat_schema.py`):
  name ≤100, profile_image ≤2048 + http(s)/data-image prefix, matri_id ≤15 alphanumeric,
  questionnaire answer/key/value caps, filters ≤100 entries, `ChatRequest.message` ≤
  `MAX_MESSAGE_LENGTH`, conversation title ≤200. Empty message still 400 (route-level,
  required by `test_acceptance.py`).
- **`RequestLoggingMiddleware`** (`app/main.py`): pure ASGI, SSE-safe; assigns
  `X-Request-ID` (echoes client header or UUID hex[:12]), logs method/path/status/
  duration, sets `scope["request_id"]`.
- **Frontend** (`hooks/useChat.js`): 120s streaming watchdog (`STREAM_TIMEOUT_MS`,
  `STREAM_TIMEOUT_MSG`; user-abort vs watchdog-abort distinguished via
  `watchdogAborted`). A11y: `Chat.jsx` aria-labels on icon buttons + `role="log"`/
  `aria-live`/`aria-busy`; `ChatMessage.jsx` `aria-hidden` decorative icons + label on
  delete/menu buttons; `Login.jsx` label/id + autoComplete + `role="alert"`;
  `ThinkingIndicator`/`TypingIndicator` `role="status"`; Sidebar menu `aria-expanded`.

### Verification
- Backend suite: **351 passed / 1 known P9 failure**
  (`test_register_only_fetch`, .com vs .in — scheduled P9).
- Frontend `npm run build` succeeds.

## 2026-08-02 — Conversation Flow "Consultant" track (CF-0..CF-7) documented

### Added
- `.agents/modules/conversation-consultant-context.md` (plan + decisions + exact
  MyVivahAI `WELCOME_MESSAGE` copy).
- CF phase table in `PHASES.md`; CF decisions in `DECISIONS.md`; CF tasks + P7
  completion in `TODO.md`; pre-coding entry in `WORK_LOG.md`.
- Decisions: MyVivahAI identity (parametric `ASSISTANT_NAME`/`PLATFORM_NAME`),
  Marathi-first ALL replies, MatriID gate soft-default/hard-behind-config, known prefs
  auto-apply, search-early `ONBOARDING_SEARCH_STRATEGY` default `gender_plus_core`,
  onboarding only with zero prior conversations, chat-embedded biodata. User requested
  `.agents/` updates explicitly (reverses earlier constraint).

## 2026-07-31 — Migrated matrimony DB to Disha Vadhuvar (dishavadhuvar.com)

### Changed
- **DB credentials** — `backend/.env` and `config.py` defaults now point at the new
  matrimony database `82.197.82.66` / `u583780661_dishavadhuvar` (was
  `82.25.121.160` / `u320743426_mvv`). Old credentials fully removed. Password remains
  `.env`-only (never committed).
- **`PHOTO_BASE_URL`** → `https://dishavadhuvar.com/gallary/` (verified against a live photo).
- **`schema_discovery.LOOKUP_TABLES`** — corrected column labels for the new DB:
  `education→edu`, `occupation→occu`, `mother_tounge→mother_tounge`,
  `maritial_status→status`. The old labels (`Education`, `Occupation`, `MotherTongue`,
  `Maritalstatus`) do not exist as columns in those lookup tables, so those schema
  lookups previously returned nothing.
- **`ALLOWED_SQL_TABLES`** — replaced the old `agents/agent_*` list (tables no longer
  present) with tables that exist: `register,siteconfig,cms,successstory,testimonial,
  banners,news,seo,packages,activity`.

### Optimized
- `schema_discovery._sync_fetch_all()` now loads all 142 tables' columns in a single
  `INFORMATION_SCHEMA.COLUMNS` query instead of one query per table. Startup schema
  refresh dropped from ~60 s to ~16 s against the slower remote host.

### Fixed
- `query_builder.SEARCH_SSL` now selects `MatriID` (was missing, so profile-search rows
  carried no MatriID and detail lookups by MatriID could not resolve).
- `matri_service` member `photo_url` now prepends `PHOTO_BASE_URL` (was a bare filename).

### Files
- Modified: `backend/.env`, `backend/.env.example`, `backend/app/config.py`,
  `backend/app/services/schema_discovery.py`, `backend/app/services/query_builder.py`,
  `backend/app/services/matri_service.py`,
  `backend/tests/test_matri_service.py`, `.agents/WORK_LOG.md`

### Verification
- Live-verified against the new DB: connection, schema refresh, profile search, profile
  detail, and MatriID link with PE filters (`ES92669`).
- Backend suite: 210 passed (unchanged), `--ignore=tests/test_acceptance.py`.
- Branding intentionally left as "myvivahai" (per user). Vector search NOT re-indexed
  (old index still holds old-DB profiles) — MySQL searches work without it.

## 2026-07-31 — Profile Edit + MatriID Linking + Cost-Effective Preference Questionnaire

Plan: `.agents/PHASES.md`. Contract: `.agents/modules/profile-preferences-context.md`.

### Added
- **Edit Profile** — PATCH `/api/profile` (name, profile_image); frontend `/app/profile`
  page with profile form, MatriID link, questionnaire wizard and saved-preference review.
- **MatriID linking** — POST `/api/profile/matri/link` validates the ID, reads the member's
  `PE_*` partner-expectation columns from the read-only matrimony MySQL DB and gap-fills
  from the member's latest saved search (`advance_saveandsearch` → `basic_saveandsearch`).
  `User` stores `matri_id`, `matri_name`, `matri_synced_at`.
- **Rule-based questionnaire (zero LLM)** — `app/core/questionnaire.py` builds a confirm /
  single / custom-text decision tree over `BUILD_ORDER`; known PE values are pre-filled and
  confirmed with Keep / Change / Skip. Completion persists `user_preferences` (SQLite) and
  the values auto-apply as default profile-search filters in chat (Phase 4 merge), reducing
  LLM extraction calls.
- **Tests** — `backend/tests/test_matri_service.py`, `backend/tests/test_questionnaire.py`
  (36 tests). Suite: **210 passed** (174 prior + 36 new).

### Fixed
- **Custom text answers never saved** — `apply_answers` in `questionnaire.py` bailed on the
  `option_id == "custom"` block via `if option is None: continue`, so typed caste/education/
  occupation/city answers were dropped. Restructured so the custom branch runs first.
- **Questionnaire infinite loop** — `current_node` now advances past answered custom-text
  nodes (`seq + 1; continue`).
- **Member photo always empty** — `matri_service.py` read `PhotoURL`, which does not exist
  in `register` (verified via INFORMATION_SCHEMA); now reads `Photo1`.

### Files
- New: `backend/app/repositories/preference_repository.py`,
  `backend/app/models/user_preference_model.py`, `backend/app/core/questionnaire.py`,
  `backend/app/schemas/profile_schema.py`, `backend/app/api/profile_routes.py`,
  `backend/tests/test_matri_service.py`, `backend/tests/test_questionnaire.py`,
  `frontend/src/services/profileService.js`, `frontend/src/pages/Profile.jsx`
- Modified: `backend/app/models/user_model.py`, `models/__init__.py`, `database.py`,
  `schemas/auth_schema.py`, `services/matri_service.py`, `services/chat_service.py`,
  `services/db_query_service.py`, `main.py`, `frontend/src/app/router.jsx`,
  `frontend/src/components/ui/Sidebar.jsx`, `.agents/TODO.md`, `.agents/WORK_LOG.md`

### Verification
- Backend: `pytest tests -q --ignore=tests/test_acceptance.py` → 210 passed.
- Frontend: `npm run build` → Vite production build passed (Profile chunk emitted).
- MatriID linking verified against the live matrimony DB (WP88076, WP37886, error paths).

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
174 tests pass under `unittest discover` (164 pre-existing + 10 new), or 175 under
`pytest`, which additionally collects the bare `def test_acceptance()` function that
`unittest` skips. Each new test was confirmed to fail when its fix is reverted.
`pyflakes` reports no undefined names.

Note: that extra pytest-only test is a live deployment smoke script that swallows its
own failures and `return`s instead of asserting, so it passes even with no server
running. Logged in `ISSUES.md`; pre-existing on `main`, not addressed here.

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

## 2026-07-31 — Fixed MatriID never persisting + questionnaire falling through to the LLM

### Root cause
- \get_current_user\ resolved its DB session via \Depends(get_db_session)\ while endpoints used
  \Depends(get_db)\ — two different dependency callables, so FastAPI created **two separate
  SQLAlchemy sessions per request**. Mutations set on the auth-loaded \user\ object (e.g.
  \user.matri_id\) were flushed/committed against the *other* session and silently lost.
- On top of that, FastAPI tears down \yield\ dependencies **before a StreamingResponse
  generator runs**, so even with one session the \user\ object reached
  \stream_process_message\ detached from any session; the fix below would still not persist.
  Consequence: \users.matri_id\ stayed NULL forever, so every request the user appeared
  unlinked (chat kept asking for the ID) and questionnaire answers like \कायम ठेवा\ fell
  through to the LLM router ("TF-IDF Local Router classified: 'कायम ठेवा' -> 'database'").

### Changed
- \pp/dependencies.py\ — \get_db = get_db_session\ (single dependency callable) so the
  auth-loaded \user\ and the endpoint's \db\ share one session per request.
- \pp/services/chat_service.py\ — new \ChatService._attach_user(user)\ merges the (possibly
  detached) authenticated \user\ back into \self.db\'s session at the top of both
  \stream_process_message\ and \process_message\, so mutations like \user.matri_id\ are
  tracked and committed.

### Tests
- \	ests/test_session_persistence.py\ (new): asserts \get_db is get_db_session\, that
  \link_matri_id_to_user\ persists matri_id on a shared session, and that a questionnaire
  session survives a "second request" (user re-fetched from DB).
- \	ests/test_session_unification_e2e.py\ (new): drives the real FastAPI app with an in-memory
  DB — register → stream a bare MatriID → \/api/auth/me\ shows \matri_id\ → answering
  \कायम ठेवा\ in the same conversation (and after a simulated page reload) replies with the
  next questionnaire question and never calls the LLM.
- Full backend suite: **307 passed**.
