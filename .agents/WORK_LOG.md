# Work Log

## 2026-08-02 — P10 offline AI-eval harness + P11 deployment runbook

- P10: added `tests/eval_harness.py` — an offline, pytest-invisible rubric harness
  (not collected: no `test_`-prefixed functions). Scores 10 scenarios through the real
  `ChatService.stream_process_message` with mocked DB/LLM boundaries:
  guest welcome gate, branded Marathi greeting, identity persona (never "chatbot"),
  resume-search route (Marathi photo cards, no LLM, topic chips), no-match honesty
  (no fabricated profiles + सल्ला), first-candidate biodata (zero-LLM sectioned),
  section-chip drill, welcome-back prefix, LLM-extraction Marathi search, comparison
  route. Rubric: marathi_first / no_hallucination / routing / deterministic /
  suggestions / identity. Run: `python -m tests.eval_harness` → **10/10 pass**.
  (Two scenario bugs were harness-setup issues, not product bugs: identity phrase is
  "तुम्ही कोण आहात", and gender must live in accumulated filters not default_filters
  or the questionnaire auto-start hijacks the chip.)
- P11: wrote `.agents/modules/deployment-runbook.md` — Hostinger KVM2 deploy steps:
  preflight, `.env` reference (CF vars incl. PHOTO_BASE_URL `.in`, gate soft,
  `gender_plus_core`), Qdrant install, schema boot + `reindex_profiles.py`, KVM2 2GB
  bge-m3 memory plan (VECTOR_FALLBACK toggle / KVM4), uvicorn systemd unit, nginx SSE
  config, `python -m tests.test_acceptance` + `tests.eval_harness` verification, manual
  smoke checklist, rollback, post-deploy checklist, open constraints.
- Live P11 execution (server access + secrets) remains with the user.

## 2026-08-02 — P11 prep: acceptance smoke script no longer false-passes

- `tests/test_acceptance.py` rewritten (ISSUES.md open item): the function is now
  `run_acceptance()` (no `test_` prefix) so pytest collects **0** tests from the file —
  the `--ignore=tests/test_acceptance.py` flag is no longer needed. Every check uses a
  real `_assert` that raises on failure; `__main__` exits non-zero on any failure. It
  stays a manual deployment smoke script: `python -m tests.test_acceptance` against a
  running server.
- Full suite: `python -m pytest tests -q` → **430 passed / 0 failed** (no ignore flag).

## 2026-08-02 — P8 more tests + P9 known-failure fix (suite now fully green)

- P8: added `tests/test_db_query_formatting.py` (15 tests) for the deterministic
  zero-LLM helpers the CF-5/CF-6 routes rely on but which had no direct coverage:
  `add_photo_url` (config-base URL, leading-slash strip, nophoto.jpg → "", missing → ""),
  matri `_photo_url`, `format_filter_summary` (age range, मुलगी/मुलगा, Marathi labels,
  manglik/complexion mappings, empty), `format_no_matches_notice` (filter summary + सल्ला),
  `format_profile_results_markdown` (context header, numbered photo cards, no-photo dash line).
- P9: fixed the long-standing known failure `test_matri_service.py::
  FetchPartnerExpectationsTests::test_register_only_fetch` — it hardcoded
  `https://dishavadhuvar.com/...` while config default + `.env` both pin
  `https://dishavadhuvar.in/gallary/` (hcdn CDN; both domains verified serving). Assertion
  now derives the expected URL from `settings.PHOTO_BASE_URL`, so it can't drift again.
- Full suite: **430 passed / 0 failed** (was 414 + 1 known P9). Frontend `npm run build`
  succeeds. P10 (AI eval) and P11 (KVM2 deploy) remain — both need live infra/credentials.

## 2026-08-02 — CF-7: verification + first-candidate detail route bug fix

- Verified the per-phase test files named in the CF-7 plan are already up to date:
  `test_matri_auto_link.py` (link reply = profile + PE summary + missing-only onboarding,
  not `MATRI_ID_SUCCESS`/confirm-node), `test_chat_questionnaire_flow.py` (missing-only
  auto-start, search-early once per session, zero-prior onboarding gate),
  `test_session_unification_e2e.py` (2 tests green via TestClient).
- Strengthened `test_suggestions.py::test_first_candidate_detail_route_resolves_from_candidates`:
  it now patches `stream_format_db_result` to raise (proving CF-6 zero-LLM biodata), asserts
  the reply contains the sectioned biodata (header + "शिक्षण व करिअर") and that the done
  event carries `BIODATA_SECTION_CHIPS`.
- **This caught a real bug**: the "आधी पाहिलेले प्रोफाइल पुन्हा पाहा" route used
  `selected_index: 0`, but `resolve_contextual_profile` is 1-based (`int(x) - 1`), so the
  index never matched and the branch fell back to the "तुम्हाला कोणत्या प्रोफाइलची माहिती
  हवी आहे?" prompt. The old test missed it because it only asserted `done["type"] == "done"`.
  Fixed the route to `selected_index: 1` (first candidate; falls back to `current_selected`
  from memory when no candidates).
- Full suite: 414 passed / 1 known P9; frontend build succeeds. Consultant track CF-0..CF-7 ✅.

## 2026-08-02 — CF-6: chat-embedded rich biodata + section chips

- `matri_service.py`:
  - `_BIODATA_EXTRA_LABELS_MR` (EducationDetails, Star, Moonsign, Complexion, BloodGroup,
    Bodytype, Fathersoccupation, Mothersoccupation, noofbrothers, noofsisters, Interests)
    merged into `_BIODATA_LABELS_MR`.
  - `BIODATA_SECTIONS` — 8 sections (basic 👤, education 📚, family 👨‍👩‍👧‍👦, physical 🏋️,
    lifestyle 🌿, horoscope 🔮, partner 🎯, location 📍), each `key`/`emoji`/`title`/`fields`.
  - `BIODATA_SECTION_ROUTES` (chip `"{emoji} {title}"` → section key) + `BIODATA_SECTION_CHIPS`.
  - `_format_biodata_section` (bullets, `_clean`-empty values skipped, `_BIODATA_LABELS_MR`
    fallback to `_PE_LABELS_MR`), `format_profile_section(row, key)` (None when empty),
    `format_profile_biodata(row)` (header + `_photo_url` + non-empty sections) — zero LLM.
- `chat_service.py`:
  - `SUGGESTION_ROUTES` gains every biodata chip → `{"intent": "profile_detail",
    "fields": ["all"], "biodata_section": key, "selected_index/reference": None,
    "deterministic": True}`.
  - Route-built `extracted` carries `biodata_section`.
  - profile_detail branch: `fields in (None, ["all"])` no longer asks the category question
    (`_DETAIL_CATEGORY_QUESTION` constant removed) — fetches the full row once (cached on
    MatriID match) and renders `format_profile_biodata`; a `biodata_section` renders
    `format_profile_section` (falls back to "या प्रोफाइलसाठी ही माहिती उपलब्ध नाही.").
    Full/section replies carry `BIODATA_SECTION_CHIPS` suggestions.
- Tests: `test_biodata.py` (9 tests) — formatter units, chips↔routes coverage, and two
  stream tests (full biodata deterministic + section chip skips LLM entirely).
- Suite 414 passed / 1 known P9; frontend build succeeds.

## 2026-08-02 — CF-5: deterministic suggestions engine + SUGGESTION_ROUTES + frontend chips

- `chat_service.py`:
  - `build_suggestions(context)` — deterministic Marathi follow-up chips, no LLM:
    no MatriID → `WELCOME_SUGGESTIONS`; `questionnaire_done` →
    `QUESTIONNAIRE_DONE_SUGGESTIONS`; known `last_topic` → `WELCOME_BACK_SUGGESTIONS`;
    else `GENERIC_WELCOME_BACK_SUGGESTIONS`. Injected into every `done` event when the
    reply doesn't already carry chips (gate/welcome-back keep theirs).
  - `SUGGESTION_ROUTES` — exact-phrase chip routing that bypasses `extract_search_params`
    entirely (no LLM): resume/new/next-search (deterministic profile_search from memory
    filters, `reset_filters` clears accumulated), comparison, and first-candidate
    profile_detail. Questionnaire-topic chip set now fully routed.
  - `WELCOME_BACK_SUGGESTIONS["questionnaire"]` replaced the unrouted
    "माझ्या जोडीदाराच्या पसंती बदला" with "मागील सर्च चालू ठेवा" so every chip routes.
- `db_query_service.py`: unchanged this phase (routing consumes existing paths).
- Frontend:
  - `useChat.js`: captures `doneEvent.suggestions` onto the assistant message and reads
    `meta.suggestions` when loading history (chips persist across reloads).
  - `ChatMessage.jsx`: renders `message.suggestions` chips (same pill styling as
    questionnaire options) calling `onSend(text)`.
  - `EmptyState.jsx`: suggestions now dynamic — `SUGGESTIONS_NO_ID` (MatriID-first) vs
    `SUGGESTIONS_LINKED` (preference-first) based on `needsMatriId`.
- Tests: new `tests/test_suggestions.py` (10 tests) — `build_suggestions` matrix,
  every chip in the actionable sets has a route, and three stream tests proving the
  route skips LLM extraction (resume search, new-search resets filters, first-candidate
  detail). Updated `test_conversation_memory.py::test_first_ever_user_gets_no_prefix`
  (CF-5 now injects generic chips on every reply).
- Verification: CF suites 123 passed / 1 known P9; full suite → **405 passed / 1 known P9**;
  frontend `npm run build` succeeds.
- Next: CF-6 (chat-embedded rich biodata + follow-up chips via `resolve_contextual_profile`).

## 2026-08-02 — CF-4: conversation memory + "परत स्वागत!" welcome-back + contextual chips

- `chat_service.py`:
  - `_enrich_memory(metadata, intent_label)` annotates assistant metadata with
    explicit memory fields — `last_topic` (from intent), `viewed_profiles`
    (derived from `profile_candidates`), `compared_pairs` (from `compared_pair`),
    `last_filters` (copy of `accumulated_filters`). Never overwrites existing keys.
  - `_load_history` now restores those fields plus the previously-unrestored
    `questionnaire_searched` flag — fixing a latent CF-3 issue where search-early
    could repeat across turns in the same conversation.
  - `_welcome_back(user, user_id, conversation_id)` returns a Marathi
    "परत स्वागत, {name}! 🙏" prefix + topic-aware chips for a LINKED user starting
    a brand-new conversation when they already have prior conversations
    (`count_by_user > 1` with the current conversation counted). Guests, continuing
    conversations, and first-ever chats get None. `_last_topic_across_conversations`
    scans the user's newest conversations for the latest `last_topic` in metadata.
  - Welcome-back prefix streamed as the first token; suggestions merged into the
    assistant metadata + `done` event; the main flow's `done` event now goes through
    `_done_event` so metadata (suggestions etc.) actually reaches the client.
  - Questionnaire-flow metadata also enriched via `_enrich_memory(..., "questionnaire")`.
- `db_query_service.py`: `handle_profile_comparison` success metadata now carries
  `compared_pair` ([{MatriID,Name}, {MatriID,Name}]) so the memory layer can persist it.
- New `WELCOME_BACK_SUGGESTIONS` per topic (profile_search/profile_detail/comparison/
  questionnaire) + `GENERIC_WELCOME_BACK_SUGGESTIONS` fallback.
- Tests: new `tests/test_conversation_memory.py` (16 tests) — `_enrich_memory`
  derivation/no-overwrite, `_load_history` restore (incl. `questionnaire_searched`),
  `_welcome_back` guards + topic/generic chips + AsyncMock tolerance, `_last_topic_
  across_conversations` newest-first scan, and two stream tests (returning user
  streams prefix + done suggestions + persisted memory; first-ever user gets neither).
- Verification: CF suites 161 passed / 1 known P9; full suite → **395 passed / 1 known
  P9** (`test_register_only_fetch`).
- Next: CF-5 (deterministic suggestions engine + click routing + frontend chips +
  dynamic `EmptyState.jsx`).

## 2026-08-02 — CF-3: missing-only questionnaire + search-early + zero-prior onboarding

- `core/questionnaire.py`:
  - `build_nodes(pe_filters, missing_only=True)`: chat onboarding auto-applies known
    preferences silently and asks only missing categories — no more "कायम ठेवा?"
    confirm nodes in chat (profile-page path `start_questionnaire`/
    `advance_questionnaire` still use `missing_only=False`).
  - New `is_viable_search(filters, strategy)` for the `ONBOARDING_SEARCH_STRATEGY`
    strategies (`gender_plus_core` default / `gender_only` / `full_only`).
- `config.py` + `.env.example`: `ONBOARDING_SEARCH_STRATEGY=gender_plus_core`.
- `chat_service.py`:
  - `_questionnaire_start(..., missing_only=True)`; `_try_auto_link_matri` uses it and
    skips the questionnaire start when the user already has prior conversations
    (`conv_repo.count_by_user`; `isinstance(int)` guard tolerates AsyncMock in unit tests).
  - `_process_questionnaire` builds nodes with `missing_only=True`; auto-start gated on
    zero prior conversations (`conversation_id is None` + `count_by_user <= 1`) and now
    fires whenever there are missing categories (not just when prefs = gender only).
  - Search-early: after each valid answer, when `is_viable_search` passes for the
    configured strategy, run `handle_profile_search` once per session and prepend the
    matches above the next question; persisted `questionnaire_searched` flag prevents
    repeats; completion still does the final full-filter search.
- Tests: `MissingOnlyBuildTests` + `ViableSearchTests` (test_questionnaire.py),
  search-early prepends/once-per-session + zero-prior-skip (test_chat_questionnaire_flow.py),
  updated `test_pe_present_flow_starts_at_first_missing_category` (test_matri_auto_link.py),
  fixed stale `test_reask_on_unparsed_answer` assertion ("वयोगट" not "वैवाहिक" — the first
  missing question for gender-only PE is age_range).
- Verification: affected suites 99 passed / 1 known P9; full suite → **379 passed / 1 known
  P9** (`test_register_only_fetch`). Config loads: MyVivahAI soft gender_plus_core.
- Next: CF-4 (conversation memory + "परत स्वागत!" welcome-back + contextual chips).

## 2026-08-02 — CF-2: rich profile load + zero-LLM Marathi summary

- **PHOTO_BASE_URL discrepancy resolved (verified)**: `.env` pins
  `https://dishavadhuvar.in/gallary/`; probed a real photo
  (`2023_07_11_01_31_0431.jpg`) on both domains — **both return 200** (`.com` =
  LiteSpeed origin, `.in` = hcdn CDN). Not a bug; the known P9 test failure
  (`test_register_only_fetch` asserting `.com`) stays scheduled for P9.
- Added `REGISTER_PROFILE_COLUMNS` in `matri_service.py` (rich profile cols +
  PE cols, deduped) — verified every column exists in the live register table via
  `INFORMATION_SCHEMA`. `_fetch_register_row` now selects them.
- Added zero-LLM Marathi summary: `_PROFILE_LABELS_MR` (28 fields),
  `_PE_LABELS_MR` (18 partner-preference labels), `_extract_profile_summary`,
  `_extract_pe_summary_mr`, and `format_user_profile_summary()` → "📋 तुमचे
  प्रोफाइल:" + "🎯 तुमच्या जोडीदाराच्या पसंती:" bullet lists; returns "" when
  nothing meaningful.
- `fetch_partner_expectations` now returns `profile` + `pe_summary_mr` (additive);
  auto-link success reply in `_try_auto_link_matri` prepends the summary before
  `MATRI_ID_SUCCESS` or the questionnaire opener.
- Tests: `test_matri_service.py` (+4 unit, +2 asserts in register-only fetch),
  `test_matri_auto_link.py` (+1 reply-prepends-summary).
- Verification: affected suites 68 passed / 1 known P9; full suite
  `pytest tests -q --ignore=tests/test_acceptance.py` → **370 passed / 1 known P9**.
  Live smoke: `link_matri_id('ES92669')` → Satish Gaikwad Inamdar summary renders.
- Next: CF-3 (missing-only questionnaire + search-early + zero-prior-onboarding).

## 2026-08-02 — CF-0 + CF-1 implemented and verified

- **CF-0 (MyVivahAI identity + Marathi-first)**: added `ASSISTANT_NAME`/`PLATFORM_NAME`
  to `config.py` + `.env.example`; rewrote `BASE_SYSTEM_PROMPT` (now an f-string, identity +
  Marathi-first LANGUAGE RULES + new examples), `FORMAT_SYSTEM_PROMPT`, `INTENT_SYSTEM_PROMPT`,
  `llm_service.format_db_notice` and both `language_instruction` strings; added
  `_EXTRACTION_IDENTITY` prefix prepended to `STRUCTURED_EXTRACTION_PROMPT` at the
  `extraction_service` Tier-3 call site (kept the extraction prompt a plain string — f-string
  broke on its JSON braces with `ValueError: Invalid format specifier`); added exact
  `WELCOME_MESSAGE`, `IDENTITY_RESPONSES` + `_is_identity_question()`, rebranded
  `GREETING_RESPONSES`/`MATRI_ID_PROMPT`; greeting shortcut now also answers persona
  questions; added `MyVivahAIIdentityTests`; updated greeting-copy assertions.
- **CF-1 (Identity gate)**: `MATRI_ID_GATE_MODE` (soft/hard) in `config.py` + `.env.example`;
  new `_apply_identity_gate` in `chat_service.py` — soft: first message of a brand-new
  conversation with no linked MatriID and a non-ID, non-greeting message → `WELCOME_MESSAGE`
  + `WELCOME_SUGGESTIONS` chips, persisting `matri_id_prompted` metadata (guest browsing
  proceeds after); hard: every message blocked until linked; ID-looking messages always fall
  through to auto-link. `_done_event` now also carries `suggestions` when present. New
  `tests/test_identity_gate.py` (6 unit + 2 stream). Gate inserted in
  `stream_process_message` between auto-link and normal processing; reuses `_persist_matri_reply`.
- Verification: affected suites green (identity gate + questionnaire + e2e + auto-link: 49
  passed); full backend suite `pytest tests -q --ignore=tests/test_acceptance.py` →
  **365 passed / 1 known P9 failure** (`test_register_only_fetch`, .com vs .in).
- Note: console `print` of emoji fails on cp1252 (`UnicodeEncodeError`) — not a code bug;
  `python -X utf8` prints fine.
- Next: CF-2 (rich profile load + zero-LLM Marathi summary).

## 2026-08-02 — CF track planned; `.agents/` updated (pre-coding)

- User approved the "Conversation Flow Enhancement — Consultant" track (CF-0..CF-7)
  and explicitly asked to update the `.agents/` folder first so everything is
  remembered ("update agents folder according so will remmber all the things and
  start step by step") — reversing the earlier "forget about agents folder" note.
- Confirmed decisions (also in `DECISIONS.md`): MyVivahAI identity (parametric via
  `ASSISTANT_NAME`/`PLATFORM_NAME`), Marathi-first for ALL replies, MatriID gate
  soft-default with hard behind `MATRI_ID_GATE_MODE`, known prefs auto-apply
  (never re-ask), search-early via `ONBOARDING_SEARCH_STRATEGY` (default
  `gender_plus_core`), onboarding only when zero prior conversations, chat-embedded
  rich biodata.
- Created `.agents/modules/conversation-consultant-context.md`; added the CF phase
  table to `PHASES.md`, decisions to `DECISIONS.md`, CF tasks + P7 completion to
  `TODO.md`. `CHANGELOG.md` pending entry for P7.
- Noted a PHOTO_BASE_URL discrepancy: `CHANGELOG.md` records
  `https://dishavadhuvar.com/gallary/` while `config.py:97` shows `.in` — verify
  before CF-2.
- Next: CF-0 (identity + Marathi-first), then CF-1..CF-7.

## 2026-07-31 — Root-cause fix: MatriID never persisted, questionnaire hit the LLM

- Live diagnosis: after "MatriID linked: DI80369", a chat answer "कायम ठेवा" was classified by
  the TF-IDF router as 'database' (LLM path). The DB showed `users.matri_id = NULL` for every
  user even though prefs/messages saved fine — so the ID never persisted and the chat kept
  re-asking for it, and on the next request `user.matri_id` was falsy so `_process_questionnaire`
  skipped (fell through to the LLM router).
- Two-layer root cause:
  1. `get_current_user` used `Depends(get_db_session)`; endpoints used `Depends(get_db)` — two
     different callables → two sessions per request → user-object mutations committed nowhere.
  2. FastAPI tears down `yield` deps before a StreamingResponse generator runs, so the `user`
     arrives detached even with a single session.
- Fixes: `get_db = get_db_session` in `app/dependencies.py` (one session per request) +
  `ChatService._attach_user` (merges the user back into `self.db` at the top of
  `stream_process_message`/`process_message`) so `user.matri_id` mutations are tracked/committed.
- Backfilled the existing dev user (id=3) with `matri_id=DI80369` so no re-link is needed.
- New tests: `tests/test_session_persistence.py` (3) + `tests/test_session_unification_e2e.py`
  (real FastAPI app + in-memory DB; proves `/api/auth/me` returns matri_id after auto-link and
  that "कायम ठेवा" is answered by the questionnaire with zero LLM calls). Backend: **307 passed**;
  dev server (uvicorn --reload) auto-restarted with the fix.

## 2026-07-31 — Rule-based fast path + clickable questionnaire chips

- `extraction_service.rule_based_extract(message)`: deterministic, zero-LLM extraction for
  clear profile queries. Handles gender keywords (Devanagari/English female/male), cities via
  `_CITY_MR_EN` + `_MR_CITY_SUFFIX` suffix matching resolved against the DB
  (`_resolve_against_db` prefers exact then shortest substring match — fixes "maratha"
  resolving to "Kokanastha Maratha"), Devanagari/English religion/caste words, `N ते M वर्ष`
  age ranges, and counts like `N मुली`/`N profiles` (capped at 50). Intercepts only when
  filters/limit are present OR (profile word + search verb + Devanagari); greetings and detail
  queries return None; vague English / bare "दाखवा" fall through to the LLM.
- Wired as extraction Tier 1.5 in `extract_search_params` → `answer_database_question_hybrid`
  → `_handle_profile_search(deterministic=True)` which formats via
  `format_profile_results_markdown` (photo cards: `![Name](PhotoURL) Age, Gender, City, …`) with
  the Marathi no-match/too-many notices. This is what makes "पुण्यातील 5 मुलींची प्रोफाइल दाखवा"
  answer instantly instead of the ~121s LLM format pass. Questionnaire auto-start now skips when
  the rule extractor yields a concrete profile answer; questionnaire completion always runs the
  deterministic branch.
- Clickable questionnaire option chips: `_questionnaire_start`/`_process_questionnaire` persist
  `questionnaire_options` + `questionnaire_progress {"current","total"}` in assistant-message
  `metadata_json` (start/reask/advance). Streaming `done` event gains `questionnaire
  {options, progress}` via `_done_event`. `get_conversation` messages now carry `metadata`
  (via new `_safe_metadata`, `history_routes` `response_model=dict`). Frontend `useChat.js`
  attaches `questionnaire` from load metadata and merges the done-event payload; `ChatMessage.jsx`
  renders clickable Marathi option pills (`bg-primary-500/10`, hover/active, disabled while
  streaming) that call the same `onSend` path.
- Tests: new `tests/test_rule_based_extract.py` (10) covering "पुण्यातील 5 मुलींची प्रोफाइल
  दाखवा"; `test_chat_questionnaire_flow.py` grew streaming tests (token→done ordering, done
  `questionnaire.options`, no-options on completion, auto-link done carrying questionnaire) and
  two metadata tests. Backend suite: **302 passed**. Frontend `npm run build` passes.

## 2026-07-31 — Professional chat UI polish (`/app/chat`)

- Rewrote `ChatMessage.jsx`: user/assistant/error/streaming bubble variants with `Avatar`
  (gradient user initial vs bot badge), asymmetric rounded corners, per-bubble timestamps
  (`formatTime` via `en-IN` locale), Marathi retry link on errors, "फोटो नाही" photo
  placeholder, `max-w-[520px]` bubbles.
- Rewrote `EmptyState.jsx`: blurred primary glow hero + gradient bot badge, Marathi headline
  ("नमस्कार, आपले स्वागत आहे!" vs "तुम्ही काय शोधत आहात?"), uppercase MatriID input with
  inset search icon + "शोधा" button, pink partner-preferences banner linking `/app/profile`,
  and four Marathi suggestion chips. Prop renamed `onEnterId` → `onSend` (ID form + chips now
  share one message-send path).
- Rewrote `Chat.jsx` shell: sticky glass header (brand title + online status, New Chat button,
  user avatar/name + MatriID state), radial-gradient conversation backdrop, professional
  composer (auto-resizing textarea, Enter/Shift+Enter hint, gradient send button, streaming
  stop button, disabled-while-streaming states). Fixed EmptyState to receive `onSend={send}`
  (the old `onEnterId` prop would have broken ID submission after the rewrite).
- `ThinkingIndicator.jsx` streaming step labels translated to Marathi.
- Validation: `npm run build` passes (2,575 modules). Dev server already running on
  `http://localhost:5173` (PID 27116), so HMR picked the changes up live.

## 2026-07-31 — Guided conversational questionnaire wired into chat

- Auto-link success now starts the guided questionnaire flow in-chat (zero LLM):
  - PE empty (only gender) → Marathi by-name success + first fresh question (age range).
  - PE present → by-name success + confirm/keep/change/skip node for the first saved value.
  - `_try_auto_link_matri` builds the opener via new `_questionnaire_start(pe_filters)` and
    persists it with `metadata_json`; partner gender is never asked (guarded by requiring
    `pe_filters.gender` before a flow may start).
- `ChatService._process_questionnaire(...)` drives the session in both `stream_process_message`
  and `process_message`:
  - Active session (`questionnaire_answers` + `questionnaire_pe_filters` in assistant-message
    `metadata_json`, loaded by `_load_history`) parses each chat answer with
    `questionnaire_chat.parse_answer` (numbered options, Devanagari digits, Marathi/Hinglish
    synonyms, custom text, "any") and replies with the next question; unparseable answers get a
    Marathi re-ask.
  - Fresh chat + linked MatriID + no meaningful saved prefs (nothing beyond gender) →
    auto-start from the first question again.
  - Flow end: saves the final filters via `PreferenceRepository.replace_all(source="questionnaire")`,
    runs `_handle_profile_search`, and replies with a Marathi by-name confirmation plus the
    matches. `questionnaire_done` flag prevents re-entry.
- Session state lives only in `metadata_json` (no schema change); `questionnaire_chat.py`
  `format_question` now shows `प्रश्न N/M` progress.
- Remaining English fallback notices in `db_query_service.py` translated to Marathi
  (no-match, too-many-results, "Profile not found", unavailable-info, detail-category question,
  multiple-match clarification); same clarification translated in `chat_service.py`.
- Frontend `useChat.js`: invalidates the `['me']` query on stream done when the store user lacks
  `matri_id`, so the chat page stops re-asking for an ID right after linking.
- Tests: new `tests/test_questionnaire_chat.py` (37), `tests/test_chat_questionnaire_flow.py` (11),
  `tests/test_db_query_service.py` (7); `test_questionnaire.py` updated for gender-skip
  (`age_range_confirm` first, gender auto-applied); `test_matri_auto_link.py` gained two flow-start
  tests. Backend suite: **286 passed**. Frontend `npm run build` passes.

## 2026-07-31 — Marathi/Hinglish chat-first MatriID onboarding

- Chat now asks for the user's MatriID in Marathi when it opens with no ID linked: the empty
  chat screen renders a Marathi assistant bubble ("तुमचा matrimony ID शेअर करा…") plus a
  MatriID input in `EmptyState` ("Perfect Partner शोधा"). Submitting the ID sends it as a
  normal chat message — no page redirect.
- Backend auto-link: `ChatService` (`stream_process_message` / `process_message`) now takes
  the authenticated `user`; when `user.matri_id` is empty and the message is a bare ID token
  (e.g. `ES92669`) or contains an id/matri/आयडी hint (`_extract_matri_id`), it links the ID
  via the new shared `matri_service.link_matri_id_to_user(db, user, matri_id)` helper and
  replies conversationally in Marathi (success / not-found / DB-error variants).
- `profile_routes.POST /api/profile/matri/link` refactored to reuse the same helper.
- Marathi/Minglish translations: greetings, the ID prompt, `_DETAIL_CATEGORY_QUESTION`,
  inline notices, `user_facing_error`, the full questionnaire (`core/questionnaire.py`:
  questions, options, confirm keep/change/skip, `known_value` text), `EmptyState`, `Chat`
  input placeholder, `Profile.jsx` labels, and `Landing` example chips. Filter values,
  `option_id`, `text_key` and the greeting keys are unchanged (LLM extraction + tests intact).
- Tests: new `tests/test_matri_auto_link.py` (18 tests) covering `_extract_matri_id` and the
  auto-link success/not-found/error/already-linked/existing-conversation paths; updated
  `test_questionnaire.py` (`known_value` → "Female जोडीदार", Marathi validation error) and
  `test_chat_error_messages.py` (Marathi `user_facing_error` assertions). Backend suite:
  **228 passed**. Frontend `npm run build` passes.
- Fixed a dead link: EmptyState's partner-preferences card now goes to `/app/profile`
  (the old `/app/partner-preferences` route never existed).

## 2026-07-31 — Migrated matrimony DB to Disha Vadhuvar (dishavadhuvar.com)

- Replaced the old matrimony DB (`82.25.121.160` / `u320743426_mvv`) completely with the
  new Disha Vadhuvar DB (`82.197.82.66` / `u583780661_dishavadhuvar`) in `backend/.env`
  and the `config.py` defaults (host/user/dbname/photo URL; password stays in `.env`).
- Inspected the new DB: same `register` structure (all `PE_*` partner-expectation columns
  present) plus the same `advance_saveandsearch` / `basic_saveandsearch` saved-search
  tables, so `matri_service`, `query_builder` and `db_query_service` needed no schema changes.
- Fixed `schema_discovery.LOOKUP_TABLES` column labels to match the new DB:
  `education→edu`, `occupation→occu`, `mother_tounge→mother_tounge`, `maritial_status→status`
  (previously pointed at non-existent columns, so those lookups silently returned nothing).
- Confirmed `PHOTO_BASE_URL` = `https://dishavadhuvar.com/gallary/` by probing a live photo.
- Optimized `_sync_fetch_all()` to fetch every table's columns in ONE
  `INFORMATION_SCHEMA.COLUMNS` query instead of one per table: schema refresh dropped from
  ~60 s to ~16 s on the slower remote host (startup `refresh_cache()` is synchronous).
- Fixed `query_builder.SEARCH_SSL` to include `MatriID` (it was missing, so search rows had
  no MatriID and profile-detail lookups by MatriID could not resolve).
- `matri_service` member `photo_url` now prepends `PHOTO_BASE_URL` (was a bare filename that
  would not render in the Profile page); test updated accordingly.
- Updated `ALLOWED_SQL_TABLES` to tables that exist in the new DB (old agent tables removed).
- Live-verified against the new DB: DB connection, schema refresh, profile search
  (Maratha brides in Pune), profile detail, and MatriID link (`ES92669`) with PE filters.
- Kept branding as-is per user (still "myvivahai" everywhere). Vector search fallback was
  deliberately NOT re-indexed (old index still holds old-DB profiles) per user decision.

## 2026-07-31 — Profile & Partner-Preference module: Phases 1-7 implemented

- Phase 1 (data layer): `User.matri_id/matri_name/matri_synced_at`, new `UserPreference`
  table (unique `(user_id, filter_key)`), migration in `database.py`, `UserResponse`
  extension, `preference_repository.py` (list/upsert/replace_all/clear/to_filter_dict).
- Phase 2 (`matri_service.py`): `normalize_matri_id` (uppercase, `^[A-Za-z0-9]+$`, ≤15),
  `fetch_partner_expectations` (register `PE_*` columns → gap-fill from
  `advance_saveandsearch` then `basic_saveandsearch`), `link_matri_id`. Verified live:
  WP88076 (PE only), WP37886 (saved-search fallback), and error paths.
- Phase 3 (`core/questionnaire.py`): zero-LLM decision tree over `BUILD_ORDER` with
  confirm (keep/change/skip), single and custom-text nodes; `start_questionnaire` /
  `advance_questionnaire` in `matri_service.py`. Fixed an infinite loop where custom text
  answers never advanced `current_node`.
- Phase 4: saved preferences auto-apply as `default_filters` in the chat profile-search
  path (merged via `_merge_filters` in `chat_service.py` and `db_query_service.py`).
- Phase 5 (`api/profile_routes.py`): PATCH `/api/profile`, POST `/api/profile/matri/link`,
  GET/POST/DELETE `/api/profile/preference`, POST `/api/profile/preference/start|next`,
  all JWT-guarded, registered in `main.py`.
- Phase 6 (frontend): `services/profileService.js`, `pages/Profile.jsx` (edit profile,
  MatriID link + PE summary, questionnaire wizard with progress bar, saved-prefs review),
  `/app/profile` route, Sidebar entry, `['me']` query invalidation. Vite build passed.
- Phase 7 (tests): added `test_matri_service.py` and `test_questionnaire.py` (36 tests).
  The new tests exposed a real bug: `apply_answers` never saved custom text answers
  (caste/education/occupation/city) because the custom-text block was unreachable behind
  `if option is None: continue`. Fixed; suite at **210 passed** (174 + 36).
- Also fixed a latent mismatch: member `photo_url` read `PhotoURL` (a column that does not
  exist) instead of `Photo1` — confirmed via INFORMATION_SCHEMA; always returned "" before.

## 2026-07-31 — Profile & Partner-Preference module: planning + Phase 1

- Inspected the live matrimony MySQL DB (`u320743426_mvv`): `register` (5,601 rows) carries
  `PE_*` partner-expectation columns (~5,101 populated) plus free-text `PartnerExpectations`;
  `basic_saveandsearch` (323) and `advance_saveandsearch` (346) store saved partner searches
  keyed by `MatriID`.
- Confirmed the app has no profile-edit surface today: `users` (SQLite) has no `matri_id`;
  no profile routes; no `/app/profile` page.
- Agreed with the user: store preferences in app SQLite (matrimony DB stays read-only),
  auto-apply saved preferences as chat search defaults, PE_* primary with saved-search
  fallback, and a pre-fill-and-confirm questionnaire.
- Created `.agents/PHASES.md` and `.agents/modules/profile-preferences-context.md`;
  updated `TODO.md`, `DECISIONS.md`, `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`.
- Started Phase 1 (backend data layer).

## 2026-07-23 — Chat error-rendering investigation started

- Reviewed the supplied frontend and backend logs.
- Confirmed the backend recovered from the earlier proxy reset and returned healthy HTTP 200 responses, followed by an intentional structured HTTP 429 quota response.
- The browser crash indicates that an object with `{code, message}` reached JSX as a React child.
- Expected modifications: normalize API failures at the frontend boundary, add focused regression coverage where practical, run the frontend production build, and update project records.

## 2026-07-23 — Chat error-rendering fix completed

- Added a reusable API-error formatter that extracts string details, structured `detail.message`, native error messages, or a safe fallback.
- Updated `useChat` so both toast and chat state receive a string instead of the backend error object.
- Added a defensive content normalization in `ChatMessage` to prevent malformed or legacy object content from becoming a React child.
- Confirmed the supplied backend log's final failure was an intentional HTTP 429 quota response; earlier Vite proxy resets occurred while the backend was unavailable/restarting.
- Validation completed: structured `{code, message}` conversion check passed, Vite production build passed (2,577 modules), and `git diff --check` passed.

## 2026-07-23 — General-response quality work started

- Reviewed user examples showing unnecessary language-detection/reasoning commentary and forced matchmaking redirects after general questions.
- Confirmed the root cause in `BASE_SYSTEM_PROMPT`: it mandates a parenthesized explanation after every response and examples reinforce the behavior.
- Expected modifications: `backend/app/core/prompts.py`, focused prompt-regression tests, and `.agents` records.
- Risk: a broad persona change could weaken the intended matrimony experience; the correction will be limited to directness, domain relevance, and non-disclosure of internal reasoning.

## 2026-07-23 — General-response quality completed

- Removed the instruction and examples that exposed parenthesized internal reasoning.
- Kept the warm matchmaker persona for matrimony requests while allowing direct answers to harmless general questions.
- Added explicit behavior for unclear/random input: request one concise clarification without guessing.
- Added direct programming and unclear-input examples to the general system prompt.
- Added three regression tests covering internal-reasoning suppression, direct off-topic assistance, and concise clarification.
- Validation completed: all 29 backend tests passed.

## 2026-07-23 02:00 +05:30 — Work started

- Read the user-supplied mandatory documentation workflow.
- Confirmed that `.agents/` existed but contained no files.
- Initialized permanent project context, architecture, decisions, issues, task tracking, and module context before application code changes.
- Started the dynamic provider/model, subscription, quota, payment, and administration implementation.
- Expected modifications: relevant backend AI/model/schema/service/API/database files; frontend router/services/hooks/pages/admin components; tests; `.agents` records.
- Primary risks: schema migration safety, incomplete historical token accounting, concurrent credit spending, provider capability differences, secret handling, and unavailable live payment credentials.

## 2026-07-26 15:30 +05:30 — Phase 3: Embedding + Qdrant vector search implemented

- Installed dependencies: qdrant-client, sentence-transformers, torch (torch 2.13.0+cpu, works with Python 3.14.6).
- Created `embedding_service.py`: BAAI/bge-m3 local embedding model (1024-d, lazy-loaded singleton). Supports `embed_text()`, `embed_batch()`, `build_profile_document()`.
- Created `vector_service.py`: Qdrant client wrapper with metadata filtering (Gender, Caste, City, Religion, Maritalstatus, Age). Auto-creates collection on first use. Cosine distance, score threshold >= 0.5.
- Created `indexing_service.py`: Full re-index pipeline — fetches all active profiles from MySQL, builds documents, generates embeddings in batches of 100, upserts to Qdrant.
- Updated `config.py`: Added QDRANT_HOST, QDRANT_PORT, EMBEDDING_MODEL, EMBEDDING_BATCH_SIZE.
- Updated `db_query_service.py`: `answer_database_question_hybrid()` now falls back to Qdrant vector search when MySQL returns 0 results. Extracted `_add_photo_url()` as reusable helper.
- All 29 tests pass. No regressions.

## 2026-07-26 15:00 +05:30 — Phase 2: Structured extraction + query builder implemented

- Added `STRUCTURED_EXTRACTION_PROMPT` to `prompts.py`: LLM outputs only JSON filters, never SQL.
- Created `extraction_service.py`: Calls LLM with extraction prompt, parses JSON, validates filters, includes keyword fallback.
- Created `query_builder.py`: Python parameterized SQL builder from structured filters. No LLM involvement.
- Updated `db_query_service.py`: Added `answer_database_question_hybrid()` — uses extraction + query builder instead of LLM SQL generation. Returns "No matching profiles found." for empty results instead of calling LLM.
- Updated `chat_service.py`: Routes to `answer_database_question_hybrid` when `CHAT_ENGINE == "hybrid_rag"`. Falls back to legacy intent+SQL path when `CHAT_ENGINE == "legacy"`.
- Default `CHAT_ENGINE` is `"hybrid_rag"` — new pipeline active by default.
- Pending: Run tests to verify no regressions.

## 2026-07-26 14:45 +05:30 — Phase 1: Hallucination fixes implemented

- Executed Phase 1 changes:
  - **Change A** — Fixed `BASE_SYSTEM_PROMPT` contradictions (lines 19-22): Removed "NEVER say you don't have access" directive. Replaced with "If no matching profiles found, honestly say 'No matching profiles found'."
  - **Change B** — Fixed `FORMAT_SYSTEM_PROMPT` example names (lines 72-73): Replaced "Sneha Patil" and "Priya Sharma" with obfuscated placeholders.
  - **Change C** — Added `_is_profile_query()` safety gate in `chat_service.py`: Before calling `get_general_response()`, checks if message contains profile-related keywords. If yes, returns "No matching profiles found" without calling any LLM.
  - **Change D** — Added `CHAT_ENGINE` feature flag to `config.py` (default: "hybrid_rag", can be "legacy").
- File changes: `prompts.py`, `chat_service.py`, `config.py`.
- No dependencies added. No new packages required.
- Pending: Run tests to verify no regressions.

## 2026-07-26 14:30 +05:30 — Hybrid RAG pipeline discovery and planning

- User reported that the chatbot is hallucinating fake matrimonial profiles (names, ages, photos, locations) in response to profile queries.
- Traced the root cause to three compounding issues:
  1. Contradictory `BASE_SYSTEM_PROMPT` directives forcing fabrication (lines 19-22).
  2. Intent classifier (llama-3.1-8b, 10 tokens) misclassifying Marathi/mixed-language subcaste queries.
  3. `FORMAT_SYSTEM_PROMPT` example names leaking into LLM output.
- Proposed a full Hybrid RAG pipeline replacement: Structured Extraction → Python Query Builder → MySQL + Qdrant fallback.
- User approved the approach and provided detailed requirements:
  - Local embedding model: BAAI/bge-m3 (multilingual, offline, no API cost).
  - Vector DB: Qdrant on a separate VPS (not Docker on main VPS).
  - Feature flag: CHAT_ENGINE = legacy|hybrid_rag for gradual migration.
  - No hardcoded examples — all generated dynamically from real database values.
  - Phase 1 priority: Stop hallucinations immediately (prompt fix + safety gate).
- Explored the laptop environment and VPS constraints:
  - Laptop: 16GB RAM, 474GB disk (283GB free), Python 3.14.x, no GPU.
  - VPS: Hostinger KVM 1 (1 vCPU, 1GB RAM, ~25GB SSD).
  - bge-m3 requires ~4-6GB RAM for CPU inference — may need KVM upgrade.
  - Qdrant requires ~200MB-500MB RAM — fits on separate KVM 1.
- Updated all `.agents/` documentation with the new architecture plan.

## 2026-07-23 02:20 +05:30 — Commercial AI module completed

- Added dynamic AI provider/model registry, task routes, ordered fallback, context checks, direct health tests, and normalized response/usage handling.
- Re-routed intent, general chat, SQL generation, database formatting, and notices through task keys while preserving legacy call compatibility for existing tests.
- Added versioned subscription plans, subscriptions, atomic/idempotent credit reservation, daily limits, usage ledger, cost estimation, payment orders, gateway configuration references, and audit records.
- Seeded Free, Basic, Silver, Groq models/routes, and the manual payment adapter safely and idempotently at startup.
- Added customer plans/subscription UI and sidebar credit display.
- Added a consolidated admin console for commercial summary, plan publication, provider/model configuration, routing/testing, subscription assignment/adjustment/cancellation, payments, gateway references, usage, and audits.
- Added six commercial quota/cost/chat integration tests; total suite now has 26 passing tests.
- Validation completed: Python compile, 26 backend tests, frontend production build, FastAPI startup/public plan smoke test, route registration inspection, and `git diff --check`.
- External limitation: live gateway payment and live AI-provider acceptance tests require deployment credentials and remain explicitly tracked.

## 2026-07-31 — Performance and stability fixes

- Analysed the reported issues against the code before changing anything; findings recorded in `.agents/PERFORMANCE_ANALYSIS.md`.
- Confirmed the `name 'db' is not defined` report by static analysis (`pyflakes` flagged `chat_service.py:380`) and then reproduced the exact log line at runtime with Qdrant reachable and zero vector hits. Also found the same call passes 5 positional arguments to a 4-parameter function.
- Established a 164-test baseline before editing, and kept it green throughout; final state is 174 tests.
- Each new regression test was verified to fail when its corresponding fix is reverted, so the tests genuinely guard the bugs.
- Two claims from the pre-approval analysis were checked and corrected: the MySQL pool does retry after a failed creation (`_pool` stays `None`), so no change was made there; and the schema-context saving is ~1.7 ms per turn rather than the 5-40 ms originally estimated, because prompt truncation caps the context near 2.5 KB.
- Scope was deliberately kept small per the follow-up instruction: dropped the proposed extraction result cache, shared HTTP client pool, route-target cache, new config settings and the vector-service async wrapper. Used `asyncio.to_thread` at the two existing call sites instead of introducing a new abstraction.
- Measured the event-loop fix directly: a 0.5 s blocking Qdrant call allowed 3 heartbeat ticks before and 52 after.
- Reviewer reported 175 passing tests against the PR head while this branch reported 174. Investigated rather than attributing it to environment variance: `tests/test_acceptance.py` declares a bare `def test_acceptance()` rather than a `unittest.TestCase`, so `unittest discover` skips it and `pytest` collects it. Both counts were correct for their runner.
- That test cannot fail: each check is wrapped in a `try/except` that only increments a counter, and the function ends with `return failed == 0` instead of asserting. Confirmed by running it under pytest with no server on localhost:8000 — it reports "1 passed" while every HTTP call fails, and pytest emits `PytestReturnNotNoneWarning`. Recorded in `ISSUES.md` as a pre-existing defect on `main`; not fixed here to keep this PR scoped to the performance work.
