import json
from app.config import settings
from app.ai.llm_client import call_llm, call_groq
from app.core.logger import logger
from app.core.prompts import BASE_SYSTEM_PROMPT, FORMAT_SYSTEM_PROMPT


def _truncate_payload(payload: dict) -> str:
    truncated_rows = []
    for row in payload.get("rows", []):
        truncated_row = {}
        for key, value in row.items():
            if isinstance(value, str) and len(value) > settings.MAX_FIELD_CHARS:
                truncated_row[key] = value[:settings.MAX_FIELD_CHARS] + "..."
            else:
                truncated_row[key] = value
        truncated_rows.append(truncated_row)

    result = json.dumps({
        "user_question": payload["user_question"],
        "executed_sql": payload["executed_sql"],
        "row_count": payload["row_count"],
        "rows": truncated_rows[:settings.MAX_ROWS_IN_PAYLOAD],
    }, ensure_ascii=False, default=str)

    if len(result) > settings.MAX_PAYLOAD_CHARS:
        result = result[:settings.MAX_PAYLOAD_CHARS] + '"}'

    return result


async def get_general_response(message: str) -> dict:
    return await call_llm(BASE_SYSTEM_PROMPT, message)


async def format_db_result(message: str, sql_result: dict) -> dict:
    payload = {
        "user_question": message,
        "executed_sql": sql_result["sql"],
        "row_count": sql_result["row_count"],
        "rows": sql_result["rows"],
    }
    payload_str = _truncate_payload(payload)
    return await call_groq(
        messages=[
            {"role": "system", "content": FORMAT_SYSTEM_PROMPT},
            {"role": "user", "content": payload_str},
        ],
        temperature=settings.FORMAT_TEMPERATURE,
        max_tokens=settings.FORMAT_MAX_TOKENS,
    )
