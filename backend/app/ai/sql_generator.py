import json
import re
from app.config import settings
from app.core.constants import SENSITIVE_FIELDS
from app.core.prompts import SQL_GENERATION_SYSTEM_TEMPLATE, DB_SCHEMA_HINT
from app.ai.llm_client import call_groq
from app.ai.gateway import call_ai
from app.core.logger import logger


SQL_GENERATION_SYSTEM = SQL_GENERATION_SYSTEM_TEMPLATE.format(DB_SCHEMA_HINT=DB_SCHEMA_HINT)


def clean_llm_json(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    match = re.search(r'\{.*\}', text, flags=re.DOTALL)
    return match.group(0) if match else text


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


async def generate_sql(message: str, allowed_tables: set, history: list[dict] | None = None, db=None) -> tuple[dict, dict, list[dict]]:
    sql_messages = [{"role": "system", "content": SQL_GENERATION_SYSTEM}]
    if history:
        sql_messages.extend(history)
    sql_messages.append({"role": "user", "content": message})
    if db is not None:
        result = await call_ai(
            db, "sql_generation", messages=sql_messages,
            temperature=settings.SQL_TEMPERATURE, max_tokens=settings.SQL_MAX_TOKENS,
        )
    else:
        result = await call_groq(
            messages=sql_messages,
            temperature=settings.SQL_TEMPERATURE,
            max_tokens=settings.SQL_MAX_TOKENS,
        )
    try:
        parsed = json.loads(clean_llm_json(result["content"]))
    except Exception as e:
        logger.error(f"SQL JSON parse error: {e}; raw={result['content'][:500]}")
        raise ValueError("Could not convert request into a database query.")
    return parsed, result.get("usage", {}), result.get("events", [])
