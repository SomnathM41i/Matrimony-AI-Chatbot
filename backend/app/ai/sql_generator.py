import json
import re
from app.core.constants import DB_SCHEMA_HINT, SENSITIVE_FIELDS
from app.ai.llm_client import call_groq
from app.core.logger import logger


SQL_GENERATION_SYSTEM = f"""
You are the intent-and-SQL planner for an admin database assistant.
First understand what the user is asking for, then generate a safe MySQL SELECT query for that intent.
Return ONLY JSON in this exact shape:
{{"needs_database": true, "intent": "profile_search|agent_report|plans|stats|support|success_story|cms_content|general", "intent_summary": "short plain-English summary", "sql": "SELECT ...", "answer_without_database": ""}}

Rules:
- Always identify the user's intent before writing SQL.
- Use the intent to choose the correct table.
- Generate exactly one SELECT query.
- Use only the tables and columns listed in the schema.
- Never select password fields or sensitive login fields.
- Do not use SELECT *.
- Select enough columns for an admin to understand the record.
- For member/profile lists select MatriID, Name, Age, Gender, Maritalstatus, Religion, Caste, City, Dist, State, Education, Occupation, Annualincome, Height, Mobile, Status, Photo1.
- Photo1 contains the profile photo filename. The system automatically prepends the PHOTO_BASE_URL to create the full photo URL.
- For agent lists select agent_id, full_name, mobile, email, city, state, pincode, joining_date, status.
- For agent sales select sale_id, sale_reference, customer_name, customer_mobile, agent_id, plan_name, plan_amount, payment_status, sale_status, sale_date.
- If the user asks for a list, include a LIMIT.
- For location, search City OR Dist OR State with LIKE.
- For gender, use LOWER(Gender)=LOWER('Female') or LOWER(Gender)=LOWER('Male').
- If the user asks about a specific person by name, search Name LIKE '%searchterm%'.
- If the user asks "tell me about X" or "who is X", treat X as a name search.
- If no database is needed, return needs_database false, intent general, sql empty, and put the normal answer in answer_without_database.

{DB_SCHEMA_HINT}
""".strip()


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
    if not lowered.startswith("select "):
        raise ValueError("Only SELECT queries are allowed.")
    if ";" in sql:
        raise ValueError("Only one query is allowed.")
    if re.search(
        r'\b(insert|update|delete|drop|alter|truncate|create|replace|grant|revoke|call|exec|load)\b',
        lowered
    ):
        raise ValueError("Unsafe SQL command blocked.")

    referenced_tables = set(re.findall(r'\b(?:from|join)\s+`?([a-zA-Z0-9_]+)`?', lowered))
    if not referenced_tables:
        raise ValueError("No table found in SQL.")
    if not referenced_tables.issubset(allowed_tables):
        blocked = sorted(referenced_tables - allowed_tables)
        allowed = ", ".join(sorted(allowed_tables))
        raise ValueError(f"Access denied to tables: {', '.join(blocked)}. Allowed: {allowed}.")

    if " limit " not in lowered:
        sql += " LIMIT 20"

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


async def generate_sql(message: str, allowed_tables: set) -> tuple[dict, dict]:
    result = await call_groq(
        messages=[
            {"role": "system", "content": SQL_GENERATION_SYSTEM},
            {"role": "user", "content": message},
        ],
        temperature=0,
        max_tokens=900,
    )
    try:
        parsed = json.loads(clean_llm_json(result["content"]))
    except Exception as e:
        logger.error(f"SQL JSON parse error: {e}; raw={result['content'][:500]}")
        raise ValueError("Could not convert request into a database query.")
    return parsed, result.get("usage", {})
