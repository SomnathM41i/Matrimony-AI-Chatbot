from app.ai.llm_client import call_llm, call_groq
from app.core.logger import logger

BASE_SYSTEM_PROMPT = """You are an intelligent AI admin assistant for a matrimony platform.
You have access to a MySQL database with member profiles, membership plans, and site content.
You can answer ANY question freely using your own knowledge.
When the user asks about members, profiles, statistics, or site data, query the database and show results.
Be conversational, smart, and thorough."""

FORMAT_SYSTEM_PROMPT = """
You are an admin database assistant.
Format the SQL result in clear human language.
Be direct. Do not show SQL unless the user asks.
If there are no rows, say no matching records were found.
For profile rows, show a compact numbered list with important fields.
Never invent records or counts that are not in the provided data.
"""


async def get_general_response(message: str) -> str:
    return await call_llm(BASE_SYSTEM_PROMPT, message)


async def format_db_result(message: str, sql_result: dict) -> str:
    payload = {
        "user_question": message,
        "executed_sql": sql_result["sql"],
        "row_count": sql_result["row_count"],
        "rows": sql_result["rows"],
    }
    return await call_groq(
        messages=[
            {"role": "system", "content": FORMAT_SYSTEM_PROMPT},
            {"role": "user", "content": str(payload)},
        ],
        temperature=0.2,
        max_tokens=1400,
    )
