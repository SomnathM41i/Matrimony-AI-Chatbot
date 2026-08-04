"""Helpers to drive the rule-based partner-preference questionnaire
conversationally inside the chat (Marathi/Hinglish answers, zero LLM)."""

import re

from app.core.questionnaire import ANY, CUSTOM

_DIGIT_TRANSLATION = str.maketrans("०१२३४५६७८९", "0123456789")

_ANY_LIKE = ("कोणतीही", "कोणतेही", "कोणताही", "पसंती नाही", "any", "सर्व", "नको", "skip")
_SKIP_LIKE = ("कोणतीही", "कोणतेही", "कोणताही", "पसंती नाही", "any", "सर्व", "नको", "skip", "नाही", "वगळा")

_GENDER_SYNONYMS = {
    "female": ["मुलगी", "मुली", "स्त्री", "महिला", "female", "girl", "ladki", "वधू", "औरत"],
    "male": ["मुलगा", "मुले", "पुरुष", "पुरूष", "male", "boy", "ladka", "वर", "आदमी"],
}

_MARITAL_SYNONYMS = {
    "unmarried": ["कधीही लग्न", "unmarried", "never married", "लग्न नाही", "अविवाहित", "single"],
    "divorced": ["घटस्फोट", "divorced", "divorce"],
    "widowed": ["विधवा", "widow"],
    "widower": ["विधुर", "widower"],
}

_RELIGION_SYNONYMS = {
    "hindu": ["हिंदू", "हिन्दू", "हिंदु", "hindu"],
    "muslim": ["मुस्लिम", "मुसलमान", "muslim", "islam"],
    "christian": ["ख्रिश्चन", "ख्रिस्ती", "christian"],
    "sikh": ["शीख", "sikh"],
    "jain": ["जैन", "jain"],
    "buddhist": ["बौद्ध", "buddhist"],
}

_MANGLIK_SYNONYMS = {
    "yes": ["मांगलिक", "मंगलिक", "manglik", "yes", "होय", "हो"],
    "no": ["अमांगलिक", "अमंगलिक", "non", "no", "नाही"],
}

_COMPLEXION_SYNONYMS = {
    "very_fair": ["अतिशय गोरा", "very fair"],
    "wheatish_medium": ["गहूवर्णी मध्यम", "wheatish medium"],
    "fair": ["गोरा", "fair", "गोरी"],
    "wheatish": ["गहूवर्णी", "wheatish"],
    "dark": ["सावळा", "dark", "काळा"],
}

_CONFIRM_SYNONYMS = {
    "keep": ["keep", "कायम", "ठेवा", "ठीक", "होय", "हो", "yes"],
    "change": ["change", "बदला", "बदल"],
    "skip": ["skip", "वगळा", "नको", "नाही", "no"],
}


def first_name(name: str | None) -> str:
    if not name:
        return ""
    parts = name.strip().split()
    return parts[0] if parts else ""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").translate(_DIGIT_TRANSLATION).strip().lower())


def _numbers_in(text: str) -> list[int]:
    return [int(n) for n in re.findall(r"\d+", text)]


def _contains_any(text: str, keywords) -> bool:
    return any(k in text for k in keywords)


def _find_option(node: dict, option_id: str) -> dict | None:
    for option in node.get("options", []):
        if option["id"] == option_id:
            return option
    return None


def _option_by_index(node: dict, message: str) -> dict | None:
    text = message.strip().translate(_DIGIT_TRANSLATION)
    options = node.get("options", [])
    if text.isdigit() and 1 <= int(text) <= len(options):
        return options[int(text) - 1]
    return None


def _match_by_keywords(node: dict, text: str, synonyms: dict) -> dict | None:
    for option_id, keywords in synonyms.items():
        if _contains_any(text, keywords):
            option = _find_option(node, option_id)
            if option is not None:
                return option
    return None


def _match_age_range(node: dict, text: str) -> dict | None:
    nums = _numbers_in(text)
    if not nums:
        return None
    for option in node.get("options", []):
        if option["id"] == ANY:
            continue
        amin = option.get("filters", {}).get("age_min")
        amax = option.get("filters", {}).get("age_max")
        if amin is None and amax is None:
            continue
        try:
            if len(nums) >= 2:
                low, high = min(nums), max(nums)
                if amin is not None and amax is not None and int(amin) == low and int(amax) == high:
                    return option
            else:
                n = nums[0]
                if amin is not None and int(amin) <= n <= int(amax or "999"):
                    return option
        except (TypeError, ValueError):
            continue
    return None


def _match_by_label(node: dict, text: str) -> dict | None:
    if not text:
        return None
    for option in node.get("options", []):
        label = _normalize(option.get("label", ""))
        if not label:
            continue
        if label in text or text in label:
            return option
    return None


def parse_answer(node: dict, message: str) -> dict | None:
    """Map a free-text chat answer to a questionnaire answer dict.

    Returns {"node_id", "option_id"} or {"node_id", "option_id": "custom",
    "value"} or None when the answer cannot be recognized."""
    node_id = node["id"]
    node_type = node.get("type")
    text = _normalize(message)
    if not text:
        return None

    numbered = _option_by_index(node, message)
    if numbered is not None:
        return {"node_id": node_id, "option_id": numbered["id"]}

    if node_type == "confirm":
        option = _match_by_keywords(node, text, _CONFIRM_SYNONYMS)
        return {"node_id": node_id, "option_id": option["id"]} if option else None

    if node_type == "text":
        preset = _match_by_label(node, text)
        if preset is not None:
            return {"node_id": node_id, "option_id": preset["id"]}
        if _contains_any(text, _SKIP_LIKE):
            option = _find_option(node, ANY)
            if option is not None:
                return {"node_id": node_id, "option_id": option["id"]}
        return {"node_id": node_id, "option_id": CUSTOM, "value": message.strip()}

    if _contains_any(text, _ANY_LIKE):
        option = _find_option(node, ANY)
        if option is not None:
            return {"node_id": node_id, "option_id": option["id"]}

    category = node.get("category")
    synonyms = {
        "gender": _GENDER_SYNONYMS,
        "marital_status": _MARITAL_SYNONYMS,
        "religion": _RELIGION_SYNONYMS,
        "manglik": _MANGLIK_SYNONYMS,
        "complexion": _COMPLEXION_SYNONYMS,
    }.get(category)
    if synonyms:
        option = _match_by_keywords(node, text, synonyms)
        if option is not None:
            return {"node_id": node_id, "option_id": option["id"]}

    if category == "age_range":
        option = _match_age_range(node, text)
        if option is not None:
            return {"node_id": node_id, "option_id": option["id"]}

    return _match_by_label(node, text)


def format_question(node: dict, index: int | None = None, total: int | None = None) -> str:
    lines = []
    if index is not None and total:
        lines.append(f"प्रश्न {index}/{total}")
    lines.append(node.get("question", ""))
    for i, option in enumerate(node.get("options", []), start=1):
        lines.append(f"{i}. {option['label']}")
    lines.append("(पर्यायावर क्लिक करा किंवा थेट मजकूर टाइप करा)")
    return "\n".join(lines)
