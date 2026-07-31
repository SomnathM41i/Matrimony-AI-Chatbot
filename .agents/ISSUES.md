# Issues

## `test_acceptance.py` reports a false pass under pytest

- Root cause: `tests/test_acceptance.py` defines a bare `def test_acceptance()` (not a `unittest.TestCase`), so `unittest discover` skips it while `pytest` collects it. Inside, every check is wrapped in a `try/except` that swallows the exception and increments a counter, and the function ends with `return failed == 0` instead of `assert`. Pytest ignores return values, so the test reports "1 passed" even when the server is unreachable and every HTTP call fails.
- Evidence: running `pytest tests/test_acceptance.py` with no server on `localhost:8000` yields `1 passed`, plus `PytestReturnNotNoneWarning: ... returned <class 'bool'>. Did you mean to use assert instead of return?`
- Effect: explains why the suite counts as 174 under `unittest` and 175 under `pytest`. The extra test provides no real coverage under either runner; it is a live deployment smoke script that must be run manually against a running server.
- Affected files: `backend/tests/test_acceptance.py`.
- Severity: Low for correctness (no product code affected), Medium for process — it is a permanently green test that can never fail.
- Status: Open. Pre-existing on `main`, not introduced by the performance work. Suggested fix: convert the internal counters to real `assert`s and mark it with a pytest marker (or rename it off the `test_` prefix) so it is not collected in the default unit-test run.

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

## LLM hallucinates fake matrimonial profiles (RESOLVED)

- Root cause (primary): `BASE_SYSTEM_PROMPT` lines 19-22 contain contradictory directives — "NEVER say you don't have access to member information" conflicts with "NEVER invent profile details." When intent misclassification routes a profile query to the general response path, the model can neither refuse nor answer truthfully, so it fabricates profiles.
- Root cause (secondary): Intent classifier uses llama-3.1-8b with only 10 max tokens, which frequently misclassifies Marathi/mixed-language queries about subcastes like "96 Kuli Maratha" as "general" instead of "database."
- Root cause (tertiary): `FORMAT_SYSTEM_PROMPT` example names ("Sneha Patil", "Priya Sharma") leak into LLM output as fabricated profile data.
- Root cause (quaternary): Even when data was retrieved from DB, the LLM formatting layer would fabricate personal details (favorite food, appetite, eating habits) that don't exist in any database column.
- Affected files: `backend/app/core/prompts.py`, `backend/app/services/db_query_service.py`, `backend/app/services/chat_service.py`
- Severity: Critical — users received fake personal data (names, ages, photos, food preferences) for real members.
- Status: RESOLVED 2026-07-27. Multiple defense layers implemented:
  1. Hybrid RAG pipeline (Phases 2-5): Structured extraction + Python query builder replaces intent→SQL generation. LLM never generates SQL or free-text answers.
  2. Safety gate in `chat_service.py`: Profile-keyword queries in general path return "No matching profiles found" without calling LLM.
  3. Pre-formatting guard in `_handle_profile_detail()`: Detects questions about unavailable personal attributes (favorite food, appetite, eating habits) and returns "not available" without calling LLM.
  4. `FORMAT_SYSTEM_PROMPT` hardened with explicit list of forbidden fabrications and "MOST IMPORTANT rule" emphasis.
  5. `BASE_SYSTEM_PROMPT` strengthened with anti-hallucination instructions.
  6. Legacy modules (`intent_llm.py`, `intent_detector.py`, `sql_generator.py`) deleted.

## Python 3.14 compatibility for ML dependencies

- Root cause: The development laptop runs Python 3.14.x. PyTorch and sentence-transformers may not have official wheels for Python 3.14, requiring compilation from source or fallback to CPU-only builds.
- Affected files: `backend/requirements.txt`, deployment environment.
- Severity: Medium — may cause installation delays or require Python version downgrade.
- Status: Resolved 2026-07-26. Phase 3 confirmed `torch 2.13.0+cpu` and `sentence-transformers 5.6.1` work with Python 3.14.6 on Windows x64. CPU-only builds are sufficient for the bge-m3 embedding model. No version downgrade required.

## bge-m3 memory requirements on KVM 1 VPS

- Root cause: BAAI/bge-m3 requires ~4-6GB RAM for CPU-based inference. The existing Hostinger KVM 1 VPS has only 1GB RAM.
- Affected files: `backend/app/services/embedding_service.py`, deployment architecture.
- Severity: High — the embedding model cannot run on the main app VPS.
- Status: Design decision — bge-m3 runs on the same VPS as the main application. The VPS may need upgrading to KVM 2 (2GB RAM) or KVM 4 (4GB RAM) for inference. Alternative: load the model lazily or use a smaller model for the main VPS and keep bge-m3 for indexing only.
- Resolution: Test bge-m3 RAM usage on laptop first. If VPS cannot handle it, options include: (1) upgrade VPS plan, (2) use a smaller embedding model on the app VPS, (3) run embeddings on a separate instance.
