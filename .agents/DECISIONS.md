# Decisions

## 2026-07-23 — Provider-independent AI and subscription boundaries

- Decision: AI tasks will use a router and normalized provider interface; subscription logic will use normalized usage and user-facing credits rather than provider-specific APIs.
- Reason: providers, models, endpoints, token prices, and availability can change without invalidating subscriptions.
- Alternatives considered: keep direct Groq calls and add plan checks around them; rejected because it hard-couples commercial logic to one provider.
- Impact: current Groq client will become an adapter and all task modules will select routes by task key.

## 2026-07-23 — Versioned plans and rates

- Decision: plan benefits and model rates will be versioned/snapshotted.
- Reason: later administrative edits must not rewrite historical payments, entitlements, or costs.
- Impact: additional persistence and admin publication workflow are required.

## 2026-07-23 — Server-authoritative commercial state

- Decision: prices, credits, subscription status, token cost, and payment verification are authoritative only on the backend.
- Reason: browser state is user-controlled and cannot safely enforce billing.
- Impact: existing local-storage token display remains informational only.

## 2026-07-23 — Environment-referenced provider secrets

- Decision: provider and payment configuration stores environment-variable names, not readable secret values.
- Reason: administrators need dynamic routing/configuration without exposing credentials through APIs, browser storage, database exports, or logs.
- Alternatives considered: encrypted secret contents in the application database; deferred because safe key management and rotation require a separate deployment secret.
- Impact: adding a provider requires setting its secret in the server environment and entering only that variable name in the admin panel.

## 2026-07-23 — Manual payments before live gateway selection

- Decision: implement provider-neutral payment contracts, server-authored pending orders, and audited manual confirmation; do not simulate online checkout.
- Reason: no gateway or sandbox credentials were supplied, and falsely activating client-reported payments would be unsafe.
- Alternatives considered: assume a gateway and hard-code it; rejected as contrary to provider independence and payment security.
- Impact: live payment integration is an explicit blocked follow-up; subscriptions can be fully tested and operated manually meanwhile.

## 2026-07-23 — Atomic maximum-credit reservation

- Decision: reserve the maximum of normal/database credit cost with a conditional database update, then finalize idempotently.
- Reason: the request type is known only after intent detection and concurrent messages must not overspend a balance.
- Impact: long-running provider calls do not leave an open write transaction, failures release credits, and duplicate finalization cannot double-charge.

## 2026-07-23 — Domain persona without forced redirection

- Decision: keep matchmaking as the assistant's primary persona while answering harmless general questions directly.
- Reason: forcing coding, mathematics, or unclear input back into matchmaking creates irrelevant replies and a poor user experience.
- Impact: provider/model changes inherit the same behavior through the centrally managed general-chat system prompt; internal reasoning and language-detection notes must never be shown to users.
