import re


DB_WORDS = [
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
    "caste", "religion", "hindu", "muslim", "buddhist", "christian", "sikh",
    "jain", "maratha", "brahmin", "mali", "kumbhar", "dhangar", "sutar",
    "nhavi", "koshti", "teli", "shimpi", "sonar", "wani", "lingayat",
    "education", "educated", "occupation", "job", "business", "salary",
    "income", "annual income", "age", "years old", "marital status",
    "unmarried", "divorced", "widow", "widower",
]


def is_database_question(message: str) -> bool:
    msg = message.lower()

    if not any(word in msg for word in DB_WORDS):
        name_match = re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', message)
        if name_match:
            matched = name_match.group()
            words = matched.split()
            if len(words) >= 3 or (len(words) >= 2 and re.search(r'[aeiou]', matched, re.IGNORECASE)):
                return True
        return False

    purchase_intent = any(w in msg for w in ["how", "where", "link", "steps", "steps to"])
    buy_word = any(w in msg for w in ["buy", "purchase", "payment", "pay"])
    plan_word = "plan" in msg or "plans" in msg
    if purchase_intent and buy_word and plan_word:
        return False

    return True
