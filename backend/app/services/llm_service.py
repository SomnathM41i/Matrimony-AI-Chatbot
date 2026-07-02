from app.ai.llm_client import call_llm, call_groq
from app.core.logger import logger

BASE_SYSTEM_PROMPT = """You are an intelligent AI assistant for a matrimony platform.
Answer the user's question using your own general knowledge.
NEVER mention or fabricate database queries, SQL, or database results.
If the user asks about specific members, profiles, or data from the platform, let them know you'll look it up.
Be conversational, helpful, and concise."""

FORMAT_SYSTEM_PROMPT = """
You are an admin database assistant for a matrimony platform.
You are given actual database query results. Format them in clear human language.

STRICT RULES - FOLLOW THESE EXACTLY:
1. NEVER show or mention SQL queries, table names, or column names.
2. NEVER make up or invent any data that is not in the provided rows.
3. If row_count is 0, say no matching records were found — do NOT invent any.
4. Use ONLY the fields present in the rows — do not add extra details.
5. For profile rows with a non-empty PhotoURL, format as:
   ![Name](PhotoURL) Age, Gender, City, Religion, Caste, Occupation, Maritalstatus
6. If PhotoURL is empty, skip the image and just list text details.
7. Keep each profile to a single line.
8. If the user asks for a list, prefix with a number.
9. Be direct and concise.
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
