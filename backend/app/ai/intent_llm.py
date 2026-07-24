import re

from app.config import settings
from app.ai.llm_client import call_groq
from app.ai.gateway import call_ai
from app.ai.intent_detector import is_database_question
from app.core.logger import logger
from app.core.prompts import INTENT_SYSTEM_PROMPT


def is_response_transformation_request(message: str) -> bool:
    """Return True when the user wants the previous answer transformed, not queried again."""
    normalized = " ".join((message or "").lower().split())
    language_names = (
        "marathi", "english", "hindi", "gujarati", "bengali", "punjabi",
        "tamil", "telugu", "kannada", "malayalam", "urdu", "odia",
        "assamese", "nepali", "spanish", "french", "german", "arabic",
    )
    transformation_phrases = (
        "translate", "translation", "say this", "tell me this",
        "explain this", "summarize this", "make it shorter",
        "marathi madhe", "marathit", "मराठीत", "मराठी मध्ये",
        "भाषांतर", "इंग्रजीत", "हिंदी में",
    )
    previous_answer_references = (
        "this", "that", "it", "above", "previous", "response", "answer",
        "हे", "ते", "याचे", "याचा",
    )
    explicitly_names_language = any(
        f"in {language}" in normalized or f"into {language}" in normalized
        for language in language_names
    )
    return (
        (explicitly_names_language or any(phrase in normalized for phrase in transformation_phrases))
        and any(reference in normalized for reference in previous_answer_references)
    )


def is_contextual_database_follow_up(message: str, history: list[dict] | None) -> bool:
    """Recognize profile questions that depend on a person shown earlier."""
    if not history:
        return False

    normalized = " ".join((message or "").lower().split())
    profile_reference_pattern = (
        r"\b(?:he|she|her|him|his|their)\b|"
        r"\b(?:this person|this profile|that profile)\b|"
        r"(?:त्या|तिच|तिला|त्याच|त्याला|यांचा|इनकी|उसकी|उसका)"
    )
    profile_questions = (
        "age", "old", "photo", "picture", "details", "profile", "education",
        "occupation", "job", "income", "height", "city", "location", "caste",
        "religion", "marital", "contact", "phone", "mobile", "name", "show",
        "वय", "फोटो", "माहिती", "शिक्षण", "नोकरी", "उत्पन्न", "उंची",
        "कुठे", "शहर", "जात", "धर्म", "उम्र", "तस्वीर", "जानकारी",
    )
    if not (
        re.search(profile_reference_pattern, normalized) is not None
        and any(term in normalized for term in profile_questions)
    ):
        return False

    recent_assistant_messages = [
        item.get("content", "")
        for item in history[-6:]
        if item.get("role") == "assistant"
    ]
    profile_evidence = (
        "![", "female", "male", "unmarried", "divorced", "profile",
        "महिला", "पुरुष", "प्रोफाइल",
    )
    return any(
        any(evidence in content.lower() for evidence in profile_evidence)
        for content in recent_assistant_messages
    )


async def detect_intent_with_llm(
    message: str,
    history: list[dict] | None = None,
    db=None,
    include_result: bool = False,
):
    if history and is_response_transformation_request(message):
        return False

    try:
        intent_messages = [{"role": "system", "content": INTENT_SYSTEM_PROMPT}]
        if history:
            intent_messages.extend(history)
        intent_messages.append({"role": "user", "content": message[:settings.INTENT_MESSAGE_TRUNCATION]})
        if db is not None:
            result = await call_ai(
                db,
                "intent_detection",
                messages=intent_messages,
                temperature=settings.INTENT_TEMPERATURE,
                max_tokens=settings.INTENT_MAX_TOKENS,
            )
        else:
            result = await call_groq(
                messages=intent_messages,
                model=settings.INTENT_MODEL,
                temperature=settings.INTENT_TEMPERATURE,
                max_tokens=settings.INTENT_MAX_TOKENS,
            )
        label = result.get("content", "").strip().lower()
        decision = label == "database"
        return (decision, result) if include_result else decision
    except Exception as e:
        logger.warning(f"LLM intent detection failed, falling back to keywords: {e}")
        decision = (
            is_contextual_database_follow_up(message, history)
            or is_database_question(message)
        )
        fallback = {"usage": {}, "events": []}
        return (decision, fallback) if include_result else decision
