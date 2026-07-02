import mysql.connector
from app.config import settings
from app.core.logger import logger
from app.ai.sql_generator import generate_sql, validate_select_sql, sanitize_rows
from app.core.constants import DB_SCHEMA_HINT


def get_mysql_connection():
    return mysql.connector.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        connect_timeout=settings.DB_CONNECT_TIMEOUT,
    )


def safe_query(sql: str, params: tuple | None = None, fetch_one: bool = False):
    try:
        conn = get_mysql_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params or ())
        row = cur.fetchone() if fetch_one else cur.fetchall()
        cur.close()
        conn.close()
        return row
    except Exception as e:
        logger.error(f"DB query error: {e}")
        return None


def check_db_connection() -> bool:
    try:
        conn = get_mysql_connection()
        conn.ping()
        conn.close()
        return True
    except Exception:
        return False


def execute_llm_sql(sql: str) -> dict:
    sql = validate_select_sql(sql, settings.allowed_tables_set)
    rows = safe_query(sql)
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


async def answer_database_question(message: str) -> str:
    plan = await generate_sql(message, settings.allowed_tables_set)
    if not plan.get("needs_database", True):
        return plan.get("answer_without_database", "")
    sql_result = execute_llm_sql(plan.get("sql", ""))
    from app.services.llm_service import format_db_result
    return await format_db_result(message, sql_result)


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
