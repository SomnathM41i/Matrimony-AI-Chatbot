INTENT_MAP = {
    "pricing": [
        "price", "cost", "plan", "subscription", "fee", "pay", "membership",
        "premium", "basic", "gold", "platinum", "diamond", "upgrade", "paid",
        "how much", "amount", "rupees", "package", "pricing",
    ],
    "profile": [
        "list", "female", "male", "city", "name", "age", "member", "profile",
        "match", "find", "looking for", "bride", "groom", "candidate", "girl",
        "boy", "show", "suggest", "eligible", "search", "looking", "available",
    ],
    "support": [
        "support", "contact", "email", "phone", "call", "reach", "help desk",
        "live chat", "team", "address", "office", "hours", "timing", "helpline",
    ],
    "faq": ["faq", "register", "upload", "password", "photo", "edit", "delete", "how to"],
    "success": ["success", "story", "couple", "married", "love", "testimonial", "marriage", "wedding"],
    "about": ["about", "who we are", "company", "platform", "site", "website", "introduce"],
    "safety": ["safety", "secure", "safe", "privacy", "private", "protect", "fake", "report", "fraud", "scam", "verify", "verification", "authentic"],
    "return": ["return", "refund", "cancel", "cancellation", "money back", "guarantee"],
}

CITIES = [
    "mumbai", "pune", "thane", "kalyan", "dombivali", "nashik", "nagpur",
    "karad", "sangamner", "miraj", "khed", "ahilyanagar", "barshi", "solapur",
    "kolhapur", "satara", "sangli", "latur", "aurangabad", "jalgaon", "akola",
    "amravati", "nanded", "dhule", "wardha", "virar", "chembur", "panvel",
    "badlapur", "ulhasnagar", "shirol", "malshiras", "baramati", "shirdi",
    "kopargaon", "shrigonda", "bhiwandi", "ambarnath", "palghar",
]

RELIGIONS = ["hindu", "muslim", "buddhist", "christian", "jain", "sikh"]

CASTE_KEYWORDS = [
    "maratha", "brahmin", "kunbi", "mali", "dhangar", "lingayath", "teli",
    "chambhar", "mahar", "matang", "bhandari", "agri", "vanjari", "sonar",
    "kumbhar", "nhavi", "sutar", "shimpi", "koshti", "gavali", "dhobi",
    "koli", "prajapati", "lohar", "tamboli", "sharma", "verma", "gupta",
]

GENDER_KEYWORDS_MALE = ["groom", "boy", "male", "man", "men", "his", "he", "mulga"]
GENDER_KEYWORDS_FEMALE = ["bride", "girl", "female", "woman", "women", "her", "she", "ladki", "mulgi", "mahila"]


def detect_intent(message: str) -> str:
    msg = message.lower()
    for intent, keywords in INTENT_MAP.items():
        for kw in keywords:
            if kw in msg:
                return intent
    return "general"


def detect_gender(message: str) -> str | None:
    msg = message.lower()
    if any(w in msg for w in GENDER_KEYWORDS_FEMALE):
        return "Female"
    if any(w in msg for w in GENDER_KEYWORDS_MALE):
        return "Male"
    return None


def extract_age_range(message: str) -> tuple[int | None, int | None]:
    import re
    msg = message.lower()

    range_patterns = [
        r'\bage\s*(?:between|from)?\s*(\d{2})\s*(?:-|to|and)\s*(\d{2})\b',
        r'\b(\d{2})\s*(?:-|to|and)\s*(\d{2})\s*(?:years?|yrs?|age)\b',
    ]
    for pattern in range_patterns:
        match = re.search(pattern, msg)
        if match:
            ages = [int(match.group(1)), int(match.group(2))]
            if all(18 <= age <= 80 for age in ages):
                return min(ages), max(ages)

    single_patterns = [
        r'\bage\s*(?:is|=|:)?\s*(\d{2})\b',
        r'\b(\d{2})\s*(?:years?|yrs?)\s*old\b',
    ]
    for pattern in single_patterns:
        match = re.search(pattern, msg)
        if match:
            age = int(match.group(1))
            if 18 <= age <= 80:
                return max(age - 3, 18), min(age + 3, 80)

    return None, None


def extract_city(message: str) -> str | None:
    msg = message.lower()
    for city in CITIES:
        if city in msg:
            return city
    return None


def extract_limit(message: str, default: int = 10, maximum: int = 50) -> int:
    import re
    match = re.search(r'\b(?:top|first|list|show|give me|display)?\s*(\d{1,3})\b', message.lower())
    if not match:
        return default
    return max(1, min(int(match.group(1)), maximum))


def extract_religion(message: str) -> str | None:
    msg = message.lower()
    for r in RELIGIONS:
        if r in msg:
            return r.capitalize()
    return None


def extract_caste(message: str) -> str | None:
    msg = message.lower()
    for c in CASTE_KEYWORDS:
        if c in msg:
            return c.capitalize()
    return None


def extract_marital_status(message: str) -> str | None:
    msg = message.lower()
    if any(w in msg for w in ["unmarried", "never married"]):
        return "Unmarried"
    if "divorc" in msg:
        return "Divorced"
    if "widow" in msg:
        return "Widowed"
    return None


def is_database_question(message: str) -> bool:
    import re
    msg = message.lower()

    db_words = [
        "member", "members", "profile", "profiles", "female", "male", "girl", "boy",
        "bride", "groom", "list", "show", "find", "search", "city", "location",
        "pune", "sangli", "mumbai", "plan", "plans", "price", "pricing", "stats",
        "statistics", "count", "total", "success", "story", "contact", "support",
        "agent", "agents", "commission", "commissions", "customer", "customers",
        "sale", "sales", "withdrawal", "withdrawals", "assignment", "assignments",
        "tell me about", "tell me regarding", "tell me location", "tell me address",
        "tell me age", "tell me dob", "tell me date of birth", "tell me mobile",
        "tell me phone", "tell me email", "tell me details", "tell me name",
        "details of", "details about", "information about", "information of",
        "about", "who is", "who are", "show me", "give me", "do you know",
        "date of birth", "mobile number", "phone number", "email address",
        "age of", "location of", "address of", "city of", "name of",
    ]

    if any(word in msg for word in db_words):
        return True

    return bool(re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', message))
