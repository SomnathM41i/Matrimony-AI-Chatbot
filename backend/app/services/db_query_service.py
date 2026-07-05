import asyncio
import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
from app.config import settings
from app.core.logger import logger
from app.ai.sql_generator import generate_sql, validate_select_sql, sanitize_rows
from app.ai.llm_client import GroqPayloadTooLargeError


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
    try:
        conn = _sync_get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params or ())
        row = cur.fetchone() if fetch_one else cur.fetchall()
        cur.close()
        conn.close()
        return row
    except Exception as e:
        logger.error(f"DB query error: {e}")
        return None


def _sync_check_connection() -> bool:
    try:
        conn = _sync_get_connection()
        conn.ping()
        conn.close()
        return True
    except Exception:
        return False


def _sync_execute_llm_sql(sql: str) -> dict:
    sql = validate_select_sql(sql, settings.allowed_tables_set)
    rows = _sync_safe_query(sql)
    clean = sanitize_rows(rows or [])
    for row in clean:
        photo = row.get("Photo1") or ""
        if photo and photo.lower() != "nophoto.jpg":
            row["PhotoURL"] = settings.PHOTO_BASE_URL.rstrip("/") + "/" + photo.lstrip("/")
        else:
            row["PhotoURL"] = ""
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


async def answer_database_question(message: str) -> dict:
    sql_plan, sql_usage = await generate_sql(message, settings.allowed_tables_set)
    if not sql_plan.get("needs_database", True):
        return {"content": sql_plan.get("answer_without_database", ""), "usage": sql_usage}
    sql_result = await execute_llm_sql(sql_plan.get("sql", ""))

    if sql_result["row_count"] > settings.MAX_ROWS_BEFORE_NARROW:
        return {
            "content": (
                f"I found {sql_result['row_count']} results, which is too many to show at once. "
                "Please narrow your search by adding more specific criteria."
            ),
            "usage": sql_usage,
        }

    from app.services.llm_service import format_db_result
    try:
        formatted = await format_db_result(message, sql_result)
    except GroqPayloadTooLargeError:
        return {
            "content": (
                "Your search returned too many results for me to process in one go. "
                "Please narrow your search by adding more specific criteria."
            ),
            "usage": sql_usage,
        }
    return {
        "content": formatted["content"],
        "usage": accumulate_usage(sql_usage, formatted.get("usage", {})),
    }


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
