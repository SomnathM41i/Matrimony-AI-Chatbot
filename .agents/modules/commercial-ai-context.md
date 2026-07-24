# Commercial AI Module Context

## Objective

Add dynamic commercial controls without coupling plans or subscriptions to any AI vendor. Administrators must manage plans, users' subscriptions, AI providers, models, token prices, task routing, fallbacks, usage, payments, and audit history.

## Confirmed Initial Business Defaults

- Free: INR 0, monthly allowance 50 credits, 10 messages/day, no contacts.
- Basic: INR 2,499, 30 days, 500 credits, 200 messages/day, 30 contacts.
- Silver: INR 4,999, 60 days, 1,500 credits, 200 messages/day, 60 contacts.
- Normal successful chat: one credit.
- Database/profile successful chat: two credits.
- Failed AI work: no credit charge.

## Provider Independence

- Task keys: `intent_detection`, `general_chat`, `sql_generation`, `database_formatting`, and optionally `database_notice`/`translation`.
- Provider adapters return a normalized response and usage record.
- Route publication must validate provider/model availability and task capabilities.
- Ordered fallback is allowed for transient errors and rate limits, not invalid credentials/configuration loops.

## Commercial Independence

- User credits do not change automatically when a model price changes.
- Actual provider cost is calculated from effective model-rate versions and shown in profitability reports.
- Existing subscribers retain their purchased plan snapshot.
- Admin changes must be audited.

## Security

- Provider secrets are write-only/masked and encrypted or referenced from environment configuration.
- Client-provided prices, balances, subscription status, and payment results are never trusted.
- Internal commercial tables are excluded from AI-query table allowlists.

## Verification Constraints

- Live payment activation cannot be end-to-end tested until a concrete payment provider and test credentials are supplied.
- Ollama/provider fallbacks can be configured but require the external service to be running for integration tests.

## Implemented Status — 2026-07-23

- Backend commercial models, seed data, customer/admin APIs, atomic quotas, plan versioning, provider/model routing, transient fallback, context validation, normalized usage/cost tracking, audit events, manual orders, and payment adapter contract are implemented.
- Customer plan selection and balance display are available at `/app/plans` and in the chat sidebar.
- The consolidated admin console at `/admin/commercial-ai` controls plans, providers, models, task routes, subscriptions, orders, gateway references, usage, and audit history.
- Free subscriptions are lazily created for authenticated users and renew after expiration when no paid plan is active.
- Live checkout remains disabled until a concrete payment adapter is installed and configured.
