from app.config import settings
from app.ai.llm_client import call_groq
from app.ai.intent_detector import is_database_question
from app.core.logger import logger
from app.core.prompts import INTENT_SYSTEM_PROMPT


async def detect_intent_with_llm(message: str) -> bool:
    try:
        result = await call_groq(
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": message[:settings.INTENT_MESSAGE_TRUNCATION]},
            ],
            model=settings.INTENT_MODEL,
            temperature=settings.INTENT_TEMPERATURE,
            max_tokens=settings.INTENT_MAX_TOKENS,
        )
        label = result.get("content", "").strip().lower()
        if label == "database":
            return True
    except Exception as e:
        logger.warning(f"LLM intent detection failed, checking keywords: {e}")

    return is_database_question(message)
