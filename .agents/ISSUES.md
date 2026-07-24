# Issues

## Structured chat errors crash the React route

- Root cause: the backend returns quota failures as a structured `{code, message}` detail object, while the frontend chat error path passed that object into JSX and the toast instead of a display string.
- Affected files: frontend chat hook/components and API error handling.
- Severity: Critical user-interface failure.
- Status: Resolved 2026-07-23. API errors are normalized to strings at the chat boundary, and `ChatMessage` defensively normalizes non-string content.

## General replies expose internal reasoning and force domain redirection

- Root cause: `BASE_SYSTEM_PROMPT` explicitly requires a parenthesized reasoning/action sentence and instructs a matchmaker persona without a rule allowing direct handling of harmless off-topic questions.
- Affected files: `backend/app/core/prompts.py`.
- Severity: High user-experience issue.
- Status: Resolved 2026-07-23. The general prompt now answers clear questions directly, asks one brief clarification for unclear input, and forbids internal reasoning/language-detection commentary.

## AI usage under-counts intent detection

- Root cause: `detect_intent_with_llm` returns only a boolean and discards the provider usage returned by `call_groq`.
- Affected files: `backend/app/ai/intent_llm.py`, `backend/app/services/chat_service.py`.
- Severity: High for billing, Low for current chat functionality.
- Status: Resolved 2026-07-23. Intent detection now returns normalized usage/events to `ChatService`, and every successful AI task call is written to `ai_usage_events`.

## Local SQLite schema may lag SQLAlchemy models

- Root cause: startup migration currently adds only two user columns; an observed existing SQLite database did not expose the token columns defined by `ChatMessage`.
- Affected files: `backend/app/database.py`, `backend/app/models/chat_model.py`, deployed/local database files.
- Severity: High for usage accounting.
- Status: Resolved 2026-07-23. Startup migration adds missing token columns and registers/creates all commercial models before seeding defaults. Startup smoke test passed against the existing local database.

## No payment provider selected or configured

- Root cause: payment-provider choice and credentials were not supplied.
- Affected files: future billing adapter and deployment configuration.
- Severity: Blocks live payment verification only.
- Status: Blocked for live checkout. A manual adapter, pending orders, audited admin confirmation, and an abstract adapter contract are implemented. A live adapter still requires a selected gateway and sandbox credentials.

## Live provider integration not exercised in automated tests

- Root cause: external AI endpoints, valid provider secrets, and a staging environment are outside the isolated test suite.
- Affected files: `backend/app/ai/gateway.py` and admin model/route health endpoints.
- Severity: Medium before deployment, not a code-completion blocker.
- Status: Open deployment task. Unit/integration tests validate normalized cost and complete chat accounting with mocked AI results; admins can run live model and route tests after secrets are installed.
