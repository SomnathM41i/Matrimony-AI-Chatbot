# Changelog

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
