import os, json, re, logging, html
import mysql.connector
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Matrubhumi Vivah Vishwa AI Chatbot")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "82.25.121.160"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "u320743426_mvv"),
    "password": os.getenv("DB_PASSWORD", "6w8zBn/3"),
    "database": os.getenv("DB_NAME", "u320743426_mvv"),
    "connect_timeout": 10,
}
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

@app.on_event("startup")
def startup():
    try:
        conn = get_db()
        conn.ping()
        conn.close()
        log.info("Database connection OK")
    except Exception as e:
        log.warning(f"Database connection failed on startup: {e}")

@app.get("/health")
def health():
    db_ok = False
    try:
        conn = get_db()
        conn.ping()
        conn.close()
        db_ok = True
    except Exception:
        pass
    return {"status": "ok" if db_ok else "degraded", "database": "connected" if db_ok else "unreachable"}

SITE_CACHE = None
def get_site_info():
    global SITE_CACHE
    if SITE_CACHE:
        return SITE_CACHE
    try:
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT Webname, Fromemail, ContactEmail, address, openingtime, contactusmobile1, reg_phone, facebook, youtube FROM siteconfig LIMIT 1")
        SITE_CACHE = cur.fetchone()
        cur.close(); conn.close()
    except Exception as e:
        log.error(f"get_site_info: {e}")
        SITE_CACHE = {}
    return SITE_CACHE

INTENT_MAP = {
    "pricing": ["price", "cost", "plan", "subscription", "fee", "pay", "membership", "premium", "basic", "gold", "platinum", "diamond", "upgrade", "paid", "how much", "amount", "rupees", "₹", "package"],
    "faq": ["how", "what", "can", "do", "where", "when", "why", "faq", "register", "upload", "password", "photo", "edit", "delete"],
    "success": ["success", "story", "couple", "married", "love", "testimonial", "marriage", "wedding"],
    "profile": ["match", "find", "looking for", "bride", "groom", "candidate", "girl", "boy", "show", "suggest", "eligible", "search", "looking", "available"],
    "support": ["support", "contact", "email", "phone", "call", "reach", "help desk", "live chat", "team", "address", "office", "hours", "timing", "helpline"],
    "about": ["about", "who we are", "company", "platform", "site", "website", "matrubhumi", "vivah", "vishwa", "introduce"],
    "safety": ["safety", "secure", "safe", "privacy", "private", "protect", "fake", "report", "fraud", "scam", "verify", "verification", "authentic"],
    "return": ["return", "refund", "cancel", "cancellation", "money back", "guarantee", "cancel membership"],
}

CITIES = ["mumbai", "pune", "thane", "kalyan", "dombivali", "nashik", "nagpur", "karad", "sangamner", "miraj", "khed", "ahilyanagar", "barshi", "solapur", "kolhapur", "satara", "sangli", "latur", "aurangabad", "jalgaon", "akola", "amravati", "nanded", "dhule", "wardha", "virar", "chembur", "panvel", "badlapur", "ulhasnagar", "shirol", "malshiras", "baramati", "shirdi", "kopargaon", "shrigonda", "bhiwandi", "ambarnath", "palghar"]
RELIGIONS = ["hindu", "muslim", "buddhist", "christian", "jain", "sikh"]
CASTE_KEYWORDS = ["maratha", "brahmin", "kunbi", "mali", "dhangar", "lingayath", "teli", "chambhar", "mahar", "matang", "bhandari", "agri", "vanjari", "sonar", "kumbhar", "nhavi", "sutar", "shimpi", "koshti", "gavali", "dhobi", "koli", "prajapati", "lohar", "tamboli", "sharma", "verma", "gupta"]

INTENT_SYSTEM = {
    "pricing": "You are a pricing advisor for Matrubhumi Vivah Vishwa, a Marathi matrimony website. Answer using ONLY the membership plan data below. Show plan name, price, duration, contacts, and features in a clear numbered list.",
    "faq": "You are a help assistant for Matrubhumi Vivah Vishwa. Answer the user's question using ONLY the FAQ/content data below. Give clear, helpful answers in plain text.",
    "success": "You are a success story narrator for Matrubhumi Vivah Vishwa. Share the success stories happily. If no stories exist yet, encourage the user to be the first success story!",
    "profile": "You are a matchmaking assistant for Matrubhumi Vivah Vishwa, a Marathi matrimony website. Based on the member profiles from the database, suggest suitable matches. For each include: Name, Age, City, Religion, Caste, Education, Occupation, Income. Be respectful and helpful.",
    "support": "You are a support representative for Matrubhumi Vivah Vishwa. Share the contact details from the database - email, phone, address, and working hours. Be friendly and professional.",
    "about": "You are a company representative for Matrubhumi Vivah Vishwa. Share information about the website from the database details below.",
    "safety": "You are a safety advisor for Matrubhumi Vivah Vishwa. Share safety guidelines and privacy information from the database. Reassure the user about their data security.",
    "return": "You are a policies advisor for Matrubhumi Vivah Vishwa. Explain the return/refund/cancellation policy from the database information below.",
    "general": "You are a helpful assistant for Matrubhumi Vivah Vishwa (Matrubhumi Vivah Vishwa). Answer the user using any relevant information from the database. Be friendly and professional.",
}

def strip_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return html.unescape(text)[:2000]

def detect_intent(message):
    msg = message.lower()
    for intent, keywords in INTENT_MAP.items():
        for kw in keywords:
            if kw in msg:
                return intent
    return "general"

def detect_gender(message):
    msg = message.lower()
    if any(w in msg for w in ["bride", "girl", "female", "woman", "women", "her", "she", "ladki", "mulgi", "mahila"]):
        return "Female"
    if any(w in msg for w in ["groom", "boy", "male", "man", "men", "his", "he", "mulga"]):
        return "Male"
    return None

def extract_age_range(message):
    nums = [int(n) for n in re.findall(r'\d+', message)]
    if len(nums) >= 2:
        return min(nums), max(nums)
    elif len(nums) == 1:
        return max(nums[0] - 3, 18), nums[0] + 3
    return None, None

def extract_city(message):
    msg = message.lower()
    for city in CITIES:
        if city in msg:
            return city
    return None

def extract_religion(message):
    msg = message.lower()
    for r in RELIGIONS:
        if r in msg:
            return r.capitalize()
    return None

def extract_caste(message):
    msg = message.lower()
    for c in CASTE_KEYWORDS:
        if c in msg:
            return c.capitalize()
    return None

def extract_marital_status(message):
    msg = message.lower()
    if any(w in msg for w in ["unmarried", "never married"]):
        return "Unmarried"
    if "divorc" in msg:
        return "Divorced"
    if "widow" in msg:
        return "Widowed"
    return None

def safe_query(sql, params=None, dictionary=True, fetch_one=False):
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=dictionary)
        cur.execute(sql, params or ())
        row = cur.fetchone() if fetch_one else cur.fetchall()
        cur.close(); conn.close()
        return row
    except Exception as e:
        log.error(f"DB query error: {e}")
        return None

def query_pricing():
    return safe_query("SELECT plandisplayname, planamount, planduration, plannoofcontacts, description1, description2, description3, description4, description5, description6, description7 FROM membershipplan")

def query_cms_page(link):
    return safe_query("SELECT content, link, mobile, email, whatsapp, officetime FROM cms WHERE link = %s LIMIT 1", (link,), fetch_one=True)

def query_success():
    rows = safe_query("SELECT bridename, groomname, marriagedate, successmessage FROM successstory WHERE approve=1 LIMIT 5")
    if not rows:
        rows = safe_query("SELECT bridename, groomname, marriagedate, successmessage FROM testimonial WHERE approve=1 LIMIT 5")
    return rows or []

def query_profiles(message):
    conditions = ["Status IN ('Active', 'Paid')"]
    params = []
    gender = detect_gender(message)
    if gender:
        conditions.append("Gender = %s"); params.append(gender)
    age_min, age_max = extract_age_range(message)
    if age_min and age_max:
        conditions.append("CAST(Age AS UNSIGNED) BETWEEN %s AND %s"); params.extend([age_min, age_max])
    city = extract_city(message)
    if city:
        conditions.append("City LIKE %s"); params.append(f"%{city}%")
    religion = extract_religion(message)
    if religion:
        conditions.append("Religion = %s"); params.append(religion)
    caste = extract_caste(message)
    if caste:
        conditions.append("Caste = %s"); params.append(caste)
    marital = extract_marital_status(message)
    if marital:
        conditions.append("Maritalstatus = %s"); params.append(marital)
    sql = f"SELECT MatriID, Name, Gender, Age, Maritalstatus, Religion, Caste, City, State, Education, Occupation, Annualincome FROM register WHERE {' AND '.join(conditions)} ORDER BY RAND() LIMIT 5"
    rows = safe_query(sql, params)
    if not rows:
        rows = safe_query("SELECT MatriID, Name, Gender, Age, Maritalstatus, Religion, Caste, City, State, Education, Occupation, Annualincome FROM register WHERE Status IN ('Active','Paid') ORDER BY RAND() LIMIT 5")
    return rows or []

async def call_llm(system_prompt, user_message, db_data):
    if not GROQ_API_KEY or GROQ_API_KEY == "your-groq-api-key":
        return "⚠ Groq API key not configured. Set the GROQ_API_KEY environment variable and restart."
    data_str = json.dumps(db_data, indent=2, default=str)[:4000] if db_data else "No data found."
    prompt = f"User Question: {user_message}\n\nDatabase Information:\n{data_str}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={
                    "model": "llama3-70b-8192",
                    "messages": [
                        {"role": "system", "content": system_prompt[:2000]},
                        {"role": "user", "content": prompt[:3000]}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 800
                },
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        return "The request timed out. Please try again with a simpler question."
    except Exception as e:
        log.error(f"LLM error: {e}")
        return f"I found the information but had trouble formatting it. Here is the raw data:\n\n{data_str[:1000]}"

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    intent = detect_intent(req.message)

    try:
        if intent == "pricing":
            db_data = query_pricing()
            reply = await call_llm(INTENT_SYSTEM["pricing"], req.message, db_data)
        elif intent == "faq":
            db_data = query_cms_page("help page") or {}
            content = strip_html(db_data.get("content", ""))
            reply = await call_llm(INTENT_SYSTEM["faq"], req.message, {"faq_content": content})
        elif intent == "success":
            db_data = query_success()
            reply = await call_llm(INTENT_SYSTEM["success"], req.message, db_data)
        elif intent == "profile":
            db_data = query_profiles(req.message)
            system = INTENT_SYSTEM["profile"]
            if not db_data:
                system += " No exact matches found. Show available profiles and suggest refining search criteria."
            reply = await call_llm(system, req.message, db_data)
        elif intent == "support":
            info = get_site_info() or {}
            contact = query_cms_page("contact us") or {}
            reply = await call_llm(INTENT_SYSTEM["support"], req.message, {"site_info": info, "contact_page": contact})
        elif intent == "about":
            db_data = query_cms_page("aboutus") or {}
            content = strip_html(db_data.get("content", ""))
            reply = await call_llm(INTENT_SYSTEM["about"], req.message, {"about_content": content})
        elif intent == "safety":
            db_data = query_cms_page("safematrimony") or {}
            content = strip_html(db_data.get("content", ""))
            reply = await call_llm(INTENT_SYSTEM["safety"], req.message, {"safety_content": content})
        elif intent == "return":
            db_data = query_cms_page("return_policy") or {}
            content = strip_html(db_data.get("content", ""))
            reply = await call_llm(INTENT_SYSTEM["return"], req.message, {"return_policy": content})
        else:
            info = get_site_info() or {}
            faq = query_cms_page("help page") or {}
            reply = await call_llm(INTENT_SYSTEM["general"], req.message, {
                "site_info": info,
                "membership_plans": query_pricing(),
                "faq": strip_html(faq.get("content", "")),
            })
    except Exception as e:
        log.error(f"Chat error: {e}")
        reply = "Sorry, something went wrong. Please try again later."

    return ChatResponse(reply=reply)

@app.get("/")
def root():
    return {"status": "running", "site": "Matrubhumi Vivah Vishwa AI Chatbot", "health": "/health"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
