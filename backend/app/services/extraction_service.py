import json
import re
from app.config import settings
from app.core.prompts import STRUCTURED_EXTRACTION_PROMPT
from app.ai.llm_client import call_groq
from app.ai.gateway import call_ai
from app.core.logger import logger
from app.services.example_generator import generate_examples
from app.services.schema_discovery import build_schema_context

DEFAULT_FILTERS = {
    "gender": None,
    "caste": None,
    "subcaste": None,
    "city": None,
    "dist": None,
    "state": None,
    "age_min": None,
    "age_max": None,
    "religion": None,
    "marital_status": None,
    "education": None,
    "occupation": None,
    "complexion": None,
    "diet": None,
    "manglik": None,
    "gotra": None,
    "income_min": None,
    "income_max": None,
    "height_min": None,
    "height_max": None,
}

PROFILE_KEYWORDS = {
    "profile", "profiles", "member", "members", "bride", "groom",
    "girl", "girls", "boy", "boys", "woman", "women", "man", "men",
    "mulgi", "muli", "मुलगी", "मुली", "महिला",
    "mula", "mule", "मुलगा", "मुले", "पुरुष",
    "वधू", "वर", "प्रोफाइल", "सदस्य",
    "show", "दाखवा", "search", "शोधा",
    "her", "his", "she", "he", "तिचे", "त्याचे", "उसका", "उनका",
    "first", "second", "third", "last", "next", "previous",
    "kundali", "kundli", "dikhao", "dikha", "dikhaye",
    "uski", "unki", "unka", "uska", "meri", "teri",
    "1st", "2nd", "3rd", "match", "find", "looking", "require",
}

DETAIL_KEYWORDS = {
    "her", "his", "she", "he", "this profile", "that profile",
    "tell me more", "tell me about", "details",
    "education", "family", "horoscope", "income", "career",
    "photo", "mobile", "contact", "age", "address",
    "manglik", "gotra", "gothra", "gotram",
    "father", "mother", "brother", "sister", "parent",
    "occupation", "job", "salary", "earning",
    "तिचे", "त्याचे", "उसका", "उनका", "इसके",
    "शिक्षण", "कुटुंब", "भविष्य", "कुंडली",
    "शिक्षा", "परिवार", "कुंडली",
    "uski", "unki", "unka", "uska", "meri", "teri",
    "kundali", "kundli", "dikhao", "dikha", "dikhaye",
    "kya", "kaun", "kaisa", "kaise",
    "kitna", "kitni", "kahan", "kab",
    "biodata", "employed", "height", "weight", "same",
}

VALID_FIELDS = {
    "all", "education", "career", "income", "family",
    "horoscope", "manglik", "gotra", "location",
    "physical", "lifestyle", "photo", "contact",
}

def clean_json(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    match = re.search(r'\{.*\}', text, flags=re.DOTALL)
    return match.group(0) if match else text

def validate_filters(filters: dict) -> dict:
    clean = {}
    for key in DEFAULT_FILTERS:
        value = filters.get(key)
        if value is not None:
            if isinstance(value, str):
                value = value.strip()
                clean[key] = value if value else None
            elif isinstance(value, (int, float)):
                clean[key] = value
            else:
                clean[key] = None
        else:
            clean[key] = None
    return clean

def validate_fields(fields: list | None) -> list[str] | None:
    if not fields:
        return None
    valid = [f for f in fields if isinstance(f, str) and f.lower() in VALID_FIELDS]
    return [f.lower() for f in valid] if valid else None

def _word_in(text: str, word: str) -> bool:
    return bool(re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', text))

def is_likely_profile_message(message: str) -> bool:
    msg = message.lower()
    has_profile = any(_word_in(msg, kw) for kw in PROFILE_KEYWORDS)
    has_community = any(_word_in(msg, kw) for kw in (
        "maratha", "brahmin", "mali", "kunbi", "dhangar",
        "hindu", "muslim", "buddhist", "jain", "christian", "sikh",
        "मराठा", "ब्राह्मण", "माळी", "हिंदू",
        "jat", "जात", "धर्म", "caste", "religion",
        "kuli", "कुळी",
    ))
    has_search_verb = any(
        _word_in(msg, w) for w in [
            "show", "search", "find", "list", "need", "want", "looking",
            "दाखवा", "शोधा", "हवी", "हवे", "पाहिजे",
            "dikhao", "dikha", "dikhaye", "बताओ", "ढूंढो",
        ]
    )
    has_detail = any(_word_in(msg, kw) for kw in DETAIL_KEYWORDS)
    return has_profile or has_community or has_search_verb or has_detail

def _is_detail_query(message: str) -> bool:
    msg = message.lower()
    detail_indicators = 0
    for kw in DETAIL_KEYWORDS:
        if _word_in(msg, kw):
            detail_indicators += 1
    if msg.strip() in ("her", "his", "she", "him", "her profile", "his profile"):
        return True
    first_word = msg.split()[0] if msg.split() else ""
    if first_word in ("her", "his", "she", "he", "this", "that"):
        detail_indicators += 1
        if msg.strip() == first_word:
            return True
    positional = re.search(r'\b(first|second|third|last|next|previous|1st|2nd|3rd)\b', msg)
    if positional:
        detail_indicators += 1
    return detail_indicators >= 1

async def extract_search_params(
    message: str,
    history: list[dict] | None = None,
    db=None,
) -> dict:
    msg_clean = message.lower().strip().rstrip(".!?,")
    
    # Tier 1: Heuristic Fast-Path (Greetings & Trivial conversation)
    FAST_PATH_GENERAL = {
        "hi", "hello", "hey", "namaste", "नमस्कार", "नमस्ते", "हॅलो", "namaskar",
        "good morning", "good afternoon", "good evening",
        "yes", "no", "thanks", "thank you", "ok", "okay", "bye", "goodbye",
        "fine", "sure", "not really", "आभार", "धन्यवाद", "ठीक आहे", "thank",
        "great", "awesome", "cool", "perfect"
    }
    if msg_clean in FAST_PATH_GENERAL:
        return {"intent": "general", "filters": {}, "limit": 10, "selected_index": None, "selected_reference": None}

    # Tier 2: Zero-Memory Lexical & Keyword Routing (Bypasses LLM for unrelated general topics)
    if not is_likely_profile_message(message) and not _is_detail_query(message):
        # High confidence that this is completely unrelated general conversation - bypass LLM completely!
        return {"intent": "general", "filters": {}, "limit": 10, "selected_index": None, "selected_reference": None}

    # Tier 3: External LLM Structured Parameter Extraction
    dynamic_examples = generate_examples()
    schema_ctx = build_schema_context()
    full_prompt = STRUCTURED_EXTRACTION_PROMPT + "\n\n### LIVE SCHEMA CONTEXT ###\n" + schema_ctx + "\n\n" + dynamic_examples
    messages = [{"role": "system", "content": full_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message[:settings.LLM_MESSAGE_TRUNCATION]})

    try:
        if db is not None:
            result = await call_ai(
                db, "sql_generation", messages=messages,
                temperature=settings.SQL_TEMPERATURE, max_tokens=settings.SQL_MAX_TOKENS,
            )
        else:
            result = await call_groq(
                messages=messages,
                temperature=settings.SQL_TEMPERATURE,
                max_tokens=settings.SQL_MAX_TOKENS,
            )
        raw = result.get("content", "")
        parsed = json.loads(clean_json(raw))
    except Exception as e:
        logger.warning(f"Extraction failed, using keyword fallback: {e}")
        if _is_detail_query(message):
            return {"intent": "profile_detail", "filters": {}, "fields": ["all"], "limit": 1, "selected_index": None, "selected_reference": None}
        return {"intent": "profile_search", "filters": _keyword_fallback(message), "limit": 10, "selected_index": None, "selected_reference": None}

    intent = parsed.get("intent", "profile_search")
    if intent not in ("profile_search", "profile_detail"):
        return {
            "intent": "general",
            "filters": {},
            "limit": 10,
            "selected_index": parsed.get("selected_index"),
            "selected_reference": parsed.get("selected_reference"),
        }

    raw_filters = parsed.get("filters", {})
    filters = validate_filters(raw_filters)
    fields = validate_fields(parsed.get("fields"))

    limit = parsed.get("limit", 10)
    if not isinstance(limit, int) or limit < 1:
        limit = 10
    if limit > 50:
        limit = 50

    return {
        "intent": intent,
        "filters": filters,
        "fields": fields,
        "limit": limit,
        "selected_index": parsed.get("selected_index"),
        "selected_reference": parsed.get("selected_reference"),
    }

def _keyword_fallback(message: str) -> dict:
    msg = message.lower()
    filters = {}

    if any(kw in msg for kw in ["female", "girl", "woman", "महिला", "मुलगी", "मुली", "स्त्री", "वधू", "ladki"]):
        filters["gender"] = "Female"
    elif any(kw in msg for kw in ["male", "boy", "man", "पुरुष", "मुलगा", "मुले", "वर", "ladka"]):
        filters["gender"] = "Male"

    for caste_keyword in ["maratha", "brahmin", "mali", "kunbi", "dhangar"]:
        if caste_keyword in msg:
            filters["caste"] = caste_keyword.title()
            break

    city_match = re.search(r'(?:^|\s)(?:in|at|from)\s+([A-Za-z\u0900-\u097F]{3,})', msg)
    if not city_match:
        city_match = re.search(r'([A-Za-z\u0900-\u097F]{3,})\s+(?:मध्ये|में|का|की|ची|चा)', msg)
    if city_match:
        filters["city"] = city_match.group(1).capitalize()

    return filters