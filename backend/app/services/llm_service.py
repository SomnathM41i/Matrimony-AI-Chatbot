import json
from app.config import settings
from app.ai.llm_client import call_llm, call_groq
from app.ai.gateway import call_ai
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


async def get_general_response(message: str, history: list[dict] | None = None, db=None) -> dict:
    current_message = (
        "CURRENT USER MESSAGE (detect language from this text; history is context only):\n"
        + message
    )
    if db is None:
        return await call_llm(BASE_SYSTEM_PROMPT, current_message, history=history)
    messages = [{"role": "system", "content": BASE_SYSTEM_PROMPT[:settings.LLM_PROMPT_TRUNCATION]}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": current_message[:settings.LLM_MESSAGE_TRUNCATION]})
    return await call_ai(db, "general_chat", messages, max_tokens=settings.DEFAULT_MAX_TOKENS)


async def format_db_result(message: str, sql_result: dict, history: list[dict] | None = None, db=None) -> dict:
    payload = {
        "user_question": message,
        "language_instruction": (
            "Reply in the language of user_question, unless user_question explicitly "
            "requests a different target language."
        ),
        "executed_sql": sql_result["sql"],
        "row_count": sql_result["row_count"],
        "rows": sql_result["rows"],
    }
    payload_str = _truncate_payload(payload)
    fmt_messages = [{"role": "system", "content": FORMAT_SYSTEM_PROMPT}]
    if history:
        fmt_messages.extend(history)
    fmt_messages.append({"role": "user", "content": payload_str})
    if db is not None:
        return await call_ai(
            db, "database_formatting", messages=fmt_messages,
            temperature=settings.FORMAT_TEMPERATURE, max_tokens=settings.FORMAT_MAX_TOKENS,
        )
    return await call_groq(messages=fmt_messages, temperature=settings.FORMAT_TEMPERATURE, max_tokens=settings.FORMAT_MAX_TOKENS)


async def format_db_notice(message: str, notice: str, history: list[dict] | None = None, db=None) -> dict:
    """Translate a database status notice without changing its meaning."""
    system_prompt = (
        "You are myvivahai's multilingual assistant. Rewrite the supplied NOTICE as a "
        "short, warm response in the language of the CURRENT USER MESSAGE. If the user "
        "explicitly requests another target language, use that language. Do not add facts, "
        "profiles, or database details. Return only the response."
    )
    current_message = f"CURRENT USER MESSAGE:\n{message}\n\nNOTICE:\n{notice}"
    if db is None:
        return await call_llm(system_prompt, current_message, history=history)
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": current_message})
    return await call_ai(db, "database_notice", messages, max_tokens=settings.DEFAULT_MAX_TOKENS)
