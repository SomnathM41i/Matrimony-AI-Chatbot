import asyncio
import re
import threading
import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
from app.config import settings
from app.core.constants import SENSITIVE_FIELDS
from app.core.logger import logger


def validate_select_sql(sql: str, allowed_tables: set) -> str:
    sql = (sql or "").strip()
    sql = re.sub(r'\s+', ' ', sql)
    if sql.endswith(";"):
        sql = sql[:-1].strip()

    lowered = sql.lower()

    blocked_keywords = [
        r'\b(insert|update|delete|drop|alter|truncate|create|replace|grant|revoke|call|exec|load)\b',
        r'/\*', r'--', r'\bmysql_\w+',
        r'\b(unions?)\b',
        r'\binto\s+(outfile|dumpfile)\b',
        r'\binformation_schema\b',
        r'\b(0x[0-9a-f]+)\b',
        r'\bchar\s*\(',
        r'\b(sleep|benchmark|load_file)\s*\(',
    ]
    for pattern in blocked_keywords:
        if re.search(pattern, lowered):
            raise ValueError("Unsafe SQL pattern blocked.")

    if not lowered.startswith("select "):
        raise ValueError("Only SELECT queries are allowed.")
    if ";" in lowered:
        raise ValueError("Only one query is allowed.")

    if re.search(r'\b(?:with|select)\b.*\bfrom\b.*\bselect\b', lowered, re.DOTALL):
        raise ValueError("Subqueries are not allowed.")

    select_clause = re.split(r'\bfrom\b', lowered, maxsplit=1)[0]
    star_without_count = re.sub(r'\bcount\s*\(\s*\*\s*\)', '', select_clause)
    if re.search(r'(?:\b[a-z_][a-z0-9_]*\s*\.\s*)?\*', star_without_count):
        raise ValueError("Wildcard column selection is not allowed.")

    forbidden_fields = set(SENSITIVE_FIELDS) | {
        "passwordhash", "passcode", "secret", "secret_key", "api_key",
        "token", "refresh_token", "bank_account", "accountnumber",
    }
    referenced_identifiers = set(re.findall(r'\b[a-z_][a-z0-9_]*\b', lowered))
    blocked_fields = sorted(referenced_identifiers & forbidden_fields)
    if blocked_fields:
        raise ValueError("Sensitive database columns are not accessible.")

    referenced_tables = set(re.findall(r'\b(?:from|join)\s+`?([a-zA-Z0-9_]+)`?', lowered))
    if not referenced_tables:
        raise ValueError("No table found in SQL.")
    if not referenced_tables.issubset(allowed_tables):
        blocked = sorted(referenced_tables - allowed_tables)
        allowed = ", ".join(sorted(allowed_tables))
        raise ValueError(f"Access denied to tables: {', '.join(blocked)}. Allowed: {allowed}.")

    if " limit " not in lowered:
        sql += f" LIMIT {settings.SQL_LIMIT}"

    return sql


def sanitize_rows(rows: list[dict]) -> list[dict]:
    clean_rows = []
    for row in rows or []:
        clean = {}
        for key, value in row.items():
            if key.lower() in SENSITIVE_FIELDS or "password" in key.lower():
                continue
            clean[key] = value
        clean_rows.append(clean)
    return clean_rows


_UNKNOWN_PERSONAL_ATTRIBUTES = [
    "favorite food", "favourite food", "favorite dish", "favourite dish",
    "biryani", "pizza", "cuisine", "curry",
    "appetite", "how much does she eat", "how much does he eat",
    "how much can she eat", "how much can he eat", "how much she eat",
    "how much he eat", "eating habit", "cooking habit",
    "daily routine", "wake up", "sleeping",
    "prefer curd", "prefer yogurt", "prefer biryani",
    "favourite biryani", "favorite biryani",
    "what does she like to eat", "what does he like to eat",
    "what food does she like", "what food does he like",
    "kay khate", "kay khato", "aavadta", "आवडता",
    "जेवण", "खाणे", "खाते",
    "veg", "nonveg", "non veg", "शाकाहारी", "मांसाहारी",
    "chapati", "roti", "भात", "दाल", "सब्जी",
    "father", "mother", "brother", "sister", "वडील", "आई", "भाऊ", "बहीण",
    "kay karatat", "kay karte", "व्यवसाय", "नोकरी", "कंपनी",
    "company", "business", "व्यवसायिक",
    "education", "शिक्षण", "college", "school", "university", "विद्यापीठ",
]

_KNOWN_PERSONAL_COLUMNS = {
    "diet", "smoke", "drink", "hobbies", "interests",
    "education", "educationdetails", "occupation", "employedin", "annualincome",
    "height", "weight", "bloodgroup", "bodytype", "complexion",
    "familyvalues", "familytype", "familystatus",
    "fathername", "mothersname", "fathersoccupation", "mothersoccupation",
    "noofbrothers", "noofsisters",
    "star", "moonsign", "manglik", "gothram", "language",
    "religion", "caste", "subcaste",
    "city", "dist", "state", "country", "residencystatus",
    "matriid", "name", "age", "gender", "maritalstatus",
    "mobile", "photo1",
}


def message_asks_about_unavailable_attribute(message: str) -> bool:
    msg = message.lower().strip()
    for phrase in _UNKNOWN_PERSONAL_ATTRIBUTES:
        if phrase in msg:
            return True
    return False


class DatabaseQueryError(RuntimeError):
    """Raised when the matrimony database cannot execute a query."""


def _build_connection_args():
    args = {
        "host": settings.DB_HOST,
        "port": settings.DB_PORT,
        "user": settings.DB_USER,
        "password": settings.DB_PASSWORD,
        "database": settings.DB_NAME,
        "connect_timeout": settings.DB_CONNECT_TIMEOUT,
    }
    if settings.DB_SSL_CA:
        args["ssl_ca"] = settings.DB_SSL_CA
    return args


_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                try:
                    _pool = MySQLConnectionPool(
                        pool_name="mvv_pool",
                        pool_size=settings.DB_POOL_SIZE,
                        **_build_connection_args(),
                    )
                except Exception:
                    return None
    return _pool


def sync_get_connection():
    pool = _get_pool()
    if pool:
        try:
            return pool.get_connection()
        except Exception as e:
            # Pool exhausted or unhealthy: fall back to a direct connection.
            logger.debug(f"MySQL pool unavailable, using direct connection: {e}")
    return mysql.connector.connect(**_build_connection_args())


def sync_safe_query(sql: str, params: tuple | None = None, fetch_one: bool = False):
    conn = None
    cur = None
    try:
        conn = sync_get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params or ())
        return cur.fetchone() if fetch_one else cur.fetchall()
    except Exception as e:
        logger.error(f"DB query error: {e}")
        raise DatabaseQueryError("Database query failed") from e
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def sync_check_connection() -> bool:
    try:
        conn = sync_get_connection()
        conn.ping()
        conn.close()
        return True
    except Exception:
        return False


def add_photo_url(row: dict):
    photo = row.get("Photo1") or ""
    if photo and photo.lower() != "nophoto.jpg":
        row["PhotoURL"] = settings.PHOTO_BASE_URL.rstrip("/") + "/" + photo.lstrip("/")
    else:
        row["PhotoURL"] = ""


def sync_execute_llm_sql(sql: str) -> dict:
    sql = validate_select_sql(sql, settings.allowed_tables_set)
    rows = sync_safe_query(sql)
    clean = sanitize_rows(rows or [])
    for row in clean:
        add_photo_url(row)
    return {
        "sql": sql,
        "rows": clean,
        "row_count": len(rows or []),
    }


async def check_db_connection() -> bool:
    return await asyncio.to_thread(sync_check_connection)


async def execute_llm_sql(sql: str) -> dict:
    return await asyncio.to_thread(sync_execute_llm_sql, sql)


def safe_query(sql: str, params: tuple | None = None, fetch_one: bool = False):
    """Synchronous wrapper kept for get_database_stats. Use async functions for new code."""
    return sync_safe_query(sql, params, fetch_one)


def accumulate_usage(*usages):
    total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for u in usages:
        total["prompt_tokens"] += u.get("prompt_tokens", 0) or 0
        total["completion_tokens"] += u.get("completion_tokens", 0) or 0
        total["total_tokens"] += u.get("total_tokens", 0) or 0
    return total


def sync_execute_param_query(sql: str, params: list) -> dict:
    rows = sync_safe_query(sql, tuple(params))
    clean = sanitize_rows(rows or [])
    for row in clean:
        add_photo_url(row)
    return {
        "sql": sql,
        "rows": clean,
        "row_count": len(rows or []),
    }


async def execute_param_query(sql: str, params: list) -> dict:
    return await asyncio.to_thread(sync_execute_param_query, sql, params)


async def format_notice_safe(message: str, notice: str, history, db, fallback: str = "") -> str:
    try:
        from app.services.llm_service import format_db_notice
        result = await format_db_notice(message, notice, history=history, db=db)
        return result.get("content", "") or fallback or notice
    except Exception:
        return fallback or notice


def merge_filters(accumulated: dict | None, new_filters: dict) -> dict:
    merged = dict(accumulated or {})
    for key, value in (new_filters or {}).items():
        if value is not None:
            merged[key] = value
    return merged


TOO_MANY_NOTICE = (
    "सर्चमध्ये {count} परिणाम सापडले, एकाच वेळी सर्व दाखवणे शक्य नाही. "
    "कृपया अधिक अचूक criteria निवडा."
)

_MARITAL_MR = {
    "Unmarried": "कधीही लग्न न केलेले",
    "Divorced": "घटस्फोटित",
    "Widowed": "विधवा",
    "Widower": "विधुर",
}

_MANGLIK_MR = {"Yes": "मांगलिक", "No": "अमांगलिक"}

_COMPLEXION_MR = {
    "Very Fair": "अतिशय गोरा",
    "Fair": "गोरा",
    "Wheatish": "गहूवर्णी",
    "Wheatish Medium": "गहूवर्णी मध्यम",
    "Dark": "सावळा",
}

_FILTER_SUMMARY_ORDER = [
    ("marital_status", "वैवाहिक स्थिती"),
    ("religion", "धर्म"),
    ("caste", "जात"),
    ("subcaste", "उपजात"),
    ("education", "शिक्षण"),
    ("occupation", "व्यवसाय"),
    ("city", "स्थान"),
    ("manglik", "मांगलिक"),
    ("complexion", "रंग/वर्ण"),
]


def _filter_value_mr(key: str, value) -> str | None:
    if value is None or value == "":
        return None
    if key == "marital_status":
        return _MARITAL_MR.get(str(value), str(value))
    if key == "manglik":
        return _MANGLIK_MR.get(str(value), str(value))
    if key == "complexion":
        return _COMPLEXION_MR.get(str(value), str(value))
    return str(value)


def format_filter_summary(filters: dict) -> str:
    """Marathi, human-readable summary of the non-empty search filters."""
    parts = []
    lo, hi = filters.get("age_min"), filters.get("age_max")
    if lo or hi:
        parts.append(f"वय {lo or '?'} - {hi or '?'} वर्षे")
    gender = str(filters.get("gender") or "").lower()
    if gender:
        parts.append("मुलगी" if gender.startswith("f") else "मुलगा")
    for key, label in _FILTER_SUMMARY_ORDER:
        value = _filter_value_mr(key, filters.get(key))
        if value:
            parts.append(f"{label}: {value}")
    return ", ".join(parts)


def format_no_matches_notice(filters: dict) -> str:
    """Personalized no-match message referencing the active filters and
    offering concrete next steps."""
    summary = format_filter_summary(filters)
    if summary:
        head = f"सध्या या निकषांना जुळणारी प्रोफाइल सापडली नाही:\n{summary}"
    else:
        head = "सध्या या निकषांना जुळणारी प्रोफाइल सापडली नाही."
    return (
        f"{head}\n\n"
        "सल्ला:\n"
        "- वयोगट थोडा वाढवून पहा (उदा. 18 - 30 वर्षे)\n"
        "- रंग/वर्ण, मांगलिक किंवा वैवाहिक स्थिती सारख्या पसंती सैल करा\n"
        "- कमी निकषांसह पुन्हा शोधा, किंवा मला सांगा — \"सैल निकषांनी पर्याय दाखव\""
    )


def format_profile_results_markdown(filters: dict, sql_result: dict) -> str:
    """Zero-LLM Marathi profile listing that matches the format ChatMessage's
    splitContent renders as photo cards: `![Name](PhotoURL) Age, Gender, City, ...`."""
    rows = sql_result.get("rows") or []
    lines = []
    count = len(rows)

    ctx = []
    city = filters.get("city")
    if city:
        ctx.append(f"{city} मधील")
    gender = str(filters.get("gender") or "").lower()
    if gender == "female":
        ctx.append("मुलींची")
    elif gender == "male":
        ctx.append("मुलांची")
    if count:
        lines.append(f"येथे {' '.join(ctx)} {count} प्रोफाइल आहेत:" if ctx else f"येथे {count} जुळणारी प्रोफाइल आहेत:")
        lines.append("")

    for row in rows:
        name = row.get("Name") or "प्रोफाइल"
        details = ", ".join(
            str(row.get(k)) for k in
            ("Age", "Gender", "City", "Caste", "Religion", "Occupation", "Education")
            if row.get(k)
        )
        photo = row.get("PhotoURL") or row.get("Photo1") or ""
        if photo and photo.lower() != "nophoto.jpg":
            if photo.lower().startswith("http://") or photo.lower().startswith("https://"):
                url = photo
            else:
                url = settings.PHOTO_BASE_URL.rstrip("/") + "/" + photo.lstrip("/")
        else:
            url = settings.PHOTO_BASE_URL.rstrip("/") + "/nophoto.jpg"
        lines.append(f"![{name}]({url}) {details}")

    return "\n".join(lines)


def _build_metadata(profile_rows, filters):
    if profile_rows:
        return {
            "profile_candidates": profile_rows,
            "selected_profile": profile_rows[0] if len(profile_rows) == 1 else None,
            "accumulated_filters": filters,
        }
    return {"accumulated_filters": filters}


async def handle_profile_search(
    message: str, filters: dict, limit: int, history, db, deterministic: bool = False
) -> dict:
    from app.services.query_builder import build_profile_query
    from app.services.llm_service import format_db_result

    sql, params = build_profile_query(filters, limit=limit)
    sql_result = await execute_param_query(sql, params)

    profile_rows = [
        {"MatriID": row.get("MatriID"), "Name": row.get("Name")}
        for row in sql_result["rows"]
        if row.get("Name")
    ]
    metadata = _build_metadata(profile_rows, filters)

    if deterministic:
        if sql_result["row_count"] == 0:
            return {
                "content": format_no_matches_notice(filters),
                "matched": "none",
                "is_profile_search": True,
                "usage": {}, "events": [],
                "metadata": metadata,
            }
        if sql_result["row_count"] > settings.MAX_ROWS_BEFORE_NARROW:
            return {
                "content": TOO_MANY_NOTICE.format(count=sql_result["row_count"]),
                "matched": "too_many",
                "is_profile_search": True,
                "usage": {}, "events": [],
                "metadata": metadata,
            }
        return {
            "content": format_profile_results_markdown(filters, sql_result),
            "matched": "some",
            "is_profile_search": True,
            "usage": {}, "events": [],
            "metadata": metadata,
        }

    if sql_result["row_count"] == 0 and settings.VECTOR_FALLBACK_ENABLED:
        from app.services.embedding_service import embed_text, build_profile_document, unload_embedding_model
        from app.services.vector_service import search_with_filters
        try:
            query_text = build_profile_document(filters)
            query_vector = await embed_text(
                f"query: {message}. {query_text}",
                model_name=settings.EMBEDDING_MODEL,
            )
            # search_with_filters blocks on network I/O, so keep it off the event loop.
            vector_rows = await asyncio.to_thread(
                search_with_filters,
                query_vector,
                filters,
                limit,
                settings.QDRANT_HOST,
                settings.QDRANT_PORT,
            )
            if vector_rows:
                for row in vector_rows:
                    add_photo_url(row)
                vector_result = {
                    "sql": "vector_search",
                    "rows": vector_rows,
                    "row_count": len(vector_rows),
                }
                profile_rows = [
                    {"MatriID": row.get("MatriID"), "Name": row.get("Name")}
                    for row in vector_rows if row.get("Name")
                ]
                metadata = {
                    "profile_candidates": profile_rows,
                    "selected_profile": profile_rows[0] if len(profile_rows) == 1 else None,
                    "accumulated_filters": filters,
                } if profile_rows else {"accumulated_filters": filters}

                try:
                    formatted = await format_db_result(message, vector_result, history=history, db=db)
                except Exception:
                    formatted = {"content": f"{len(vector_rows)} जुळणारी प्रोफाइल सापडली.", "usage": {}, "events": []}

                return {
                    "content": formatted["content"],
                    "is_profile_search": True,
                    "usage": formatted.get("usage", {}),
                    "events": formatted.get("events", []),
                    "metadata": metadata,
                }
        except Exception:
            logger.exception("Vector search fallback failed")
        finally:
            # Never keep the ~2GB embedding model resident between requests.
            unload_embedding_model()

        msg = await format_notice_safe(
            message,
            "कोणतेही योग्य प्रोफाइल सापडले नाही. वेगळे शहर, जात किंवा वयोगट वापरून पाहण्याचा सल्ला द्या.",
            history, db, "तुमच्या निवडीनुसार कोणतेही योग्य प्रोफाइल सापडले नाही.",
        )
        return {"content": msg, "is_profile_search": True, "usage": {}, "events": [], "metadata": metadata}

    if sql_result["row_count"] > settings.MAX_ROWS_BEFORE_NARROW:
        msg = await format_notice_safe(
            message,
            f"सर्चमध्ये {sql_result['row_count']} परिणाम सापडले, खूप जास्त म्हणून सर्व दाखवणे शक्य नाही. अधिक criteria जोडण्याचा सल्ला द्या.",
            history, db,
            f"सर्चमध्ये {sql_result['row_count']} परिणाम सापडले, एकाच वेळी सर्व दाखवणे शक्य नाही. कृपया अधिक अचूक criteria निवडा.",
        )
        return {"content": msg, "is_profile_search": True, "usage": {}, "events": [], "metadata": metadata}

    try:
        formatted = await format_db_result(message, sql_result, history=history, db=db)
    except Exception:
        msg = await format_notice_safe(
            message,
            "सर्चमध्ये खूप जास्त परिणाम सापडले. कृपया अधिक अचूक criteria निवडून सर्च अरुंद करा.",
            history, db,
            "सर्चमध्ये खूप जास्त परिणाम सापडले, एकाच वेळी प्रक्रिया करणे शक्य नाही. कृपया सर्च अरुंद करा.",
        )
        return {"content": msg, "is_profile_search": True, "usage": {}, "events": [], "metadata": metadata}

    return {
        "content": formatted["content"],
        "is_profile_search": True,
        "usage": formatted.get("usage", {}),
        "events": formatted.get("events", []),
        "metadata": metadata,
    }


_DETAIL_CATEGORY_QUESTION = (
    "या प्रोफाइलबद्दल तुम्हाला काय जाणून घ्यायचे आहे? मी सांगू शकतो:\n\n"
    "📚 **शिक्षण व करिअर** — education, occupation, income\n"
    "👨‍👩‍👧‍👦 **कौटुंबिक माहिती** — parents, siblings, family values\n"
    "🔮 **जन्मकुंडली व मांगलिक** — star, moon sign, manglik, gotra\n"
    "📍 **स्थान** — city, district, state\n"
    "🏋️ **शारीरिक माहिती** — height, weight, blood group, complexion\n"
    "🌿 **जीवनशैली** — diet, smoking, drinking, hobbies\n"
    "📷 **फोटो व संपर्क** — photo, mobile number\n\n"
    "तुम्हाला कोणत्या माहितीत रस आहे ते सांगा!"
)


async def handle_profile_detail(
    message: str, fields: list[str] | None, limit: int, history, db,
    selected_profile: dict | None = None,
) -> dict:
    from app.services.query_builder import build_detail_query

    matri_id = selected_profile.get("MatriID") if selected_profile else None
    name = selected_profile.get("Name") if selected_profile else None

    if not matri_id and not name:
        msg = await format_notice_safe(
            message,
            "तुम्हाला कोणत्या प्रोफाइलची माहिती हवी आहे? कृपया आधी एक प्रोफाइल निवडा.",
            history, db,
            "तुम्हाला कोणत्या प्रोफाइलची माहिती हवी आहे? कृपया आधी एक प्रोफाइल निवडा.",
        )
        return {"content": msg, "is_profile_search": False, "usage": {}, "events": [], "metadata": None}

    if fields in (None, ["all"]):
        return {"content": _DETAIL_CATEGORY_QUESTION, "is_profile_search": False, "usage": {}, "events": [], "metadata": {"selected_profile": selected_profile, "accumulated_filters": {}}}

    sql, params = build_detail_query(matri_id=matri_id, name=name, fields=fields, limit=limit)
    sql_result = await execute_param_query(sql, params)

    if not sql_result.get("rows"):
        msg = await format_notice_safe(message, "प्रोफाइल सापडली नाही.", history, db, "प्रोफाइल सापडली नाही.")
        return {"content": msg, "is_profile_search": True, "usage": {}, "events": [], "metadata": None}

    from app.services.llm_service import format_db_result

    for row in sql_result["rows"]:
        add_photo_url(row)

    if message_asks_about_unavailable_attribute(message):
        msg = await format_notice_safe(
            message,
            "ही माहिती डेटाबेसमध्ये उपलब्ध नाही.",
            history, db,
            "ही माहिती डेटाबेसमध्ये उपलब्ध नाही.",
        )
        return {
            "content": msg,
            "is_profile_search": True, "usage": {}, "events": [],
            "metadata": {"selected_profile": selected_profile, "accumulated_filters": {}},
        }

    try:
        formatted = await format_db_result(message, sql_result, history=history, db=db)
    except Exception:
        formatted = {"content": "येथे प्रोफाइलची माहिती आहे.", "usage": {}, "events": []}

    return {
        "content": formatted["content"],
        "is_profile_search": True,
        "usage": formatted.get("usage", {}),
        "events": formatted.get("events", []),
        "metadata": {
            "selected_profile": selected_profile,
            "accumulated_filters": {},
        },
    }


_COMPARE_FIELDS = [
    ("Age", "वय"),
    ("Gender", "लिंग"),
    ("Maritalstatus", "वैवाहिक स्थिती"),
    ("Education", "शिक्षण"),
    ("Occupation", "व्यवसाय"),
    ("City", "शहर"),
    ("Caste", "जात"),
    ("Religion", "धर्म"),
    ("Height", "उंची"),
    ("Annualincome", "वार्षिक उत्पन्न"),
]


def format_profile_comparison(profile_a: dict, profile_b: dict) -> str:
    """Zero-LLM bilingual comparison table for two profiles. Never invents
    data — missing columns render as '—'."""
    name_a = profile_a.get("Name") or "प्रोफाइल 1"
    name_b = profile_b.get("Name") or "प्रोफाइल 2"
    lines = [f"प्रोफाइल तुलना:\n1. {name_a}\n2. {name_b}", ""]
    for col, label in _COMPARE_FIELDS:
        va = str(profile_a.get(col)) if profile_a.get(col) else "—"
        vb = str(profile_b.get(col)) if profile_b.get(col) else "—"
        lines.append(f"{label}: {va} | {vb}")
    return "\n".join(lines)


def resolve_comparison(
    selected_index: int | None,
    selected_reference: str | None,
    candidates: list[dict] | None,
    current_selected: dict | None,
) -> tuple[tuple[dict, dict] | None, str | None]:
    """Resolve the two profiles for a comparison request.

    The explicitly referenced profile ("second", "the CA girl") becomes the
    second entry; the first entry is the most recently discussed profile, or
    the first candidate when none has been selected. Returns (pair, None) on
    success or (None, clarification) when the pair cannot be resolved."""
    candidates = list(candidates) if candidates else []

    second = None
    if selected_index is not None:
        try:
            idx = int(selected_index) - 1
            if 0 <= idx < len(candidates):
                second = candidates[idx]
        except (ValueError, TypeError):
            second = None
    if second is None and selected_reference:
        ref = str(selected_reference).lower().strip()
        matches = []
        for cand in candidates:
            for key in ["Name", "Occupation", "Education", "City", "Maritalstatus", "Religion", "Caste"]:
                val = cand.get(key)
                if val and ref in str(val).lower():
                    matches.append(cand)
                    break
        if len(matches) == 1:
            second = matches[0]
        elif len(matches) > 1:
            names = ", ".join(f"'{c.get('Name')}'" for c in matches if c.get("Name"))
            return None, f"'{selected_reference}' साठी अनेक जुळणाऱ्या प्रोफाइल आढळल्या: {names}. कोणत्या दोनची तुलना करायची ते सांगा."

    first = current_selected
    if first is None and candidates:
        first = candidates[0]

    if first is None or second is None:
        return None, "कोणत्या दोन प्रोफाइलची तुलना करायची आहे? उदा. 'पहिली आणि दुसरी तुलना करा'."

    a_id = first.get("MatriID")
    b_id = second.get("MatriID")
    if a_id and b_id and str(a_id) == str(b_id):
        return None, "तुम्ही एकाच प्रोफाइलची निवड केली आहे. कृपया दोन वेगळ्या प्रोफाइलचा उल्लेख करा."

    return (first, second), None


async def handle_profile_comparison(
    message: str,
    selected_index: int | None,
    selected_reference: str | None,
    history,
    db,
    candidates: list[dict] | None,
    selected_profile: dict | None,
) -> dict:
    from app.services.query_builder import build_detail_query

    pair, clarification = resolve_comparison(
        selected_index, selected_reference, candidates, selected_profile
    )
    if clarification:
        return {
            "content": clarification,
            "is_profile_search": False,
            "usage": {}, "events": [],
            "metadata": {
                "profile_candidates": candidates,
                "selected_profile": selected_profile,
            },
        }

    first, second = pair
    rows = []
    for prof in (first, second):
        matri_id = prof.get("MatriID")
        name = prof.get("Name")
        sql, params = build_detail_query(matri_id=matri_id, name=name, fields=["all"], limit=1)
        sql_result = await execute_param_query(sql, params)
        row = sql_result["rows"][0] if sql_result.get("rows") else prof
        add_photo_url(row)
        rows.append(row)

    return {
        "content": format_profile_comparison(rows[0], rows[1]),
        "is_profile_search": False,
        "usage": {}, "events": [],
        "metadata": {
            "profile_candidates": candidates,
            "selected_profile": second,
            "cached_profile_data": rows[1],
            "compared_pair": [
                {"MatriID": rows[0].get("MatriID"), "Name": rows[0].get("Name")},
                {"MatriID": rows[1].get("MatriID"), "Name": rows[1].get("Name")},
            ],
        },
    }


def resolve_contextual_profile(
    selected_index: int | None,
    selected_reference: str | None,
    candidates: list[dict] | None,
    current_selected: dict | None
) -> tuple[dict | None, str | None]:
    if not candidates:
        return current_selected, None

    # 1. Resolve by index
    if selected_index is not None:
        try:
            idx = int(selected_index) - 1
            if 0 <= idx < len(candidates):
                return candidates[idx], None
        except (ValueError, TypeError):
            pass

    # 2. Resolve by descriptive reference (Semantic reference resolution)
    if selected_reference:
        ref = str(selected_reference).lower().strip()
        matches = []
        for cand in candidates:
            match_found = False
            for key in ["Name", "Occupation", "Education", "City", "Maritalstatus", "Religion", "Caste"]:
                val = cand.get(key)
                if val and ref in str(val).lower():
                    match_found = True
                    break
            if match_found:
                matches.append(cand)

        # Confidence-based Decision Making
        if len(matches) == 1:
            # Exactly one matches -> HIGH confidence, proceed automatically!
            return matches[0], None
        elif len(matches) > 1:
            # Multiple matches -> LOW confidence, ask for clarification.
            names = ", ".join([f"'{c.get('Name')}'" for c in matches if c.get("Name")])
            clarification = f"'{selected_reference}' साठी अनेक जुळणारी प्रोफाइल सापडली: {names}. तुम्हाला कोणती अपेक्षित आहे?"
            return None, clarification

    return current_selected, None


async def answer_database_question_hybrid(
    message: str,
    history: list[dict] | None = None,
    db=None,
    conversation_context: dict | None = None,
) -> dict:
    from app.services.extraction_service import extract_search_params

    ctx = conversation_context or {}
    accumulated_filters = ctx.get("accumulated_filters") or {}
    selected_profile = ctx.get("selected_profile")
    candidates = ctx.get("profile_candidates")

    extraction = await extract_search_params(message, history=history, db=db)
    intent = extraction.get("intent", "general")
    intent_label = extraction.get("intent_label") or intent

    if intent_label == "comparison":
        return await handle_profile_comparison(
            message,
            extraction.get("selected_index"),
            extraction.get("selected_reference"),
            history, db,
            candidates, selected_profile,
        )

    if intent == "profile_detail":
        selected_index = extraction.get("selected_index")
        selected_reference = extraction.get("selected_reference")

        resolved, clarification = resolve_contextual_profile(
            selected_index, selected_reference, candidates, selected_profile
        )
        if clarification:
            return {
                "content": clarification,
                "is_profile_search": False,
                "usage": {},
                "events": [],
                "metadata": {
                    "selected_profile": selected_profile,
                    "accumulated_filters": accumulated_filters,
                    "profile_candidates": candidates,
                }
            }

        selected_profile = resolved
        result = await handle_profile_detail(
            message,
            fields=extraction.get("fields"),
            limit=extraction.get("limit", 1),
            history=history,
            db=db,
            selected_profile=selected_profile,
        )
        if result.get("metadata"):
            result["metadata"]["profile_candidates"] = candidates
        return result

    if intent != "profile_search":
        return {"content": None, "is_profile_search": False, "usage": {}, "events": [], "metadata": None}

    default_filters = ctx.get("default_filters") or {}
    new_filters = extraction.get("filters", {})
    filters = merge_filters(merge_filters(default_filters, accumulated_filters), new_filters)
    limit = extraction.get("limit", 10)

    return await handle_profile_search(
        message,
        filters,
        limit,
        history,
        db,
        deterministic=bool(extraction.get("deterministic")),
    )


def get_database_stats() -> dict:
    results = {}
    tables = {
        "total_members": "SELECT COUNT(*) as c FROM register",
        "active_members": "SELECT COUNT(*) as c FROM register WHERE Status='Active'",
        "paid_members": "SELECT COUNT(*) as c FROM register WHERE Status='Paid'",
        "banned_members": "SELECT COUNT(*) as c FROM register WHERE Status='Banned'",
        "male_members": "SELECT COUNT(*) as c FROM register WHERE Gender='Male' AND Status IN ('Active','Paid')",
        "female_members": "SELECT COUNT(*) as c FROM register WHERE Gender='Female' AND Status IN ('Active','Paid')",

        "success_stories": "SELECT COUNT(*) as c FROM successstory",
    }
    for key, sql in tables.items():
        row = safe_query(sql, fetch_one=True)
        results[key] = row["c"] if row else 0
    return results
