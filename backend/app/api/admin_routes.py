import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.dependencies import get_db, require_admin
from app.models.user_model import User
from app.models.conversation_model import Conversation
from app.models.chat_model import ChatMessage
from app.services.db_query_service import safe_query, check_db_connection, get_database_stats

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ─── Dashboard Stats ───────────────────────────────────────

@router.get("/stats")
async def stats(admin: User = Depends(require_admin)):
    db_stats = await asyncio.to_thread(get_database_stats)
    return db_stats


# ─── App Users ──────────────────────────────────────────────

@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    offset = (page - 1) * per_page
    query = select(User).order_by(User.id.desc())
    count_query = select(func.count(User.id))

    if search:
        like = f"%{search}%"
        query = query.where(User.name.ilike(like) | User.email.ilike(like))
        count_query = count_query.where(User.name.ilike(like) | User.email.ilike(like))

    total = (await db.execute(count_query)).scalar() or 0
    users = (await db.execute(query.offset(offset).limit(per_page))).scalars().all()

    return {
        "items": [
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
                "is_verified": u.is_verified,
                "conversation_count": 0,
                "last_login": u.last_login.isoformat() if u.last_login else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    allowed = {"role", "is_active", "is_verified"}
    for key, value in body.items():
        if key in allowed:
            setattr(user, key, value)
    await db.flush()
    await db.refresh(user)
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "is_active": user.is_active, "is_verified": user.is_verified}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    await db.delete(user)
    await db.flush()
    return {"success": True}


# ─── Matrimony Profiles ────────────────────────────────────

PROFILE_FIELDS = "MatriID, Name, Age, Gender, Maritalstatus, Religion, Caste, City, Dist, State, Education, Occupation, Annualincome, Height, Mobile, Status, Photo1"

@router.get("/profiles")
async def list_profiles(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    gender: str = Query("", max_length=10),
    status: str = Query("", max_length=20),
    caste: str = Query("", max_length=50),
    city: str = Query("", max_length=100),
    admin: User = Depends(require_admin),
):
    conditions = []
    if search:
        conditions.append(f"(Name LIKE '%{search}%' OR MatriID LIKE '%{search}%' OR Mobile LIKE '%{search}%')")
    if gender:
        conditions.append(f"LOWER(Gender)=LOWER('{gender}')")
    if status:
        conditions.append(f"LOWER(Status)=LOWER('{status}')")
    if caste:
        conditions.append(f"LOWER(Caste)=LOWER('{caste}')")
    if city:
        conditions.append(f"(City LIKE '%{city}%' OR Dist LIKE '%{city}%')")

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    offset = (page - 1) * per_page

    count_sql = f"SELECT COUNT(*) as c FROM register {where}"
    count_row = await asyncio.to_thread(safe_query, count_sql, fetch_one=True)
    total = count_row["c"] if count_row else 0

    data_sql = f"SELECT {PROFILE_FIELDS} FROM register {where} ORDER BY MatriID DESC LIMIT {per_page} OFFSET {offset}"
    rows = await asyncio.to_thread(safe_query, data_sql)

    return {"items": rows or [], "total": total, "page": page, "per_page": per_page}


@router.get("/profiles/{matri_id}")
async def get_profile(matri_id: str, admin: User = Depends(require_admin)):
    sql = f"SELECT * FROM register WHERE MatriID = '{matri_id}'"
    row = await asyncio.to_thread(safe_query, sql, fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    return row


@router.patch("/profiles/{matri_id}/status")
async def update_profile_status(
    matri_id: str,
    body: dict,
    admin: User = Depends(require_admin),
):
    new_status = body.get("status", "").strip()
    if new_status not in ("Active", "Banned", "Paid", "Inactive"):
        raise HTTPException(status_code=400, detail="Invalid status. Use: Active, Banned, Paid, Inactive")
    sql = f"UPDATE register SET Status='{new_status}' WHERE MatriID='{matri_id}'"
    from app.services.db_query_service import _sync_safe_query as sync_query
    conn = None
    try:
        from app.services.db_query_service import _sync_get_connection
        conn = _sync_get_connection()
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        cur.close()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Profile not found")
    finally:
        if conn:
            conn.close()
    return {"success": True, "matri_id": matri_id, "status": new_status}


# ─── Conversations ─────────────────────────────────────────

@router.get("/conversations")
async def list_all_conversations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    offset = (page - 1) * per_page
    query = (
        select(
            Conversation.id,
            Conversation.title,
            Conversation.status,
            Conversation.created_at,
            Conversation.updated_at,
            User.id.label("user_id"),
            User.name.label("user_name"),
            User.email.label("user_email"),
            select(func.count(ChatMessage.id))
            .where(ChatMessage.conversation_id == Conversation.id)
            .correlate(Conversation)
            .scalar_subquery()
            .label("message_count"),
        )
        .join(User, Conversation.user_id == User.id)
        .order_by(Conversation.updated_at.desc())
    )

    count_query = select(func.count(Conversation.id))

    if search:
        like = f"%{search}%"
        query = query.where(User.name.ilike(like) | User.email.ilike(like) | Conversation.title.ilike(like))
        count_query = count_query.join(User, Conversation.user_id == User.id).where(
            User.name.ilike(like) | User.email.ilike(like) | Conversation.title.ilike(like)
        )

    total = (await db.execute(count_query)).scalar() or 0
    rows = (await db.execute(query.offset(offset).limit(per_page))).all()

    return {
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "status": r.status,
                "message_count": r.message_count,
                "user_id": r.user_id,
                "user_name": r.user_name,
                "user_email": r.user_email,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/conversations/{conv_id}")
async def get_conversation_detail(
    conv_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conv_id)
            .order_by(ChatMessage.created_at)
        )
    ).scalars().all()

    return {
        "id": conv.id,
        "title": conv.title,
        "user_id": conv.user_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


# ─── Settings (.env management) ──────────────────────────

def _get_env_path():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent / ".env"

def _read_env() -> dict:
    path = _get_env_path()
    if not path.exists():
        return {}
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip()
    return env

def _write_env(updates: dict):
    path = _get_env_path()
    current = _read_env()
    current.update(updates)
    lines = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if "=" in stripped and not stripped.startswith("#"):
                key = stripped.split("=", 1)[0].strip()
                if key in updates:
                    lines.append(f"{key}={updates[key]}")
                    del updates[key]
                    continue
            lines.append(line)
    for key, val in updates.items():
        if not any(ln.strip().startswith(f"{key}=") for ln in lines):
            lines.append(f"\n{key}={val}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def _mask(val: str, show_front: int = 4, show_back: int = 4) -> str:
    if not val or len(val) <= show_front + show_back + 3:
        return val
    return val[:show_front] + "..." + val[-show_back:]

def _is_masked(val: str) -> bool:
    return "..." in val

SENSITIVE_SETTINGS = {"GROQ_API_KEY", "DB_PASSWORD"}

@router.get("/settings")
async def get_settings(admin: User = Depends(require_admin)):
    env = _read_env()
    mysql_ok = await check_db_connection()
    groq_ok = bool(settings.GROQ_API_KEY)
    return {
        "llm_model": env.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "intent_model": env.get("INTENT_MODEL", "llama-3.1-8b-instant"),
        "llm_api_key": _mask(env.get("GROQ_API_KEY", ""), 6, 4),
        "llm_status": "configured" if groq_ok else "not configured",
        "db_host": env.get("DB_HOST", "localhost"),
        "db_port": int(env.get("DB_PORT", "3306")),
        "db_user": env.get("DB_USER", "root"),
        "db_password": _mask(env.get("DB_PASSWORD", ""), 2, 2),
        "db_name": env.get("DB_NAME", ""),
        "db_status": "connected" if mysql_ok else "unreachable",
    }


@router.put("/settings")
async def update_settings(body: dict, admin: User = Depends(require_admin)):
    env = _read_env()
    updates = {}

    mapping = {
        "llm_model": "GROQ_MODEL",
        "intent_model": "INTENT_MODEL",
        "llm_api_key": "GROQ_API_KEY",
        "db_host": "DB_HOST",
        "db_port": "DB_PORT",
        "db_user": "DB_USER",
        "db_password": "DB_PASSWORD",
        "db_name": "DB_NAME",
    }

    for body_key, env_key in mapping.items():
        val = body.get(body_key)
        if val is None:
            continue
        val_str = str(val).strip()
        if not val_str:
            continue
        if env_key in SENSITIVE_SETTINGS and _is_masked(val_str):
            old_val = env.get(env_key, "")
            if old_val:
                continue
        updates[env_key] = val_str

    if updates:
        _write_env(updates)
        import importlib
        importlib.reload(settings.__class__)
        for k, v in updates.items():
            setattr(settings, k, v)

    mysql_ok = await check_db_connection()
    groq_ok = bool(settings.GROQ_API_KEY)
    return {
        "success": True,
        "llm_model": settings.GROQ_MODEL,
        "intent_model": settings.INTENT_MODEL,
        "llm_api_key": _mask(settings.GROQ_API_KEY, 6, 4),
        "llm_status": "configured" if groq_ok else "not configured",
        "db_host": settings.DB_HOST,
        "db_port": settings.DB_PORT,
        "db_user": settings.DB_USER,
        "db_password": _mask(settings.DB_PASSWORD, 2, 2),
        "db_name": settings.DB_NAME,
        "db_status": "connected" if mysql_ok else "unreachable",
        "restart_required": True,
    }


@router.get("/settings/test-llm")
async def test_llm(admin: User = Depends(require_admin)):
    if not settings.GROQ_API_KEY:
        return {"status": "not configured", "message": "No API key configured"}
    try:
        from app.ai.llm_client import call_groq
        result = await call_groq(
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5,
        )
        return {"status": "connected", "model": settings.GROQ_MODEL}
    except Exception as e:
        return {"status": "failed", "message": str(e)}


@router.get("/settings/test-db")
async def test_db(admin: User = Depends(require_admin)):
    mysql_ok = await check_db_connection()
    return {
        "status": "connected" if mysql_ok else "failed",
    }


# ─── System Health ──────────────────────────────────────────

@router.get("/health")
async def admin_health(admin: User = Depends(require_admin)):
    mysql_ok = await check_db_connection()
    import app.config as app_config
    import app.ai.llm_client as llm_client
    groq_configured = bool(app_config.settings.GROQ_API_KEY)

    return {
        "mysql": "connected" if mysql_ok else "unreachable",
        "groq_api": "configured" if groq_configured else "not configured",
        "app_env": app_config.settings.APP_ENV,
    }
