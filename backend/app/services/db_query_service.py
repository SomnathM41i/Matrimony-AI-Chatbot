import asyncio
import re
import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
from app.config import settings
from app.core.constants import SENSITIVE_FIELDS
from app.core.logger import logger


def validate_select_sql(sql: str, allowed_tables: set) -> str:
    sql = (sql or "").strip()
    sql = re.sub(r'\s+', ' ', sql)
    if sql.endswith(";"):
        sql = sql[:-1].strip()

    lowered = sql.lower()

    blocked_keywords = [
        r'\b(insert|update|delete|drop|alter|truncate|create|replace|grant|revoke|call|exec|load)\b',
        r'/\*', r'--', r'\bmysql_\w+',
        r'\b(unions?)\b',
        r'\binto\s+(outfile|dumpfile)\b',
        r'\binformation_schema\b',
        r'\b(0x[0-9a-f]+)\b',
        r'\bchar\s*\(',
        r'\b(sleep|benchmark|load_file)\s*\(',
    ]
    for pattern in blocked_keywords:
        if re.search(pattern, lowered):
            raise ValueError("Unsafe SQL pattern blocked.")

    if not lowered.startswith("select "):
        raise ValueError("Only SELECT queries are allowed.")
    if ";" in lowered:
        raise ValueError("Only one query is allowed.")

    if re.search(r'\bselect\b.*\bfrom\b.*\bselect\b', lowered, re.DOTALL):
        raise ValueError("Subqueries are not allowed.")

    select_clause = re.split(r'\bfrom\b', lowered, maxsplit=1)[0]
    star_without_count = re.sub(r'\bcount\s*\(\s*\*\s*\)', '', select_clause)
    if re.search(r'(?:\b[a-z_][a-z0-9_]*\s*\.\s*)?\*', star_without_count):
        raise ValueError("Wildcard column selection is not allowed.")

    forbidden_fields = set(SENSITIVE_FIELDS) | {
        "passwordhash", "passcode", "secret", "secret_key", "api_key",
        "token", "refresh_token", "bank_account", "accountnumber",
    }
    referenced_identifiers = set(re.findall(r'\b[a-z_][a-z0-9_]*\b', lowered))
    blocked_fields = sorted(referenced_identifiers & forbidden_fields)
    if blocked_fields:
        raise ValueError("Sensitive database columns are not accessible.")

    referenced_tables = set(re.findall(r'\b(?:from|join)\s+`?([a-zA-Z0-9_]+)`?', lowered))
    if not referenced_tables:
        raise ValueError("No table found in SQL.")
    if not referenced_tables.issubset(allowed_tables):
        blocked = sorted(referenced_tables - allowed_tables)
        allowed = ", ".join(sorted(allowed_tables))
        raise ValueError(f"Access denied to tables: {', '.join(blocked)}. Allowed: {allowed}.")

    if " limit " not in lowered:
        sql += f" LIMIT {settings.SQL_LIMIT}"

    return sql


def sanitize_rows(rows: list[dict]) -> list[dict]:
    clean_rows = []
    for row in rows or []:
        clean = {}
        for key, value in row.items():
            if key.lower() in SENSITIVE_FIELDS or "password" in key.lower():
                continue
            clean[key] = value
        clean_rows.append(clean)
    return clean_rows


_UNKNOWN_PERSONAL_ATTRIBUTES = [
    "favorite food", "favourite food", "favorite dish", "favourite dish",
    "biryani", "pizza", "cuisine", "curry",
    "appetite", "how much does she eat", "how much does he eat",
    "how much can she eat", "how much can he eat", "how much she eat",
    "how much he eat", "eating habit", "cooking habit",
    "daily routine", "wake up", "sleeping",
    "prefer curd", "prefer yogurt", "prefer biryani",
    "favourite biryani", "favorite biryani",
    "what does she like to eat", "what does he like to eat",
    "what food does she like", "what food does he like",
    "kay khate", "kay khato", "aavadta", "आवडता",
    "जेवण", "खाणे", "खाते",
]

_KNOWN_PERSONAL_COLUMNS = {
    "diet", "smoke", "drink", "hobbies", "interests", "aboutmyself",
    "education", "educationdetails", "occupation", "employedin", "annualincome",
    "height", "weight", "bloodgroup", "bodytype", "complexion",
    "familyvalues", "familytype", "familystatus",
    "fathername", "mothersname", "fathersoccupation", "mothersoccupation",
    "noofbrothers", "noofsisters",
    "star", "moonsign", "manglik", "gothram", "language",
    "religion", "caste", "subcaste",
    "city", "dist", "state", "country", "residencystatus",
    "matriid", "name", "age", "gender", "maritalstatus",
    "mobile", "photo1", "partner_expectations",
}


def _message_asks_about_unavailable_attribute(message: str) -> bool:
    msg = message.lower().strip()
    for phrase in _UNKNOWN_PERSONAL_ATTRIBUTES:
        if phrase in msg:
            return True
    return False


class DatabaseQueryError(RuntimeError):
    """Raised when the matrimony database cannot execute a query."""


def _build_connection_args():
    args = {
        "host": settings.DB_HOST,
        "port": settings.DB_PORT,
        "user": settings.DB_USER,
        "password": settings.DB_PASSWORD,
        "database": settings.DB_NAME,
        "connect_timeout": settings.DB_CONNECT_TIMEOUT,
    }
    if settings.DB_SSL_CA:
        args["ssl_ca"] = settings.DB_SSL_CA
    return args


_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        try:
            _pool = MySQLConnectionPool(
                pool_name="mvv_pool",
                pool_size=settings.DB_POOL_SIZE,
                **_build_connection_args(),
            )
        except Exception:
            return None
    return _pool


def _sync_get_connection():
    pool = _get_pool()
    if pool:
        try:
            return pool.get_connection()
        except Exception:
            pass
    return mysql.connector.connect(**_build_connection_args())


def _sync_safe_query(sql: str, params: tuple | None = None, fetch_one: bool = False):
    conn = None
    cur = None
    try:
        conn = _sync_get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params or ())
        return cur.fetchone() if fetch_one else cur.fetchall()
    except Exception as e:
        logger.error(f"DB query error: {e}")
        raise DatabaseQueryError("Database query failed") from e
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def _sync_check_connection() -> bool:
    try:
        conn = _sync_get_connection()
        conn.ping()
        conn.close()
        return True
    except Exception:
        return False


def _add_photo_url(row: dict):
    photo = row.get("Photo1") or ""
    if photo and photo.lower() != "nophoto.jpg":
        row["PhotoURL"] = settings.PHOTO_BASE_URL.rstrip("/") + "/" + photo.lstrip("/")
    else:
        row["PhotoURL"] = ""


def _sync_execute_llm_sql(sql: str) -> dict:
    sql = validate_select_sql(sql, settings.allowed_tables_set)
    rows = _sync_safe_query(sql)
    clean = sanitize_rows(rows or [])
    for row in clean:
        _add_photo_url(row)
    return {
        "sql": sql,
        "rows": clean,
        "row_count": len(rows or []),
    }


async def check_db_connection() -> bool:
    return await asyncio.to_thread(_sync_check_connection)


async def execute_llm_sql(sql: str) -> dict:
    return await asyncio.to_thread(_sync_execute_llm_sql, sql)


def safe_query(sql: str, params: tuple | None = None, fetch_one: bool = False):
    """Synchronous wrapper kept for get_database_stats. Use async functions for new code."""
    return _sync_safe_query(sql, params, fetch_one)


def accumulate_usage(*usages):
    total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for u in usages:
        total["prompt_tokens"] += u.get("prompt_tokens", 0) or 0
        total["completion_tokens"] += u.get("completion_tokens", 0) or 0
        total["total_tokens"] += u.get("total_tokens", 0) or 0
    return total


def _sync_execute_param_query(sql: str, params: list) -> dict:
    rows = _sync_safe_query(sql, tuple(params))
    clean = sanitize_rows(rows or [])
    for row in clean:
        _add_photo_url(row)
    return {
        "sql": sql,
        "rows": clean,
        "row_count": len(rows or []),
    }


async def execute_param_query(sql: str, params: list) -> dict:
    return await asyncio.to_thread(_sync_execute_param_query, sql, params)


async def _format_notice_safe(message: str, notice: str, history, db, fallback: str = "") -> str:
    try:
        from app.services.llm_service import format_db_notice
        result = await format_db_notice(message, notice, history=history, db=db)
        return result.get("content", "") or fallback or notice
    except Exception:
        return fallback or notice


def _merge_filters(accumulated: dict | None, new_filters: dict) -> dict:
    merged = dict(accumulated or {})
    for key, value in new_filters.items():
        if value is not None:
            merged[key] = value
    return merged


def _build_metadata(profile_rows, filters):
    if profile_rows:
        return {
            "profile_candidates": profile_rows,
            "selected_profile": profile_rows[0] if len(profile_rows) == 1 else None,
            "accumulated_filters": filters,
        }
    return {"accumulated_filters": filters}


async def _handle_profile_search(
    message: str, filters: dict, limit: int, history, db
) -> dict:
    from app.services.query_builder import build_profile_query
    from app.services.llm_service import format_db_result

    sql, params = build_profile_query(filters, limit=limit)
    sql_result = await execute_param_query(sql, params)

    profile_rows = [
        {"MatriID": row.get("MatriID"), "Name": row.get("Name")}
        for row in sql_result["rows"]
        if row.get("Name")
    ]
    metadata = _build_metadata(profile_rows, filters)

    if sql_result["row_count"] == 0:
        try:
            from app.services.embedding_service import embed_text, build_profile_document
            from app.services.vector_service import search_with_filters, get_client

            get_client(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

            query_text = build_profile_document(filters)
            query_vector = embed_text(
                f"query: {message}. {query_text}",
                model_name=settings.EMBEDDING_MODEL,
            )
            vector_rows = search_with_filters(
                query_vector,
                filters=filters,
                limit=limit,
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
            )
            if vector_rows:
                for row in vector_rows:
                    _add_photo_url(row)
                vector_result = {
                    "sql": "vector_search",
                    "rows": vector_rows,
                    "row_count": len(vector_rows),
                }
                profile_rows = [
                    {"MatriID": row.get("MatriID"), "Name": row.get("Name")}
                    for row in vector_rows if row.get("Name")
                ]
                metadata = {
                    "profile_candidates": profile_rows,
                    "selected_profile": profile_rows[0] if len(profile_rows) == 1 else None,
                    "accumulated_filters": filters,
                } if profile_rows else {"accumulated_filters": filters}

                try:
                    formatted = await format_db_result(message, vector_result, history=history, db=db)
                except Exception:
                    formatted = {"content": f"Found {len(vector_rows)} matching profiles.", "usage": {}, "events": []}

                return {
                    "content": formatted["content"],
                    "is_profile_search": True,
                    "usage": formatted.get("usage", {}),
                    "events": formatted.get("events", []),
                    "metadata": metadata,
                }
        except Exception as e:
            logger.warning(f"Vector search fallback failed: {e}")

        msg = await _format_notice_safe(
            message,
            "No matching profiles found. Suggest trying a different city, caste, or age range.",
            history, db, "No matching profiles found.",
        )
        return {"content": msg, "is_profile_search": True, "usage": {}, "events": [], "metadata": metadata}

    if sql_result["row_count"] > settings.MAX_ROWS_BEFORE_NARROW:
        msg = await _format_notice_safe(
            message,
            f"The search found {sql_result['row_count']} results, too many to show. Ask the user to add more criteria.",
            history, db,
            f"The search found {sql_result['row_count']} results, too many to show at once. Please add more specific criteria.",
        )
        return {"content": msg, "is_profile_search": True, "usage": {}, "events": [], "metadata": metadata}

    try:
        formatted = await format_db_result(message, sql_result, history=history, db=db)
    except Exception:
        msg = await _format_notice_safe(
            message,
            "Your search returned too many results. Please narrow your search with more specific criteria.",
            history, db,
            "Your search returned too many results for me to process in one go. Please narrow your search.",
        )
        return {"content": msg, "is_profile_search": True, "usage": {}, "events": [], "metadata": metadata}

    return {
        "content": formatted["content"],
        "is_profile_search": True,
        "usage": formatted.get("usage", {}),
        "events": formatted.get("events", []),
        "metadata": metadata,
    }


async def _handle_profile_detail(
    message: str, fields: list[str] | None, limit: int, history, db,
    selected_profile: dict | None = None,
) -> dict:
    from app.services.query_builder import build_detail_query

    matri_id = selected_profile.get("MatriID") if selected_profile else None
    name = selected_profile.get("Name") if selected_profile else None

    if not matri_id and not name:
        msg = await _format_notice_safe(
            message,
            "Which profile would you like details about? Please select one first.",
            history, db,
            "Which profile would you like details about? Please select one first.",
        )
        return {"content": msg, "is_profile_search": False, "usage": {}, "events": [], "metadata": None}

    sql, params = build_detail_query(matri_id=matri_id, name=name, fields=fields, limit=limit)
    sql_result = await execute_param_query(sql, params)

    if not sql_result.get("rows"):
        msg = await _format_notice_safe(message, "Profile not found.", history, db, "Profile not found.")
        return {"content": msg, "is_profile_search": True, "usage": {}, "events": [], "metadata": None}

    from app.services.llm_service import format_db_result

    for row in sql_result["rows"]:
        _add_photo_url(row)

    if _message_asks_about_unavailable_attribute(message):
        msg = await _format_notice_safe(
            message,
            "This information is not available in the database.",
            history, db,
            "This information is not available in the database.",
        )
        return {
            "content": msg,
            "is_profile_search": True, "usage": {}, "events": [],
            "metadata": {"selected_profile": selected_profile, "accumulated_filters": {}},
        }

    try:
        formatted = await format_db_result(message, sql_result, history=history, db=db)
    except Exception:
        formatted = {"content": "Here are the profile details.", "usage": {}, "events": []}

    return {
        "content": formatted["content"],
        "is_profile_search": True,
        "usage": formatted.get("usage", {}),
        "events": formatted.get("events", []),
        "metadata": {
            "selected_profile": selected_profile,
            "accumulated_filters": {},
        },
    }


async def answer_database_question_hybrid(
    message: str,
    history: list[dict] | None = None,
    db=None,
    conversation_context: dict | None = None,
) -> dict:
    from app.services.extraction_service import extract_search_params

    ctx = conversation_context or {}
    accumulated_filters = ctx.get("accumulated_filters")
    selected_profile = ctx.get("selected_profile")

    extraction = await extract_search_params(message, history=history, db=db)
    intent = extraction.get("intent", "general")

    if intent == "profile_detail":
        return await _handle_profile_detail(
            message,
            fields=extraction.get("fields"),
            limit=extraction.get("limit", 1),
            history=history,
            db=db,
            selected_profile=selected_profile,
        )

    if intent != "profile_search":
        return {"content": None, "is_profile_search": False, "usage": {}, "events": [], "metadata": None}

    new_filters = extraction.get("filters", {})
    filters = _merge_filters(accumulated_filters, new_filters)
    limit = extraction.get("limit", 10)

    return await _handle_profile_search(message, filters, limit, history, db)


def get_database_stats() -> dict:
    results = {}
    tables = {
        "total_members": "SELECT COUNT(*) as c FROM register",
        "active_members": "SELECT COUNT(*) as c FROM register WHERE Status='Active'",
        "paid_members": "SELECT COUNT(*) as c FROM register WHERE Status='Paid'",
        "banned_members": "SELECT COUNT(*) as c FROM register WHERE Status='Banned'",
        "male_members": "SELECT COUNT(*) as c FROM register WHERE Gender='Male' AND Status IN ('Active','Paid')",
        "female_members": "SELECT COUNT(*) as c FROM register WHERE Gender='Female' AND Status IN ('Active','Paid')",
        "membership_plans": "SELECT COUNT(*) as c FROM membershipplan",
        "success_stories": "SELECT COUNT(*) as c FROM successstory",
    }
    for key, sql in tables.items():
        row = safe_query(sql, fetch_one=True)
        results[key] = row["c"] if row else 0
    return results
