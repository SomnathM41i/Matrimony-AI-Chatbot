# Project Context

## Purpose

`myvivahai` is an AI matrimony chatbot. Authenticated users can converse with an assistant, search an external matrimonial MySQL database, inspect profiles and plans, and retain conversation history. Administrators can monitor users, profiles, conversations, and platform statistics.

## Technology Stack

- Backend: Python, FastAPI, SQLAlchemy async ORM, Pydantic, HTTPX, SlowAPI.
- Local application database: SQLite via `DATABASE_URL`; stores chatbot users, conversations, and messages.
- Business/profile database: external MySQL; queried through `mysql.connector` using a strict read-only SQL validation layer.
- AI: currently Groq's OpenAI-compatible chat-completions endpoint.
- Frontend: React, Vite, React Router, TanStack Query, Zustand, Tailwind CSS, Framer Motion.
- Authentication: JWT access and refresh tokens stored in HTTP-only cookies.

## Business Requirements

- Preserve existing chat, history, authentication, database search, and admin workflows.
- Add versioned Free, Basic, and Silver subscription plans with dynamic prices, validity, contacts, AI credits, and daily limits.
- Initial intended catalogue: Free (50 credits/month, 10/day), Basic (INR 2,499/30 days, 500 credits, 200/day, 30 contacts), Silver (INR 4,999/60 days, 1,500 credits, 200/day, 60 contacts).
- Default charging: one credit for normal chat and two credits for database/profile requests; failed AI responses must not consume credits.
- Allow 2-3 hour paid-user sessions while applying fair-use and credit controls.
- Make AI providers, models, prices, task routes, and fallbacks dynamic and manageable through the admin panel.
- AI service changes must not affect subscription/payment business logic.
- Payment integration must use server-authoritative prices, signature/webhook verification, idempotency, and a provider abstraction.

## Important Workflows

- Chat: `/api/chat` authenticates, validates a message, calls `ChatService`, stores user/assistant messages, commits, and returns usage.
- AI classification: intent model decides between general and database paths.
- Database path: model creates safe SELECT SQL, server validates and executes it against MySQL, then a model formats results.
- Authentication: login/register set access and refresh cookies; `/api/auth/refresh` rotates both tokens.
- Frontend protected routes live under `/app`; admin routes live under `/admin`.

## Database Context

- SQLite application tables: `users`, `conversations`, `chat_messages`.
- MySQL business tables include `register`, `membershipplan`, `siteconfig`, content/success tables, and agent-related tables.
- Financial, subscription, payment, provider-secret, and internal usage tables must never be exposed through `ALLOWED_SQL_TABLES`.
- Production subscription and payment mutations must be transactional and concurrency-safe.

## Existing Conventions and Important Files

- Settings: `backend/app/config.py`.
- App startup and routers: `backend/app/main.py`.
- Local DB setup: `backend/app/database.py`.
- Authentication: `backend/app/api/auth_routes.py`, `backend/app/core/auth.py`.
- Chat route/service: `backend/app/api/chat_routes.py`, `backend/app/services/chat_service.py`.
- Current AI HTTP client: `backend/app/ai/llm_client.py`.
- AI tasks: `backend/app/ai/intent_llm.py`, `backend/app/ai/sql_generator.py`, `backend/app/services/llm_service.py`.
- MySQL execution: `backend/app/services/db_query_service.py`.
- Frontend router: `frontend/src/app/router.jsx`.
- Admin pages: `frontend/src/pages/admin/`.

## Session Variables

- HTTP-only cookies: `access_token`, `refresh_token`.
- Zustand authentication state: `token` boolean and `user` object.
- Legacy browser usage key: `token_usage`; informational only and never authoritative for billing.

## Routes and Redirects

- `/chat` and `/chat/:conversationId` redirect to `/app/chat...`.
- `/history` redirects to `/app/history`.
- `/register` currently redirects to `/login` even though a registration API exists.
- Protected user routes use `/app/*`; administrators use `/admin/*`.

## Restrictions and Non-negotiable Rules

- Preserve existing APIs and flows where practical; additions should be backward-compatible.
- Do not trust plan prices, credit balances, provider costs, or payment status supplied by the browser.
- Do not expose provider/payment secrets in API responses or logs.
- Do not charge credits for failed AI operations.
- All administrative mutations require the existing admin authorization guard plus server-side role checks.
- Store money as integer minor units (paise or provider currency minor units), never floating point.
- Keep provider token cost separate from user-facing credits.
- Use versioned plan/model-rate records so history remains reproducible.

## Previously Completed Work

- Existing authenticated chatbot, history, MySQL query assistant, Groq integration, token fields, and admin monitoring were present before `.agents` documentation was initialized.
- On 2026-07-23 the commercial AI module was added: versioned plans, subscriptions, atomic credit reservations, daily limits, normalized per-call usage/cost events, dynamic AI providers/models/task routing/fallbacks, manual payment orders, provider-neutral payment contract, customer plans UI, and the Commerce & AI admin console.
- Application startup now seeds Groq provider/models, five task routes, the Free/Basic/Silver catalogue, and a manual verification gateway only when those records do not already exist.
- Current paid checkout state is manual administrator verification; no external gateway adapter is installed.

## Commercial Routes

- Customer: `/api/commercial/plans`, `/me`, `/usage`, `/orders`.
- Administration: `/api/admin/commercial/*` for plans, providers, models, routes, subscriptions, orders, gateways, usage, summary, and audit.
- Frontend: `/app/plans` and `/admin/commercial-ai`.
