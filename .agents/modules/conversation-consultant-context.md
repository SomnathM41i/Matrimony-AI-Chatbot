# Conversation Flow Enhancement — "Consultant" Track (CF-0..CF-7)

Feature: turn the chat from a search assistant into a **personal matrimonial
consultant persona** — "MyVivahAI" — that is **Marathi-first**, requires a MatriID
gate before full service, loads the member's **rich register profile** and shows a
**Marathi profile summary**, runs a **missing-only preference questionnaire** that
**auto-applies known DB preferences** without re-asking, starts **profile search
early** (before the full questionnaire), keeps **conversation memory** (last topic,
viewed profiles, compared pairs, last filters) for a **welcome-back** greeting, offers
**dynamic suggestion chips**, and renders **rich biodata directly in chat**.

Tracked as CF-0..CF-7. Follows P1-P7 (P7 = backend hardening + frontend a11y/streaming
watchdog). After CF-7, P8-P11 resume.

## Confirmed Decisions (2026-08-02)

1. **Identity (CF-0)**: assistant is **MyVivahAI — a professional matrimonial
   consultant, currently assigned to the Dishavadhuvar Matrimony platform**. Never
   "Dishavadhuvar AI", never "chatbot". Persona is **parametric** via config
   `ASSISTANT_NAME` / `PLATFORM_NAME` so it can be reused on future platforms.
   New onboarding welcome copy (exact, user-supplied):

   ```
   👋 नमस्कार!

   मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार.

   मी Dishavadhuvar वरील तुमचे प्रोफाइल समजून घेईन, तुमच्या पसंतीनुसार योग्य स्थळे शोधून देईन, प्रत्येक प्रोफाइल समजावून सांगेन आणि योग्य निर्णय घेण्यासाठी मार्गदर्शन करेन.

   सुरुवात करण्यासाठी कृपया तुमचा Matri ID सांगा.
   ```

2. **Marathi-first (user: "All replies default Marathi")**: EVERY assistant reply
   defaults to Marathi — including profile search/detail/comparison content replies
   even when the user types English/Hinglish. Hindi/English only when the user
   clearly writes in or requests that language. (Supersedes the earlier assumption
   that only onboarding/greeting had to be Marathi.)

3. **MatriID gate (CF-1)**: **soft by default** — first message of a brand-new
   conversation with no linked MatriID shows the welcome + asks for the ID once,
   then proceeds with guest browsing. **Hard** mode must exist behind config
   `MATRI_ID_GATE_MODE` (`soft`|`hard`). Persist `matri_id_prompted` metadata flag.

4. **Known DB preferences auto-apply (CF-3)**: never re-ask known values. The
   "कायम ठेवा?" confirm steps are dropped from the *chat* onboarding path; known
   values are silently applied, only missing/"Any" categories are asked.

5. **Search-early (CF-3)**: start showing matches as soon as the profile is
   "viable to search" instead of waiting for the full questionnaire. Strategies are
   all kept in code behind config `ONBOARDING_SEARCH_STRATEGY`:
   - `gender_plus_core` (**default**): partner gender + at least one of age/city/education
   - `gender_only`: only partner gender required
   - `full_only`: wait for the full questionnaire (current behaviour)
   - User may flip strategies later with a short config change (no code change).

6. **Onboarding trigger (CF-3)**: full onboarding runs only when the MatriID is
   linked AND the user has **zero prior conversations anywhere**. Any prior
   conversation (any chat session) = skip onboarding; restore context /
   welcome-back instead.

7. **Profile detail (CF-6)**: rich biodata renders **embedded in chat** (sectioned
   Marathi biodata + follow-up chips). No modal.

8. **No-ID static suggestions (CF-5)**: EmptyState's current static Marathi
   suggestion chips become **dynamic** based on whether a MatriID is linked; the
   chips click through `SUGGESTION_ROUTES` phrase matching (deterministic, no LLM).

9. **Sequencing**: CF-0..CF-7 run **before** P8-P11 (P8 more tests, P9 known-failure
   fix, P10 AI eval, P11 KVM2 deploy). CF-0..CF-7 complete ✅ (2026-08-02). P8 ✅
   (`test_db_query_formatting.py`, 15 tests) and P9 ✅ (photo-URL assertion now derives
   from `settings.PHOTO_BASE_URL`; suite fully green **430 passed / 0 failed**). P10 ✅
   offline harness (`tests/eval_harness.py`, 10 scenarios, `python -m tests.eval_harness`
   → 10/10). P11 ✅ runbook (`.agents/modules/deployment-runbook.md`); live KVM2 execution
   needs server access/secrets.

10. **`.agents/` constraint reversed (2026-08-02)**: user explicitly asked to update
    the `.agents/` folder so all decisions and the plan are remembered ("update
    agents folder according so will remmber all the things and start step by step").
    This supersedes the earlier "forget about agents folder" instruction.

## Phase Plan

| Phase | Scope | Files (primary) | Done |
|---|---|---|---|
| CF-0 | MyVivahAI identity + Marathi-first: `ASSISTANT_NAME`/`PLATFORM_NAME` config; identity + language clause in all prompts; new `WELCOME_MESSAGE` (exact copy above); branded `GREETING_RESPONSES`; persona answer to "who are you"; update greeting-copy tests; add persona/language test | `config.py`, `.env.example`, `core/prompts.py`, `services/llm_service.py`, `services/chat_service.py`, `tests/test_chat_error_messages.py` | ✅ |
| CF-1 | Identity gate: first message of new conversation without MatriID → `WELCOME_MESSAGE` + chips; `MATRI_ID_GATE_MODE` soft/hard; `matri_id_prompted` metadata flag | `services/chat_service.py`, `config.py` | ✅ |
| CF-2 | Rich profile load + Marathi summary: expand `_fetch_register_row` to full register columns; `format_user_profile_summary()` (zero-LLM Marathi "तुमचे प्रोफाइल" + "तुमच्या जोडीदाराच्या पसंती"); show once after link on first-ever conversation | `services/matri_service.py`, `services/chat_service.py` | ✅ |
| CF-3 | Missing-only questionnaire + search-early: `build_nodes(..., missing_only=True)` in `core/questionnaire.py` (auto-apply known, ask missing only); `is_viable_search()` per strategy; search as soon as viable + refinement chips; onboarding only when zero prior conversations | `core/questionnaire.py`, `services/chat_service.py`, `config.py` | ✅ |
  | CF-4 | Conversation memory + welcome-back: persist/restore `last_topic`, `viewed_profiles`, `compared_pairs`, `last_filters` in message metadata; resume-greeting → Marathi "परत स्वागत!" + contextual chips | `services/chat_service.py` | ✅ |
  | CF-5 | Suggestions engine: deterministic `build_suggestions(context)` (Marathi chips) in `done` events; `SUGGESTION_ROUTES` click handling (no LLM); render chips in `ChatMessage.jsx`, capture in `useChat.js`; dynamic `EmptyState.jsx` | `services/chat_service.py`, `frontend/src/components/ui/ChatMessage.jsx`, `frontend/src/hooks/useChat.js`, `frontend/src/components/ui/EmptyState.jsx` | ✅ |
| CF-6 | Chat-embedded rich biodata: sectioned Marathi biodata (photos/education/family/lifestyle/horoscope/partner-pref/compatibility) + follow-up chips; reuse `resolve_contextual_profile`/`selected_profile` | `services/chat_service.py`, `services/matri_service.py`, `services/db_query_service.py`, `frontend/src/components/ui/ChatMessage.jsx` | ✅ |
| CF-7 | Tests + verification: new tests per phase; expected updates to `test_matri_auto_link.py` (link reply becomes summary + missing-only, not `MATRI_ID_SUCCESS`/confirm-node) and `test_chat_questionnaire_flow.py`; verify `test_session_unification_e2e.py`; suite green | `tests/` | ✅ |

## Definition of Done (per phase)

- Backend: phase code compiles; full suite stays green (baseline 351 passed / 1 known
  P9 failure); new tests added where feasible.
- Frontend: `npm run build` passes.
- Docs: `WORK_LOG.md`, `CHANGELOG.md`, `TODO.md`, and affected context docs updated
  (README workflow: update TODO + WORK_LOG before coding; CHANGELOG + WORK_LOG after).
- Matrimony MySQL DB stays read-only.

## Security / Constraints

- MatriID lookups keep using server-built parameterized queries (`execute_param_query`).
- Identity/config values must remain `.env`-configurable; never hardcode the brand.
- No LLM call for suggestion chips or profile summaries (zero-LLM paths preferred).
- LLM stack (Ollama qwen2.5:7b primary / Groq fallback) and vector-fallback constraints
  from P1-P4 remain unchanged.
- Do not break the profile-page questionnaire path (`start_questionnaire`/
  `advance_questionnaire` in `matri_service.py`): CF-3's `missing_only` applies to the
  **chat onboarding** path only.

## Open Items / Notes

- **PHOTO_BASE_URL discrepancy — RESOLVED (CF-2, 2026-08-02)**: `.env` pins
  `https://dishavadhuvar.in/gallary/`; a real photo
  (`2023_07_11_01_31_0431.jpg`) returns **200 on BOTH** `dishavadhuvar.com`
  (LiteSpeed origin) and `dishavadhuvar.in` (hcdn CDN). Not a bug. The
  `test_register_only_fetch` assertion expecting `.com` is the known P9 failure —
  fix in P9 (either point the test at `.in` or flip the config, both work).
- Greeting copy lives in `chat_service.py` `GREETING_RESPONSES` (now MyVivahAI Marathi,
  CF-0 done); `prompts.py` persona examples were rebranded in CF-0 (`BASE_SYSTEM_PROMPT`,
  `FORMAT`, `INTENT` are f-strings; `STRUCTURED_EXTRACTION_PROMPT` stays a plain string
  with the `_EXTRACTION_IDENTITY` prefix injected at the `extraction_service` call site —
  f-string formatting breaks on its JSON braces).
- CF-0 done: `MyVivahAIIdentityTests` added to `test_chat_error_messages.py`; greeting-copy
  assertions updated. CF-1 done: `test_identity_gate.py` added; `MATRI_ID_GATE_MODE` +
  `WELCOME_SUGGESTIONS` + `matri_id_prompted` metadata live. CF-2 done: `profile` +
  `pe_summary_mr` on `fetch_partner_expectations`; auto-link reply prepends
  `format_user_profile_summary()` (live-verified with ES92669). CF-3 done:
  `build_nodes(missing_only=True)` for chat (no confirm nodes), `is_viable_search()` +
  `ONBOARDING_SEARCH_STRATEGY`, search-early (once per session via
  `questionnaire_searched`), onboarding gated on zero prior conversations. CF-4 done:
  `_enrich_memory()` persists `last_topic`/`viewed_profiles`/`compared_pairs`/
  `last_filters`; `_load_history` restores them + `questionnaire_searched`;
  `handle_profile_comparison` metadata gains `compared_pair`;
  `_welcome_back()` streams "परत स्वागत!" + topic-aware chips for a linked returning
  user on a brand-new conversation; main-flow `done` uses `_done_event`;
  `test_conversation_memory.py` added (16 tests). CF-5 done: `build_suggestions(context)`
  deterministic chips in every `done` event (matri link / questionnaire_done / last_topic /
  generic); `SUGGESTION_ROUTES` exact-phrase routing skips LLM extraction (resume/new/next
  search, comparison, first-candidate detail, `reset_filters`); `ChatMessage.jsx` renders
  `message.suggestions`, `useChat.js` captures `doneEvent.suggestions` + history
  `meta.suggestions`, `EmptyState.jsx` dynamic by `needsMatriId`; `test_suggestions.py`
  added (10 tests). Suite 405 passed / 1 known P9; frontend build succeeds. CF-6 done:
  `BIODATA_SECTIONS` (8 sections) + `_BIODATA_LABELS_MR` in `matri_service.py`; zero-LLM
  `format_profile_biodata(row)` / `format_profile_section(row, key)`; `BIODATA_SECTION_ROUTES`
  chips routed via `SUGGESTION_ROUTES` to `profile_detail` + `biodata_section` on the current
  profile (no LLM); the profile_detail branch renders full biodata for `fields=["all"]` and
  single sections for section chips (`_DETAIL_CATEGORY_QUESTION` bounce removed);
  `test_biodata.py` added (9 tests). Suite 414 passed / 1 known P9; frontend build succeeds.
  CF-7 done: verified `test_matri_auto_link.py` + `test_chat_questionnaire_flow.py` +
  `test_session_unification_e2e.py`; strengthened `test_suggestions.py` first-candidate
  detail test to prove zero-LLM biodata — caught a real bug (`selected_index: 0` vs
  1-based `resolve_contextual_profile` never resolved; fixed to `1`). Suite 414 passed /
  1 known P9; frontend build succeeds. **Consultant track CF-0..CF-7 complete ✅;
  P8-P11 resume next.**
