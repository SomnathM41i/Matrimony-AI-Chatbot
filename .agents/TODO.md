# Tasks

## Chat error rendering

- [x] Prevent API error objects from crashing the React chat screen.
  - Related files: `frontend/src/hooks/useChat.js`, chat UI components/services, frontend tests or production build, `.agents/`.
  - Priority: Critical.
  - Status: Completed and verified 2026-07-23.
  - Dependencies: backend structured quota errors and Axios response handling.
  - Notes/risks: structured error codes remain available in the Axios response while JSX and toast rendering receive only a safe user-facing string; the transient Vite proxy reset was distinct from the confirmed HTTP 429 quota response.
  - Validation: structured `{code, message}` conversion check passed, frontend production build passed, and `git diff --check` passed.

## General-response quality

- [x] Stop exposing reasoning commentary and stop forcing unrelated requests back to matchmaking.
  - Related files: `backend/app/core/prompts.py`, `backend/tests/test_chat_error_messages.py`, `.agents/`.
  - Priority: High.
  - Status: Completed and verified 2026-07-23.
  - Dependencies: general-chat task routing and existing multilingual behavior.
  - Notes/risks: preserved database safety, multilingual replies, and the matchmaker tone for genuinely matrimony-related requests; harmless general questions and code requests are now answered directly.
  - Validation: 29 backend tests passed, including three prompt-quality regressions.

## Dynamic AI, Plans, Subscriptions, Payments, and Administration

- [x] Implement a provider/model-independent commercial module with dynamic admin control.
  - Related files: `backend/app/{models,schemas,repositories,services,api,ai}/`, `backend/app/main.py`, `backend/app/database.py`, `frontend/src/{app,pages,components,hooks,services}/`, `.agents/`.
  - Priority: Critical.
  - Status: Completed and verified 2026-07-23 02:20 +05:30.
  - Dependencies: existing auth/admin roles, SQLite application DB, Groq integration, external MySQL, future payment credentials.
  - Notes/risks: must remain backward-compatible; quotas require atomic reservation; current intent usage is not included in stored totals; payment live activation cannot be fully verified without a selected provider and credentials; model capability checks are required before route publication.
  - Expected scope: provider/model registry, task routing and fallback, normalized usage/cost ledger, versioned plan catalogue, subscriptions, quotas, payment abstraction, admin APIs/UI, customer plan/usage UI, tests, and documentation.
  - Validation: 26 backend tests passed; frontend production build passed; application startup and public plan API smoke test returned Free/Basic/Silver; `git diff --check` passed.

- [!] Install and verify a live payment-gateway adapter.
  - Related files: `backend/app/services/payment_gateway.py`, commercial payment APIs, gateway configuration in the admin console.
  - Priority: High before accepting online payments.
  - Status: Blocked pending the business choice of gateway plus sandbox credentials and webhook secret.
  - Dependencies: provider account, approved redirect/webhook URLs, refund/cancellation policy.
  - Notes: manual admin verification is intentionally active; the application does not claim live checkout is available.

- [ ] Run deployment acceptance tests with the selected AI providers and production database copy.
  - Related files: AI provider/model routes, deployment environment, commercial database tables.
  - Priority: High before production rollout.
  - Status: Pending.
  - Dependencies: deployed provider secrets, reachable MySQL, staging deployment.
  - Notes: model health-test and route-test controls are available in the admin console.
