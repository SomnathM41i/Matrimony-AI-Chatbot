# Deployment Runbook — P11 (Hostinger KVM2 VPS)

Target: **Hostinger KVM2 VPS (2GB RAM)** running the MyVivahAI backend (FastAPI)
+ frontend static build. MySQL matrimony DB is read-only; Qdrant + app live on the
same VPS. Verify each phase before moving on; roll back by reverting to the previous
release tag and restarting.

---

## 0. Preflight (on the VPS)

```bash
# Ubuntu 22.04/24.04 assumed
sudo apt update && sudo apt -y install python3.12 python3.12-venv git nginx
python3.12 --version
```

Clone the repo and create the venv:

```bash
git clone <repo-url> myvivahai
cd myvivahai
git checkout <release-tag>          # tag of the release you are deploying
cd backend
python3.12 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

## 1. Environment (backend/.env)

Copy the existing `.env` (live credentials are NOT committed) and confirm every
var below. Non-negotiable values in bold.

```ini
APP_ENV=production
SECRET_KEY=<long-random-string>
DATABASE_URL=sqlite+aiosqlite:///./storage/chatbot.db

# Identity / consultant persona (CF-0)
ASSISTANT_NAME=MyVivahAI
PLATFORM_NAME=Dishavadhuvar

# MatriID gate (CF-1): soft = welcome once then guest browsing
MATRI_ID_GATE_MODE=soft
# Search-early (CF-3)
ONBOARDING_SEARCH_STRATEGY=gender_plus_core

# LLM provider (choose one)
LLM_PROVIDER=groq
GROQ_API_KEY=<key>
# or LLM_PROVIDER=cerebras / gemini with the matching *_API_KEY

# Read-only matrimony MySQL
DB_HOST=<mysql-host>
DB_PORT=3306
DB_USER=<readonly-user>
DB_PASSWORD=<readonly-password>
DB_NAME=<matrimony-db>

# Qdrant (same VPS)
QDRANT_HOST=localhost
QDRANT_PORT=6333
# bge-m3 needs 4-6GB RAM; KVM2 has 2GB — see §4 BEFORE enabling vector search.
VECTOR_FALLBACK_ENABLED=True

# CDN/origin for profile photos (verified: .in = hcdn CDN, .com = LiteSpeed origin)
PHOTO_BASE_URL=https://dishavadhuvar.in/gallary/

# CORS + frontend
FRONTEND_URL=https://<app-domain>
CORS_ORIGINS=https://<app-domain>
BACKEND_URL=https://<api-domain-or-ip>
```

## 2. Start Qdrant

```bash
# Qdrant binary (NOT Docker) — ~50-100MB RSS
curl -L -o qdrant https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-gnu.tar.gz
tar -xzf qdrant*.tar.gz && ./qdrant --http-port 6333
# Persist config/snapshots under ./storage/qdrant
```

## 3. First boot + schema + reindex

Startup (`app.main.lifespan`) auto-creates/migrates the SQLite tables and refreshes
the schema cache, so the app itself is enough for normal boot:

```bash
./venv/bin/python -c "from app.database import create_tables; import asyncio; asyncio.run(create_tables())"
```

Load profiles into Qdrant **once** (skipped safely if already indexed; only if
`VECTOR_FALLBACK_ENABLED=True`):

```bash
./venv/bin/python reindex_profiles.py
```

> bge-m3 downloads ~2.2GB on first run; pre-download on the VPS before going live.

## 4. Memory plan for KVM2 (2GB) — READ THIS

- `BAAI/bge-m3` needs **4-6GB** for live CPU inference (ISSUES.md). On KVM2 the
  safe choices are:
  - **A. Leave vector fallback on, accept swap** (risky) — the app loads the model
    per vector search and calls `unload_embedding_model()` after the reply, so it is
    only resident during a fallback search. Acceptable for low traffic.
  - **B. `VECTOR_FALLBACK_ENABLED=False`** — MySQL-first only; deterministic
    structured search covers most queries. Recommended if KVM2 stays at 2GB.
  - **C. Upgrade to KVM4 (4GB)** — cleanest; bge-m3 fits comfortably.
- Monitor: `free -h`, `systemctl status myvivahai`.

## 5. Run the API

```bash
# systemd unit (recommended) — /etc/systemd/system/myvivahai.service
[Unit]
Description=MyVivahAI API
After=network.target

[Service]
WorkingDirectory=/opt/myvivahai/backend
ExecStart=/opt/myvivahai/backend/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
EnvironmentFile=/opt/myvivahai/backend/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now myvivahai
sudo journalctl -u myvivahai -f     # watch startup logs
curl -s localhost:8000/health
```

## 6. Frontend

```bash
cd frontend
npm ci
npm run build          # emits dist/
# Serve dist/ via nginx (or copy to the API host /var/www/myvivahai)
```

nginx snippet:

```nginx
server {
    server_name <app-domain>;
    root /var/www/myvivahai;
    index index.html;
    location /api/ { proxy_pass http://127.0.0.1:8000; proxy_http_version 1.1;
        proxy_buffering off;      # SSE streaming
        proxy_read_timeout 300s; }
    location / { try_files $uri $uri/ /index.html; }
}
```

## 7. Verify deployment (automated)

From the VPS (or a machine that can reach `localhost:8000`):

```bash
cd backend
./venv/bin/python -m tests.test_acceptance     # live smoke: health, chat, auth, SSE
./venv/bin/python -m tests.eval_harness        # offline rubric: Marathi-first, routing,
                                               # zero-hallucination, deterministic biodata
```

Both exit 0 only when every check passes.

Manual smoke (authenticated):
1. Register/login, confirm cookie auth works (`/api/auth/me`).
2. Send a bare MatriID (e.g. `ES92669`) → auto-link + profile/PE summary + questionnaire.
3. Finish the questionnaire → profile search with photo cards.
4. Click a suggestion chip (e.g. "मागील सर्च चालू ठेवा", a biodata section chip) →
   deterministic reply, no LLM, follow-up chips present.
5. Type a profile keyword with no DB match → honest "सापडली नाही" + सल्ला (no
   fabricated profiles).
6. Open a second browser tab with the same user → "परत स्वागत!" welcome-back.

## 8. Rollback

- Backend: checkout the previous release tag, restart the service:
  `git checkout <prev-tag> && sudo systemctl restart myvivahai`.
- Frontend: rebuild/restore the previous `dist/`.
- SQLite DB: back up `backend/storage/chatbot.db` before each deploy
  (`cp chatbot.db chatbot.db.$(date +%F)`). Schema changes are additive/auto-migrated.
- Qdrant: reindex is idempotent (`reindex_profiles.py` only upserts).

## 9. Post-deploy checklist

- [ ] `/health` returns 200 with `status`
- [ ] Acceptance + eval harness both exit 0
- [ ] MatriID auto-link works against live MySQL (read-only)
- [ ] Questionnaire completes and saves preferences
- [ ] Profile search renders photo cards from `.in` CDN
- [ ] Suggestion chips + biodata sections render without LLM latency
- [ ] No-match replies never fabricate profiles
- [ ] `free -h` stable under load (watch bge-m3 if vector fallback is on)
- [ ] Live provider smoke: admin model/route health after secrets installed
      (ISSUES.md "Live provider integration" — requires staging creds)
- [ ] Payment-gateway adapter still blocked on business choice (ISSUES.md)

## Known constraints / open items feeding this runbook

- `ISSUES.md`: live provider integration (secrets/staging), payment adapter (blocked).
- bge-m3 memory on KVM1/2 (see §4).
- MySQL remains strictly read-only; `register`/`saveandsearch` tables are queried via
  parameterized `execute_param_query` only.
