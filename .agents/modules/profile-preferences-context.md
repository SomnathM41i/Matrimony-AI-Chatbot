# Profile & Partner-Preference Module Context

## Objective

Give authenticated users a profile-edit surface where they can link their matrimony website
user ID (`MatriID`). The backend reads that member's existing partner expectations from the
live matrimony MySQL DB (`register.PE_*` with saved-search fallback), then runs a
**rule-based decision-tree questionnaire** — zero LLM calls — that confirms known values and
captures fresh preferences. Stored preferences auto-apply as default filters in chat profile
searches, cutting LLM extraction/formatting cost and improving result relevance.

## Data Sources (read-only, live matrimony DB)

- `register` — member profiles. Partner-expectation columns: `PE_FromAge`, `PE_ToAge`,
  `PE_HaveChildren`, `PE_from_Height`, `PE_to_Height`, `PE_Height2`, `PE_Complexion`,
  `PE_MotherTongue`, `PE_Religion`, `PE_Caste`, `PE_subcaste`, `PE_Education`,
  `PE_Occupation`, `PE_Countrylivingin`, `PE_Residentstatus`, `PE_State`, `PE_City`,
  `PE_income_from`, `PE_income_to`, plus free-text `PartnerExpectations`.
- `advance_saveandsearch` / `basic_saveandsearch` — saved partner searches keyed by `MatriID`
  (fromage/toage, religion, caste, subcaste, education, occupation, marital status, city,
  state, district, country, withphoto).

## Architecture Overview

```text
Profile page (React)
  -> PATCH /api/profile                    (name, profile_image, MatriID)
  -> POST /api/profile/matri/link          (validate + sync PE summary)
  -> POST /api/profile/preference/start    (build flow, pre-fill known values)
  -> POST /api/profile/preference/next     (answer -> next question, zero LLM)
  -> GET|DELETE /api/profile/preference    (saved filters)
  -> user_preferences (SQLite)
  -> chat profile_search: preferences merge as default accumulated_filters
```

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Preference storage | App SQLite `user_preferences` | Matrimony MySQL stays read-only; no write path needed. |
| MatriID sync source | `register.PE_*` first, saved-search fallback | PE_* is canonical; saved searches fill gaps. |
| Questionnaire engine | Rule-based decision tree (JSON) | Zero LLM cost per question. |
| Question options | Map to `DEFAULT_FILTERS` keys | Answers become `build_profile_query` filters directly. |
| Known-value handling | Pre-fill & confirm ("Keep X / Change / Skip") | Fewer steps; personalization without LLM. |
| Chat integration | Merge saved prefs as default filters | Fewer extraction calls, better relevance. |

## New Files

| File | Purpose |
|---|---|
| `backend/app/models/user_preference_model.py` | SQLite `user_preferences` table (filter_key/value/source). |
| `backend/app/repositories/preference_repository.py` | Persistence for preference rows. |
| `backend/app/services/matri_service.py` | MatriID validate/link, PE summary, saved-search fallback, questionnaire flow engine. |
| `backend/app/core/questionnaire.py` | Decision-tree definition + traversal helpers. |
| `backend/app/api/profile_routes.py` | JWT-guarded profile/preference endpoints. |
| `frontend/src/pages/Profile.jsx` | Profile edit + MatriID link + questionnaire wizard. |
| `frontend/src/services/profileService.js` | API client for profile/preference endpoints. |
| `backend/tests/test_matri_service.py`, `backend/tests/test_questionnaire.py` | Unit coverage. |

## Modified Files

| File | Changes |
|---|---|
| `backend/app/models/user_model.py` | Add `matri_id`, `matri_name`, `matri_synced_at`. |
| `backend/app/models/__init__.py` | Export `UserPreference`. |
| `backend/app/database.py` | ALTER TABLE migration for new `users` columns. |
| `backend/app/schemas/auth_schema.py` | Extend `UserResponse` with matri fields. |
| `backend/app/repositories/user_repository.py` | `update_profile` helper. |
| `backend/app/services/chat_service.py`, `db_query_service.py` | Merge saved prefs as default filters. |
| `backend/app/main.py` | Register `profile_router`. |
| `frontend/src/app/router.jsx`, `components/ui/Sidebar.jsx`, `hooks/useAuth.js` | Route, entry point, state refresh. |

## Flow Engine Contract (questionnaire)

- `start(user_id, pe_summary)` -> first node (or a "keep/change" confirm node for known values).
- `answer(user_id, node_id, option_ids)` -> next node or `{done: true}`.
- Node fields: `id`, `category`, `question`, `type` (`single` | `multi` | `confirm`),
  `options`: `[{id, label, value, filters:{...}, next}]`, `skip_next`.
- On `done`, answers are flattened into a `DEFAULT_FILTERS`-compatible filter dict and saved
  with `source='questionnaire'`; PE-sourced rows are kept and overwritten per filter_key.

## Security / Constraints

- All profile/preference endpoints require `get_authenticated_user`.
- MatriID lookups are server-built parameterized queries via `execute_param_query`.
- No writes to the matrimony MySQL DB. No changes to commercial/subscription logic.
- `SENSITIVE_FIELDS` sanitation applies to any MySQL rows surfaced to the client.
