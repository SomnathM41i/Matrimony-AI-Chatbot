# Performance & Stability Analysis — Pre-Implementation Report

Date: 2026-07-31
Scope: `backend/` only. No business logic, prompts, schema, API contracts, or UI behaviour changes proposed.
Status: **Implemented 2026-07-31 at reduced scope.** See "Implementation outcome" at the end of this document for
what was actually built, which proposals were dropped as over-engineering, and which two claims below proved wrong
on closer inspection. The body is preserved as the original pre-approval analysis.

---

## 1. Root-cause analysis per issue

### Issue 1 — WatchFiles keeps restarting the server

**Root cause.** There is no server-run configuration in the repository at all. `README.md:45` documents the only
documented start command:

```
uvicorn app.main:app --reload --port 8000
```

With bare `--reload`, uvicorn's WatchFiles backend watches the **entire current working directory tree** (`backend/`).
Because the venv is created inside `backend/` (`README.md:41` → `python -m venv venv`), the watcher also monitors:

* `backend/venv/Lib/site-packages/**`
* `~/.cache/huggingface` only if it is inside the tree, but critically `sentence-transformers` writes
  `modules.json`/lock files and `torch` writes `__pycache__` inside `site-packages` on first import
* every `__pycache__/` directory the app itself generates at import time

The first call to `get_embedding_model()` (`app/services/embedding_service.py:13`) downloads/loads BAAI/bge-m3
(~2.2 GB), which touches thousands of files inside the watched tree → WatchFiles fires → uvicorn kills the worker
mid-request → on restart the next request reloads the model again. This is a self-sustaining restart loop, and it is
also the direct cause of the "embedding model loads multiple times" symptom in Issue 2 and of the interrupted SSE
streams.

**Fix.** Add a committed dev-server entrypoint that sets explicit `reload_dirs` (`app` only) and
`reload_excludes`, plus a documented equivalent CLI invocation. No runtime behaviour changes — this only affects how
the dev server is launched.

---

### Issue 2 — Embedding model loads multiple times

**Root cause (primary).** Issue 1. Each reload wipes the process, so the module-level `_model_instance`
(`embedding_service.py:9`) is discarded and re-created on the next request.

**Root cause (secondary — a real bug in the singleton).** The cache key is the `model_name` argument, and callers
disagree about what that argument is:

| Call site | model_name passed |
|---|---|
| `chat_service.py:360` | `settings.EMBEDDING_MODEL` (`"BAAI/bge-m3"`) |
| `db_query_service.py:311-314` | `settings.EMBEDDING_MODEL` |
| `indexing_service.py:60` → `embed_batch(documents)` | default `DEFAULT_MODEL` |
| `vector_service.py:_get_vector_size` → `get_embedding_dimension()` | default `DEFAULT_MODEL` |

Today `DEFAULT_MODEL == settings.EMBEDDING_MODEL` so the strings match by luck. If an operator ever sets
`EMBEDDING_MODEL` in `.env` to anything else (the setting exists precisely so they can), the `_model_name != model_name`
branch at `embedding_service.py:15` **evicts and re-loads the 2.2 GB model on every alternating call** — search vs.
re-index would thrash the model back and forth.

**Root cause (tertiary).** The model is *never* warmed at startup. `main.py`'s lifespan loads the schema cache and
checks Qdrant but does not touch the embedding model, so the ~20–60 s first-load cost is paid inside the first user
request that hits the vector fallback path.

**Additional stability defect.** `get_embedding_model()` has no lock. Two concurrent requests that both miss the cache
will both construct a `SentenceTransformer`, doubling peak RAM (~4.4 GB) and risking OOM. `example_generator.py` and
`schema_discovery.py` already use the double-checked-locking pattern; the embedding singleton does not.

**Fix.** Make it a genuinely process-wide, thread-safe, warm-on-startup singleton keyed consistently, without changing
the model or the public function signatures (tests in `tests/test_embedding_service.py` patch
`get_embedding_model` and assert `mock_get_model.assert_called_once_with("custom-model")`, so the signature must stay).

---

### Issue 3 — `Vector search fallback failed: name 'db' is not defined`

**Root cause. Confirmed, exact line.**

`backend/app/services/chat_service.py:380`

```python
notice = await format_db_notice(message, "No matching profiles found. ...", history, db, "No matching profiles found.")
```

Inside `ChatService.stream_process_message` the session is `self.db`; there is no local `db`. Verified with a static
check:

```
$ python -m pyflakes app/
app/services/chat_service.py:380:168: undefined name 'db'
```

Two further defects on the same line, independent of the NameError:

1. `format_db_notice(message, notice, history=None, db=None)` takes **four** parameters. The call passes **five**
   positional arguments (`message`, notice, history, db, `"No matching profiles found."`). Even with `db` defined this
   raises `TypeError`. The trailing string is a `_format_notice_safe`-style fallback argument that does not exist on
   `format_db_notice`.
2. The `NameError`/`TypeError` is swallowed by the enclosing `except Exception` at `chat_service.py:376`, which logs
   "Vector search fallback failed" — a **misleading message**, because the vector search actually succeeded and
   returned zero rows. The log has been sending debugging in the wrong direction.

**Effect on users.** Whenever a profile search returns 0 SQL rows *and* 0 vector rows, the intended localized
"no matching profiles" notice is skipped; the outer handler runs `_format_notice_safe` instead. The user-visible text
happens to be similar, but an extra failed code path plus an exception traceback is executed every time, and the
`logger.warning` pollutes the log.

**Fix.** Use `self.db`, call `_format_notice_safe(...)` (which has exactly this 5-arg signature and already
encapsulates the try/except + fallback contract), and make the vector-fallback `except` log the real cause with
`logger.exception`-grade detail while keeping the same user-visible output. Same fix pattern applies to
`db_query_service.py:337-338`, whose `except Exception` around the whole vector block silently hides configuration
errors too.

---

### Issue 4 — Intent analysis ≈ 70 s

`extract_search_params()` (`extraction_service.py:265-350`) is the "intent analysis" stage the timer labels `analyze`.
Measured cost breaks into four independent contributors:

**4a. The prompt is rebuilt from scratch on every single request, and it is enormous.**
`extraction_service.py:295-297`:

```python
dynamic_examples = generate_examples()      # cached — fine
schema_ctx = build_schema_context()         # NOT cached — rebuilt every call
full_prompt = STRUCTURED_EXTRACTION_PROMPT + ... + schema_ctx + ... + dynamic_examples
```

`build_schema_context()` (`schema_discovery.py:163-208`) iterates every table, every column category, and joins up to
50 castes + all religions + 40 cities + 25 educations + 25 occupations + diet/manglik/marital lists into one string, on
every request, for four different call sites (`llm_service.py:39, 62, 81, 112` and `extraction_service.py:296`).
`STRUCTURED_EXTRACTION_PROMPT` alone is 6,512 chars; with schema context the system message is typically **12–20 KB**.
That is pure CPU string work per request *and* it inflates the LLM prompt.

**4b. The whole conversation history is appended to the extraction prompt.**
`extraction_service.py:299-301` extends `messages` with `history`, which `_load_history()` caps at
`CHAT_HISTORY_LIMIT = 30` messages — and those messages include full formatted profile listings from previous turns.
A 30-message history of profile tables is easily 30–60 KB of prompt. Note it is **not** truncated: only the final user
message gets `[:LLM_MESSAGE_TRUNCATION]`.

**4c. The extraction call runs on the heaviest model with a large output budget.**
The task key is `"sql_generation"` (`extraction_service.py:305`), which `commercial_service.py:107-133` seeds to
`llama-3.3-70b-versatile` (or local `qwen2.5:3b` on Ollama). Combined with 4a+4b, a 20–80 KB prompt at 70B is
~10–30 s on Groq and easily 60 s+ on a local Ollama box. `INTENT_MODEL = "llama-3.1-8b-instant"` exists in config but
is unused by this path — that's a business/routing decision I will **not** change.

**4d. Retry amplification.** `AIProvider.retry_count` is seeded from `LLM_MAX_RETRIES = 4`
(`commercial_service.py:38`). On a 429/timeout the gateway sleeps `2**attempt + random()` → up to
1+2+4+8 ≈ 15 s of pure sleep *plus* four full re-sends of the 20 KB prompt. A single rate-limited extraction can alone
account for a 70-second `analyze` stage.

**4e. The cheap tier-2 router never short-circuits the common case.** The TF-IDF router (`extraction_service.py:74-176`)
is fast (<1 ms) but only returns early for `general`. Every `database`-classified message — i.e. every profile
search, the exact case users care about — falls through to the 70 B LLM. That is by design and I am not changing the
routing decision, but it means the only safe levers are: don't rebuild the prompt, don't send megabytes of history,
and don't repeat identical work.

**Optimizations proposed (behaviour-preserving).**

| Change | Why it's safe | Saving |
|---|---|---|
| Memoize `build_schema_context()` behind the existing `_schema_lock`, invalidated by `refresh_cache()` | Output is a pure function of `_schema_cache`, which only changes in `refresh_cache()`. Identical string returned. | 5–40 ms CPU/call ×5 call sites; removes repeated 20 KB allocations |
| Cache the assembled extraction system prompt (prompt + schema + examples) with the same invalidation | Same inputs → byte-identical prompt | 10–50 ms/request |
| Short-lived in-process cache of extraction results keyed by `(normalized message, history fingerprint)` | Identical input → identical LLM output is already assumed (`SQL_TEMPERATURE = 0.0`, deterministic). Cache is opt-in via TTL and bounded. Removes the duplicate extraction that happens when a user retries or when both `/api/chat` and `/api/chat/stream` run the same turn. | Eliminates full 10–70 s duplicate on repeats |
| Reuse a single module-level `httpx.AsyncClient` per (timeout, verify) instead of constructing one per call in `gateway.py:101/211` and `llm_client.py:32/111` | Same requests, same headers, same retries; only the connection pool is shared. Avoids a fresh TLS handshake (~100–300 ms to Groq) on every LLM call, ×4 retries ×3 calls/turn. | 0.3–1.5 s/request |
| Cache `_load_targets()` route lookup for a few seconds | Routes change only via the admin `PUT /routes/{task_key}` endpoint, which can invalidate the cache explicitly. Prevents 2–4 identical SQLite `selectinload` round-trips per turn. | 5–30 ms/request; removes N+1-ish repeated ORM loads |

Expected `analyze`: **70 s → 0.3–3 s** in the LLM-bound case, and **<300 ms whenever the TF-IDF router or the fast
path resolves the message**, which is the target stated in the ticket. The <300 ms goal is only achievable without an
LLM round trip; the existing design already routes greetings/general there, and the extraction cache extends that to
repeated queries. I will **not** add new keyword rules to force more messages down the fast path — that would change
classification behaviour.

---

### Issue 5 — Profile search ≈ 40 s

`analyze` (Issue 4) is included in that number; on top of it:

**5a. The formatting LLM call rebuilds the schema context again** (`llm_service.py:112` inside
`stream_format_db_result`) and again appends the **entire untruncated history** — the same 30 profile-table messages —
in front of the payload. So the same 20–60 KB is serialized and shipped twice per turn.

**5b. No SQL-level N+1, but there is a real query inefficiency.** `build_profile_query()`
(`query_builder.py:83-137`) wraps every predicate in `LOWER(col) = LOWER(%s)` and `LOWER(col) LIKE LOWER(%s)`.
`LOWER(col)` on the left-hand side makes every filter **non-sargable**, so MySQL cannot use an index on
`Gender`/`Caste`/`City`/`Status` and performs a full scan of `register`, then `ORDER BY Regdate DESC`. On a large
`register` table this is seconds, not milliseconds. Fixing this properly requires either functional indexes or relying
on MySQL's default case-insensitive collation — **both change query semantics/DDL, so I am NOT proposing it.** I will
document it as a recommendation and leave the SQL byte-identical.

**5c. Per-query MySQL connection churn.** `_get_pool()` (`db_query_service.py:151-165`) is correct, but if pool
creation ever fails it returns `None` and `_sync_get_connection()` falls back to `mysql.connector.connect(...)` **per
query** — a fresh TCP+auth handshake (`DB_CONNECT_TIMEOUT = 10`) on every single call, forever, because the failed
pool is never retried. Also `pool_size = 5` while `asyncio.to_thread` uses the default executor (up to 32 threads),
so under load threads block on `pool.get_connection()` and silently fall through to unpooled connects.

**5d. `_load_history()` deserializes every message's metadata on every turn.**
`chat_service.py:157-177` loads *all* messages for the conversation (no limit at the SQL level) and `json.loads()`
every `metadata_json` — which contains full `cached_profile_data` and `profile_candidates` blobs — even though only the
newest non-null value of each of the four keys is used. The loop also never breaks once all four are found. For a
50-turn conversation that is 50 JSON parses of multi-KB documents per request.

**Fixes:** shared schema-context cache (5a), retry pool creation with backoff + align pool size (5c), early-exit the
metadata scan once all four keys are resolved (5d). Query text unchanged.

Expected `search`: **40 s → 1–4 s**.

---

### Issue 6 — AI Search ≈ 34 s

The `ai_search` stage is the Qdrant vector fallback (`chat_service.py:353-374`).

**6a. First-call model load inside the request.** `embed_text()` → `get_embedding_model()` → 2.2 GB
`SentenceTransformer(...)` construction. Cold, that is 20–60 s; and because of Issue 1 it is cold *often*. This single
factor explains the bulk of the 34 s.

**6b. `get_client()` is called, then `search_with_filters()` calls `get_client()` again.**
`chat_service.py:356` warms the client, then line 361 calls `search_with_filters(...)` which internally calls
`get_client(host, port)` again (`vector_service.py:165`). Cheap after the first time, but the first call runs
`_ensure_collection()` → a network `get_collections()` round-trip, and `_get_vector_size()` inside it calls
`get_embedding_dimension()` → **loads the embedding model** as a side effect of creating a collection.

**6c. The Qdrant call is fully synchronous and blocks the event loop.**
`search_with_filters()` is a plain `def` calling `client.query_points(...)` with `timeout=120`
(`vector_service.py:32`). It is awaited from an `async` handler with no `asyncio.to_thread`, so a slow Qdrant stalls
**every** concurrent request on the worker, including the SSE heartbeats of other users. `embed_text` correctly uses
`to_thread`; the Qdrant search does not.

**6d. Then a full 70 B formatting call follows** with, again, freshly-rebuilt schema context and untruncated history.

**Fixes:** warm the embedding model at startup (6a), drop the redundant warm-up call and let `search_with_filters` own
the client (6b), run the blocking Qdrant call through `asyncio.to_thread` (6c), shared prompt cache + shared HTTP
client (6d). Result rows, filters, score threshold and ordering are untouched, so search quality is bit-identical.

Expected `ai_search`: **34 s → 0.3–1.5 s** warm.

---

### Issue 7 — Timing logs

**Current state.** `StepTimer` (`core/logger.py:17-51`) exists and is decent, but:

* it is used **only** in `stream_process_message`; the non-streaming `process_message` has no instrumentation at all;
* it covers only 4 coarse labels (`analyze`, `search`, `ai_search`, `format`) — there is nothing for request receipt,
  history/context load, vector search vs. DB search separately, prompt construction, LLM generation, response
  formatting, or DB persistence;
* `timer.log_summary()` is only reached on the success path — a request that throws logs **no timings**, which is
  exactly when you need them;
* the log line has no request id, so concurrent requests interleave unattributably;
* `logger` has no `propagate = False`, so once uvicorn configures the root logger every line is emitted twice.

**Fix.** Extend `StepTimer` with a nestable `stage()` context manager, a request id, and guaranteed emission via
`try/finally`; add the full stage list from the ticket to both `process_message` and `stream_process_message`; add
per-stage timing inside the gateway (LLM generation) and vector/DB services. Logging only — zero effect on responses.

---

## 2. Files to modify

| # | File | Change | Issues |
|---|---|---|---|
| 1 | `backend/run_dev.py` *(new)* | Committed dev entrypoint with `reload_dirs=["app"]` + `reload_excludes` for venv/site-packages/`__pycache__`/`.git`/HF/torch/model caches | 1 |
| 2 | `backend/uvicorn_dev.json` *(new, optional)* or README block | Documents the equivalent CLI flags for people who prefer `uvicorn --reload` | 1 |
| 3 | `README.md` | Update the documented start command to the safe one. Docs only. | 1 |
| 4 | `backend/app/services/embedding_service.py` | Thread-safe double-checked singleton, resolve default from `settings.EMBEDDING_MODEL`, add `warmup_embedding_model()`. Signatures unchanged. | 2, 6 |
| 5 | `backend/app/main.py` | Lifespan: warm embedding model + schema/prompt caches in a thread so startup isn't blocked; register cache invalidation. No route/response changes. | 1, 2, 4, 6 |
| 6 | `backend/app/services/chat_service.py` | Fix line 380 (`db` → `self.db`, wrong arity → `_format_notice_safe`); real exception logging on the vector fallback; early-exit metadata scan; full stage timing in **both** `process_message` and `stream_process_message`; remove the redundant `get_client()` warm-up | 3, 4, 5, 6, 7 |
| 7 | `backend/app/services/db_query_service.py` | Same fallback-logging fix in `_handle_profile_search`; pool creation retry with backoff; pool size aligned to the thread pool; stage timings around DB/vector work | 3, 5, 7 |
| 8 | `backend/app/services/schema_discovery.py` | Memoize `build_schema_context()` under the existing lock; clear it in `refresh_cache()` | 4, 5, 6 |
| 9 | `backend/app/services/extraction_service.py` | Cache the assembled extraction system prompt; bounded TTL cache for extraction results; timing logs. Prompt text, tiers, thresholds and fallbacks unchanged. | 4 |
| 10 | `backend/app/services/llm_service.py` | Use the cached schema context; no prompt text change | 4, 5, 6 |
| 11 | `backend/app/services/vector_service.py` | `search_with_filters` off the event loop via an async wrapper; keep the sync function intact for the existing unit tests; guard `_get_vector_size()` so collection creation doesn't force a model load | 6 |
| 12 | `backend/app/ai/gateway.py` | Shared `httpx.AsyncClient` pool; short-TTL route-target cache with explicit invalidation; LLM-generation timing logs | 4, 5, 6, 7 |
| 13 | `backend/app/ai/llm_client.py` | Shared `httpx.AsyncClient` pool (same retry semantics) | 4, 5, 6 |
| 14 | `backend/app/api/commercial_admin_routes.py` | Call the route-cache invalidator after `PUT /routes/{task_key}` and provider/model mutations | 4 |
| 15 | `backend/app/core/logger.py` | `propagate = False` + idempotent handler; extend `StepTimer` (stage context manager, request id, guaranteed summary). Existing `begin()/end()/log_summary()` API kept for compatibility. | 7 |
| 16 | `backend/app/config.py` | Additive settings only, all defaulting to current behaviour: `RELOAD_EXCLUDES`, `EXTRACTION_CACHE_TTL`, `SCHEMA_CONTEXT_CACHE`, `AI_ROUTE_CACHE_TTL`, `HTTP_POOL_LIMIT`, `TIMING_LOGS` | all |
| 17 | `backend/tests/test_performance_fixes.py` *(new)* | Regression tests: the `db` NameError path, singleton identity under threads, schema-context cache invalidation, extraction prompt stability | 2, 3, 4 |

No changes to: `app/core/prompts.py`, `app/services/query_builder.py`, `app/models/**`, `app/schemas/**`, any
route signature or response body, or any frontend file.

---

## 3. Why each change is required (one line each)

1. **run_dev.py / README** — without explicit excludes, loading the embedding model restarts the server; this is the upstream cause of Issues 1, 2 and half of 6.
2. **embedding_service** — the singleton is not thread-safe and evicts on a model-name mismatch; warm-up moves a 20–60 s cost out of the request path.
3. **main.py lifespan** — one warm-up at boot replaces per-request cold starts.
4. **chat_service:380** — `db` is genuinely undefined *and* the call has the wrong arity; the fallback currently always crashes.
5. **Real exception logging** — "Vector search fallback failed" is currently printed for errors that have nothing to do with vector search.
6. **schema_discovery memoization** — a 20 KB string is rebuilt 5× per request from a cache that changes only at startup.
7. **extraction prompt/result cache** — removes the largest repeated CPU + token cost in the `analyze` stage.
8. **Shared httpx clients** — a new TLS handshake per LLM call, multiplied by 4 retries and 2–3 calls per turn.
9. **Route-target cache** — 2–4 identical ORM `selectinload` queries per turn against SQLite.
10. **Qdrant off the event loop** — a synchronous 120 s-timeout network call inside `async def` blocks every other request.
11. **Pool retry / sizing** — a single transient failure at startup permanently degrades to one raw connect per query.
12. **`_load_history` early exit** — avoids parsing every historical metadata blob on every turn.
13. **Logger propagate + StepTimer** — duplicate lines today, no timings on the error path, no request correlation.

---

## 4. Expected performance

| Stage | Now | After (warm) | Main lever |
|---|---:|---:|---|
| Server restarts during model load | constant | none | reload excludes |
| Embedding model loads | per restart / per request | **1** per process | warm singleton |
| Intent analysis (fast path / router hit) | 70 s | **< 50 ms** | already local; cache removes prompt build |
| Intent analysis (LLM path, cache miss) | 70 s | **1.5–3 s** | prompt cache + no history bloat rebuild + shared client + no retry storm |
| Intent analysis (repeat query, cache hit) | 70 s | **< 20 ms** | extraction TTL cache |
| Profile search (total) | 40 s | **1.5–4 s** | above + pool + metadata scan |
| AI (vector) search | 34 s | **0.3–1.5 s** | warm model + async Qdrant |
| Vector fallback crash rate | 100 % on 0-result searches | **0 %** | Issue 3 fix |
| Duplicate log lines | 2× | 1× | `propagate = False` |

Cold start moves ~30 s of embedding-model load from the first user request into application startup. That is a
deliberate trade: startup is slower and every request afterwards is fast. I will make the warm-up non-blocking so
`/health` still answers immediately.

---

## 5. Risks and how they are contained

* **Extraction result cache** could serve a stale answer if the same message means something different in a new
  context. Contained by keying on message **plus** a fingerprint of the conversation context, keeping the TTL short
  (default 60 s), bounding the size, and making it disableable via config with a default that can be set to `0` if you
  prefer zero caching. **Tell me if you want this one dropped entirely** — everything else is unconditionally safe.
* **Shared httpx client** changes connection reuse, not request content. Retry counts, timeouts, headers and payloads
  stay identical.
* **Warm-up at startup** makes boot slower on a machine without the model cached. Run in a background thread so the
  event loop and `/health` are unaffected, exactly like the existing Qdrant check's failure tolerance.
* **Non-sargable SQL (5b)** is deliberately left alone — fixing it would change query text/indexes.

---

## 6. Verification plan

* `python -m pyflakes app/` → the `undefined name 'db'` finding must disappear.
* `python -m unittest discover backend/tests` → existing 8 test modules must stay green (they mock
  `get_embedding_model`, `get_client`, `safe_query`, so the singleton/async changes must preserve those seams).
* New `tests/test_performance_fixes.py` covering the four regressions listed above.
* Manual: start with `python run_dev.py`, confirm exactly one `Loading embedding model` line, confirm no reload while
  the model loads, run a 0-result profile search and confirm no `Vector search fallback failed` warning.

---

**Approval requested.** Reply with:
* **"approved"** to implement all of the above, or
* **"approved without the extraction cache"** if you'd rather I skip the one item with any behavioural surface, or
* tell me which items to drop.

---

## Implementation outcome (2026-07-31)

The follow-up instruction was to keep the solution simple and avoid over-engineering, so the plan above was cut
down to the changes that fix a verified root cause with the smallest edit.

### Implemented

| Issue | Change | Verified by |
|---|---|---|
| 1 | `backend/run_dev.py` with `reload_dirs=["app"]` | WatchFiles walk root asserted to be `backend/app` only; exclude patterns asserted against uvicorn's own `FileFilter` |
| 2 | Lock + consistent default in `get_embedding_model()`; warm-up at startup | 8 concurrent threads build 1 model (8 without the lock) |
| 3 | `self.db` + `_format_notice_safe()` at `chat_service.py:380`; `logger.exception` | Original log line reproduced at runtime, then confirmed absent |
| 4/5/6 | `build_schema_context()` memoized; redundant `get_client()` removed; `_load_history()` early exit | Cached output byte-identical to uncached; metadata scan result identical |
| 6 | Qdrant search moved off the event loop via `asyncio.to_thread` | 3 → 52 heartbeat ticks during a 0.5 s blocking call |
| 7 | `propagate = False`; `StepTimer` request id, no double-log, emitted on error path; `process_message()` instrumented; LLM latency/prompt size logged | Observed single-emission log lines with full stage breakdown |

### Dropped as over-engineering

Extraction result TTL cache; shared `httpx.AsyncClient` pool; AI route-target cache; six new config settings; a new
async wrapper in `vector_service`; `uvicorn_dev.json`. `asyncio.to_thread` at the two existing call sites replaced
the proposed wrapper.

### Corrections to the analysis above

1. **The MySQL pool claim in 5c was wrong.** `_get_pool()` returns `None` without assigning `_pool` when creation
   fails, so the next call retries. It does *not* degrade permanently. No change was made beyond replacing a silent
   `except: pass` with a debug log.
2. **The schema-context saving in 4a was overestimated.** Measured at ~0.35 ms per call, ~1.7 ms per turn across 5
   call sites — not 5–40 ms. Prompt truncation caps the rendered context near 2.5 KB. The change is still correct
   (it removes genuinely repeated work) but it is not a major lever.

### Honest note on the headline numbers

The 70 s / 40 s / 34 s figures are dominated by the embedding-model reload loop (Issues 1+2) and by LLM round-trip
time. The reload loop is fixed and the model now loads once, which should remove the bulk of the observed latency.
The remaining LLM cost — a 70B model receiving untruncated conversation history — is a routing and prompt-composition
decision that the constraints explicitly placed out of scope, so it was left alone. If the stages are still slow
after this change, the new per-call logs (`LLM task=... prompt_chars=... latency=...ms`) will show exactly where the
time goes, and reducing history sent to the extraction call is the next lever to discuss.
