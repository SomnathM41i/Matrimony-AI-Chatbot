import json
import re
import math
import time
import numpy as np
from app.config import settings
from app.core.prompts import STRUCTURED_EXTRACTION_PROMPT, _EXTRACTION_IDENTITY
from app.ai.llm_client import call_groq
from app.ai.gateway import call_ai
from app.core.logger import logger
from app.services.example_generator import generate_examples
from app.services.schema_discovery import build_schema_context

VALID_INTENTS = {
    "profile_search", "profile_detail", "comparison", "biodata",
    "membership", "greeting", "follow_up", "general", "admin",
}

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
    "nri": None,
    "country": None,
    "nationality": None,
    "residency_status": None,
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

class TFIDFRouter:
    def __init__(self):
        self.classes = {
            'database': [
                'show me female profiles in Pune',
                'search for a Maratha groom',
                'find active members of mali caste',
                'list brides who are never married',
                'looking for a match in Mumbai',
                'मला मुलगी दाखवा',
                'लड़की ढूंढो',
                'show me 5 profiles',
                'what is her education',
                'tell me about her family background',
                'show her photo and contact number',
                'is she working as a software engineer',
                'tell me about the second one',
                'is the doctor employed',
                'show biodata of the CA girl',
                'तिचे शिक्षण काय आहे',
                'उसकी कुंडली दिखाओ',
                'tell me about her',
                'is she working',
                'what is her age',
                'where does she live',
                'is he married or divorced',
                'what is her height and weight',
                'does she smoke or drink',
                'her mobile number and email',
                'biodata of same girl',
                'only unmarried brides',
            ],
            'general': [
                'how can I find a good partner on myvivahai',
                'what are your membership plans and pricing',
                'write a congratulatory note',
                'give me some relationship advice',
                'tell me about your platform history',
                'what is 2+2',
                'how are you',
                'hi', 'hello', 'hey', 'namaste', 'नमस्कार', 'नमस्ते', 'हॅलो', 'namaskar',
                'yes', 'no', 'thanks', 'thank you', 'ok', 'okay', 'bye', 'goodbye',
                'fine', 'sure', 'not really', 'आभार', 'धन्यवाद', 'ठीक आहे',
                'who created you', 'what is your name', 'tell me a joke'
            ]
        }
        self._build_vocabulary()
        self._compute_idf()
        self._vectorize_classes()

    def _tokenize(self, text):
        text = text.lower().strip()
        words = re.findall(r'[a-z\u0900-\u097f0-9]+', text)
        return words

    def _build_vocabulary(self):
        self.vocab = set()
        self.all_docs = []
        self.doc_classes = []
        for cls, docs in self.classes.items():
            for doc in docs:
                tokens = self._tokenize(doc)
                self.vocab.update(tokens)
                self.all_docs.append(tokens)
                self.doc_classes.append(cls)
        self.vocab = sorted(list(self.vocab))
        self.vocab_idx = {tok: idx for idx, tok in enumerate(self.vocab)}

    def _compute_idf(self):
        N = len(self.all_docs)
        self.idf = {}
        for term in self.vocab:
            df = sum(1 for doc in self.all_docs if term in doc)
            self.idf[term] = math.log((1 + N) / (1 + df)) + 1

    def _vectorize(self, tokens):
        vec = np.zeros(len(self.vocab))
        if not tokens:
            return vec
        token_counts = {}
        for tok in tokens:
            if tok in self.vocab_idx:
                token_counts[tok] = token_counts.get(tok, 0) + 1
        for tok, count in token_counts.items():
            idx = self.vocab_idx[tok]
            vec[idx] = (count / len(tokens)) * self.idf[tok]
        return vec

    def _vectorize_classes(self):
        self.class_centroids = {}
        for cls in self.classes.keys():
            vectors = []
            for doc, d_cls in zip(self.all_docs, self.doc_classes):
                if d_cls == cls:
                    vectors.append(self._vectorize(doc))
            self.class_centroids[cls] = np.mean(vectors, axis=0)

    def route(self, message):
        tokens = self._tokenize(message)
        if not tokens:
            return 'general', 0.0
        vec = self._vectorize(tokens)
        similarities = {}
        for cls, centroid in self.class_centroids.items():
            dot = np.dot(vec, centroid)
            norm_vec = np.linalg.norm(vec)
            norm_cen = np.linalg.norm(centroid)
            similarities[cls] = float(dot / (norm_vec * norm_cen)) if norm_vec > 0 and norm_cen > 0 else 0.0
        best_cls = max(similarities, key=similarities.get)
        return best_cls, similarities[best_cls]

# Instantiate the single, global TF-IDF Router singleton at module load.
router = TFIDFRouter()

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
    keywords = {
        "her", "his", "she", "he", "details", "education", "family", "horoscope", "income", "career",
        "photo", "mobile", "contact", "age", "address", "manglik", "gotra", "gothra", "gotram",
        "father", "mother", "brother", "sister", "parent", "occupation", "job", "salary", "earning",
        "शिक्षण", "कुटुंब", "भविष्य", "कुंडली", "शिक्षा", "परिवार", "कुंडली", "biodata", "employed",
        "height", "weight", "same", "uski", "unki", "unka", "uska", "meri", "teri",
        "kundali", "kundli", "dikhao", "dikha", "dikhaye",
    }
    for kw in keywords:
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
    started = time.perf_counter()

    if msg_clean in FAST_PATH_GENERAL:
        logger.info("Intent: fast-path general in %dms", (time.perf_counter() - started) * 1000)
        return {"intent": "general", "filters": {}, "limit": 10, "selected_index": None, "selected_reference": None}

    # Tier 1.5: Deterministic rule-based fast path for clear profile searches
    # (gender/city/age/count in Marathi or English). Skips the LLM entirely so
    # common queries like "पुण्यातील 5 मुलींची प्रोफाइल दाखवा" never wait on or
    # get misrouted by the external model.
    rule_based = rule_based_extract(message)
    if rule_based is not None:
        logger.info(
            "Intent: rule-based profile search in %dms filters=%s",
            (time.perf_counter() - started) * 1000,
            rule_based["filters"],
        )
        return rule_based

    # Tier 2: Zero-Memory Local TF-IDF Centroid Similarity Router
    # Only short-circuit to "general" when the router is confident about general.
    # Low scores (e.g. Romanized Marathi) fall through to the LLM so they are
    # not misrouted into a "no matches" notice before the LLM ever sees them.
    try:
        best_cls, score = router.route(message)
        logger.info(f"TF-IDF Local Router classified: '{message}' -> '{best_cls}' (Similarity: {score:.3f})")
        if best_cls == 'general' and score >= settings.ROUTER_THRESHOLD:
            logger.info("Intent: local router general in %dms", (time.perf_counter() - started) * 1000)
            return {"intent": "general", "filters": {}, "limit": 10, "selected_index": None, "selected_reference": None}
    except Exception as e:
        logger.warning(f"TF-IDF routing exception: {e}")

    # Tier 3: External LLM Structured Parameter Extraction
    dynamic_examples = generate_examples()
    schema_ctx = build_schema_context()
    full_prompt = (
        _EXTRACTION_IDENTITY
        + STRUCTURED_EXTRACTION_PROMPT
        + "\n\n### LIVE SCHEMA CONTEXT ###\n"
        + schema_ctx
        + "\n\n"
        + dynamic_examples
    )
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
        logger.info("Intent: LLM extraction in %dms", (time.perf_counter() - started) * 1000)
    except Exception as e:
        logger.warning(f"Extraction failed, using keyword fallback: {e}")
        if _is_detail_query(message):
            return {"intent": "profile_detail", "filters": {}, "fields": ["all"], "limit": 1, "selected_index": None, "selected_reference": None}
        return {"intent": "profile_search", "filters": _keyword_fallback(message), "limit": 10, "selected_index": None, "selected_reference": None}

    intent_label = parsed.get("intent", "profile_search")
    if intent_label not in VALID_INTENTS:
        intent_label = "general"

    raw_filters = parsed.get("filters", {})
    filters = validate_filters(raw_filters)
    fields = validate_fields(parsed.get("fields"))

    limit = parsed.get("limit", 10)
    if not isinstance(limit, int) or limit < 1:
        limit = 10
    if limit > 50:
        limit = 50

    # Normalize the classified intent for routing so the chat pipeline keeps
    # its existing profile_search / profile_detail / general split. The raw
    # label is retained in "intent_label" for evaluation and logging.
    intent = _normalize_intent(intent_label, parsed)
    if intent == "general":
        return {
            "intent": "general",
            "intent_label": intent_label,
            "filters": {},
            "limit": 10,
            "selected_index": parsed.get("selected_index"),
            "selected_reference": parsed.get("selected_reference"),
        }

    return {
        "intent": intent,
        "intent_label": intent_label,
        "filters": filters,
        "fields": fields,
        "limit": limit,
        "selected_index": parsed.get("selected_index"),
        "selected_reference": parsed.get("selected_reference"),
    }


def _normalize_intent(intent_label: str, parsed: dict) -> str:
    """Map a classified intent onto the routing buckets used by the chat
    pipeline (profile_search / profile_detail / general)."""
    if intent_label in ("profile_search", "profile_detail"):
        return intent_label
    if intent_label == "biodata":
        return "profile_detail"
    if intent_label == "follow_up":
        if parsed.get("selected_index") is not None or parsed.get("selected_reference"):
            return "profile_detail"
        return "general"
    # comparison, membership, greeting, admin, general -> general routing for
    # now (dedicated handling arrives with conversation-memory / pipeline work).
    return "general"

_RULE_FEMALE = {
    "मुली", "मुलींची", "मुलींच्या", "मुलगी", "मुलगीची", "महिला", "महिलांची",
    "स्त्री", "वधू", "वधूची", "बायको", "girl", "girls", "female", "woman",
    "women", "ladki", "ladkiyan", "लडकी", "लड़की", "लड़कियां", "औरत",
}
_RULE_MALE = {
    "मुलगा", "मुलगे", "मुलांची", "मुलांच्या", "मुले", "पुरुष", "वर", "वराची",
    "boy", "boys", "male", "man", "men", "ladka", "ladke", "लडका", "लड़का",
    "आदमी", "मर्द",
}

_RULE_RELIGIONS = {
    "हिंदू": "Hindu", "हिन्दू": "Hindu", "मुस्लिम": "Muslim", "मुसलमान": "Muslim",
    "ख्रिश्चन": "Christian", "ख्रिस्ती": "Christian", "शीख": "Sikh",
    "जैन": "Jain", "बौद्ध": "Buddhist",
    "hindu": "Hindu", "muslim": "Muslim", "christian": "Christian",
    "sikh": "Sikh", "jain": "Jain", "buddhist": "Buddhist",
}

_RULE_CASTES = {
    "मराठा": "Maratha", "ब्राह्मण": "Brahmin", "माळी": "Mali",
    "कुणबी": "Kunbi", "कुनबी": "Kunbi", "कुळी": "Kuli",
    "धनगर": "Dhangar", "कुर्मी": "Kurmi", "सूतार": "Sutar",
    "लोहार": "Lohar", "सोनार": "Sonar", "न्हावी": "Nhavi",
    "शिंपी": "Shimpi", "माहार": "Mahar", "कोळी": "Koli",
    "चांभार": "Chambhar", "मांग": "Mang",
    "maratha": "Maratha", "brahmin": "Brahmin", "mali": "Mali",
    "kunbi": "Kunbi", "dhangar": "Dhangar", "koli": "Koli",
}

_RULE_MARITAL = {
    "divorcee": "Divorced", "divorced": "Divorced", "घटस्फोटित": "Divorced",
    "तलाकशुदा": "Divorced", "तलाक": "Divorced",
    "widow": "Widow", "विधवा": "Widow",
    "widower": "Widower", "विधुर": "Widower",
    "unmarried": "Unmarried", "never married": "Unmarried", "अविवाहित": "Unmarried",
    "awaiting divorce": "Awaiting Divorce",
}

_RULE_NRI = {"nri", "एनआरआय", "non resident indian", "non-resident indian", "अनिवासी भारतीय"}

_CITY_MR_EN = {
    "पुणे": "Pune", "मुंबई": "Mumbai", "नाशिक": "Nashik", "नागपूर": "Nagpur",
    "सातारा": "Satara", "कोल्हापूर": "Kolhapur", "सोलापूर": "Solapur",
    "औरंगाबाद": "Aurangabad", "अमरावती": "Amravati", "जळगाव": "Jalgaon",
    "धुळे": "Dhule", "नांदेड": "Nanded", "लातूर": "Latur", "सांगली": "Sangli",
    "ठाणे": "Thane", "कल्याण": "Kalyan", "अकोला": "Akola", "परभणी": "Parbhani",
    "जालना": "Jalna", "हिंगोली": "Hingoli", "वर्धा": "Wardha",
    "यवतमाळ": "Yavatmal", "भंडारा": "Bhandara", "गोंदिया": "Gondia",
    "चंद्रपूर": "Chandrapur", "गडचिरोली": "Gadchiroli", "रत्नागिरी": "Ratnagiri",
    "सिंधुदुर्ग": "Sindhudurg", "रायगड": "Raigad", "पालघर": "Palghar",
    "अहमदनगर": "Ahmednagar", "बुलढाणा": "Buldhana", "वाशिम": "Washim",
    "उस्मानाबाद": "Osmanabad", "बीड": "Beed", "नंदुरबार": "Nandurbar",
    "पिंपरी": "Pimpri", "चिंचवड": "Chinchwad", "पनवेल": "Panvel",
    "कराड": "Karad", "बारामती": "Baramati", "लोणावळा": "Lonavala",
    "पंढरपूर": "Pandharpur", "सावंतवाडी": "Sawantwadi", "अलिबाग": "Alibag",
    "डोंबिवली": "Dombivli", "उल्हासनगर": "Ulhasnagar", "बदलापूर": "Badlapur",
    "इचलकरंजी": "Ichalkaranji", "महाड": "Mahad",
}

_MR_NUMBER_WORDS = {
    "एक": 1, "दोन": 2, "तीन": 3, "चार": 4, "पाच": 5,
    "सहा": 6, "सात": 7, "आठ": 8, "नऊ": 9, "दहा": 10,
}

# Optional Marathi case suffixes attached to a city name (पुण्यातील, नाशिकात ...).
_MR_CITY_SUFFIX = (
    r"(?:ातील|ामधील|ातल्या|ातला|ातले|ात|ाच्या|ाची|ाचा|ाचे|च्या|ची|चा|चे|"
    r"तील|त|मधील|मधल्या|मध्ये|मधे|शी|हून|कडे)?"
)


def _mr_stems(name: str) -> list[str]:
    """Surface stems of a Marathi city name for suffix matching."""
    stems = [name]
    if name.endswith("े"):
        root = name[:-1]
        stems += [root + "्या", root + "्य"]
    elif name.endswith("ू"):
        stems.append(name[:-1] + "ु")
    return stems


def _resolve_against_db(candidates: list[str], db_values: list[str]) -> str | None:
    low_cands = [str(c).strip().lower() for c in candidates if c]
    if not low_cands:
        return None
    entries = [(v, str(v).strip().lower()) for v in (db_values or []) if v and str(v).strip()]
    for v, lv in entries:
        if lv in low_cands:
            return v
    best = None
    for v, lv in entries:
        for c in low_cands:
            if c in lv or lv in c:
                if best is None or len(lv) < len(best[1]):
                    best = (v, lv)
                break
    return best[0] if best else None


def _extract_city(message: str) -> str | None:
    from app.services.schema_discovery import get_all_cities

    msg = message.lower()
    city_en = None

    for mr, en in _CITY_MR_EN.items():
        stems = _mr_stems(mr)
        pattern = r"(?<![ऀ-ॿa-zA-Z0-9])(" + "|".join(re.escape(s) for s in stems) + r")" + _MR_CITY_SUFFIX + r"(?![ऀ-ॿ])"
        if re.search(pattern, msg):
            city_en = en
            break

    if city_en is None:
        # English name as a standalone word.
        for en in set(_CITY_MR_EN.values()):
            if _word_in(msg, en.lower()):
                city_en = en
                break

    if city_en is None:
        return None
    return _resolve_against_db([city_en], get_all_cities()) or city_en


def rule_based_extract(message: str) -> dict | None:
    """Deterministic, zero-LLM fast path for clear profile-search queries.

    Returns {"intent": "profile_search", "filters": {...}, "limit": N,
    "deterministic": True} when the message clearly asks to find/show profiles
    and at least one concrete filter can be extracted. Returns None otherwise
    so the normal LLM-based extraction runs.
    """
    msg = message.strip().rstrip(".!?,")
    if not msg:
        return None
    msg_lower = msg.lower()

    if _is_detail_query(msg):
        return None

    has_profile_word = any(
        _word_in(msg_lower, kw)
        for kw in _RULE_FEMALE | _RULE_MALE | {
            "प्रोफाइल", "सदस्य", "profile", "profiles", "bride", "groom",
            "bridegroom", "जोडीदार", "मॅच", "match",
        }
    )
    has_search_verb = any(
        _word_in(msg_lower, kw)
        for kw in {"दाखवा", "दाखव", "शोधा", "शोध", "show", "search", "find",
                   "list", "dikhao", "dikha", "दिखाओ", "पाहिजे", "हवी", "हवे",
                   "हवा", "असलेली", "असलेला"}
    )
    if not (has_profile_word or has_search_verb):
        return None

    filters: dict = {}

    if any(_word_in(msg_lower, kw) for kw in _RULE_FEMALE):
        filters["gender"] = "Female"
    elif any(_word_in(msg_lower, kw) for kw in _RULE_MALE):
        filters["gender"] = "Male"

    city = _extract_city(msg_lower)
    if city:
        filters["city"] = city

    for mr, en in _RULE_RELIGIONS.items():
        if _word_in(msg_lower, mr):
            filters["religion"] = en
            break

    from app.services.schema_discovery import get_all_castes
    for mr, en in _RULE_CASTES.items():
        if _word_in(msg_lower, mr):
            filters["caste"] = _resolve_against_db([mr, en], get_all_castes()) or en
            break

    for keyword, marital in _RULE_MARITAL.items():
        if _word_in(msg_lower, keyword):
            filters["marital_status"] = marital
            if marital == "Widow" and "gender" not in filters:
                filters["gender"] = "Female"
            elif marital == "Widower" and "gender" not in filters:
                filters["gender"] = "Male"
            break

    if any(_word_in(msg_lower, kw) for kw in _RULE_NRI):
        filters["nri"] = True

    age = re.search(r"(\d{1,2})\s*(?:ते|-|–|to)\s*(\d{1,2})\s*वर्ष", msg_lower)
    if age:
        lo, hi = sorted((int(age.group(1)), int(age.group(2))))
        filters["age_min"] = lo
        filters["age_max"] = hi

    limit = None
    translated = msg.translate(str.maketrans("०१२३४५६७८९", "0123456789"))
    num = re.search(
        r"(\d{1,2})\s*(?:मुली|मुलींची|मुलींच्या|मुलगी|मुलांची|मुलांच्या|"
        r"जण|जणांची|जणांच्या|प्रोफाइल|profiles?|girls?|boys?)",
        translated,
    )
    if num:
        limit = int(num.group(1))
    else:
        word_num = re.search(
            r"(" + "|".join(_MR_NUMBER_WORDS) + r")\s*(?:मुली|मुलींची|मुलगी|मुलांची|जण|जणांची|प्रोफाइल)",
            msg_lower,
        )
        if word_num:
            limit = _MR_NUMBER_WORDS[word_num.group(1)]

    if limit is not None:
        limit = max(1, min(limit, 50))

    # Only short-circuit when the request is concrete enough to answer without
    # the LLM: at least one extracted filter/limit, or an explicit profile
    # request written in Devanagari (e.g. "प्रोफाइल दाखवा"). Vague or generic
    # queries fall through so the LLM can interpret them.
    has_devanagari = any("\u0900" <= ch <= "\u097f" for ch in msg)
    if not (filters or limit) and not (has_profile_word and has_search_verb and has_devanagari):
        return None

    return {
        "intent": "profile_search",
        "filters": filters,
        "limit": limit or 10,
        "deterministic": True,
        "selected_index": None,
        "selected_reference": None,
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
