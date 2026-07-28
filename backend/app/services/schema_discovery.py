import functools
import threading
from app.config import settings
from app.core.logger import logger


LOOKUP_TABLES = {
    "caste": "Caste",
    "caste2": "Caste",
    "religion": "Religion",
    "education": "Education",
    "occupation": "Occupation",
    "occupation2": "Occupation",
    "language": "Language",
    "mother_tounge": "MotherTongue",
    "maritial_status": "Maritalstatus",
    "income": "Income",
    "income1": "Income",
}

SEARCH_COLUMNS = [
    "Caste", "Subcaste", "Religion", "City", "Dist", "State",
    "Education", "Occupation", "Maritalstatus", "Gender",
    "Complexion", "Diet", "Smoke", "Drink", "Manglik",
    "Bodytype", "BloodGroup", "Language", "Employedin",
    "Familyvalues", "FamilyType", "FamilyStatus",
]


_schema_cache = None
_schema_lock = threading.Lock()


def _sync_fetch_all() -> dict:
    import mysql.connector

    conn = mysql.connector.connect(
        host=settings.DB_HOST, port=settings.DB_PORT,
        user=settings.DB_USER, password=settings.DB_PASSWORD,
        database=settings.DB_NAME, connect_timeout=settings.DB_CONNECT_TIMEOUT,
    )
    cur = conn.cursor()

    info = {"tables": {}, "lookup_values": {}, "distinct_values": {}}

    cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = %s", (settings.DB_NAME,))
    all_tables = [r[0] for r in cur.fetchall() if r[0] != "ignore"]

    for t in all_tables:
        cur.execute(
            "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY "
            "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
            (settings.DB_NAME, t),
        )
        info["tables"][t] = [
            {"name": r[0], "type": r[1], "nullable": r[2] == "YES", "key": r[3]}
            for r in cur.fetchall()
        ]

    for table, label in LOOKUP_TABLES.items():
        try:
            cur.execute(f"SELECT DISTINCT `{label}` FROM `{table}` WHERE `{label}` IS NOT NULL ORDER BY 1")
            values = [r[0] for r in cur.fetchall()]
            if values:
                info["lookup_values"][table] = values
        except Exception:
            pass

    for col in SEARCH_COLUMNS:
        try:
            cur.execute(
                f"SELECT DISTINCT `{col}` FROM `register` "
                f"WHERE `{col}` IS NOT NULL AND `{col}` != '' "
                f"ORDER BY 1 LIMIT 200"
            )
            values = [r[0] for r in cur.fetchall()]
            if values:
                info["distinct_values"][col] = values
        except Exception:
            pass

    cur.close()
    conn.close()
    return info


def refresh_cache():
    global _schema_cache
    with _schema_lock:
        try:
            _schema_cache = _sync_fetch_all()
            logger.info("Schema cache refreshed")
        except Exception as e:
            logger.error(f"Schema refresh failed: {e}")


def get_schema() -> dict:
    if _schema_cache is None:
        refresh_cache()
    return _schema_cache or {}


def get_distinct_values(column: str) -> list[str]:
    schema = get_schema()
    values = schema.get("distinct_values", {}).get(column, [])
    if values:
        return values
    for table_vals in schema.get("lookup_values", {}).values():
        if isinstance(table_vals, list):
            return table_vals
    return []


def get_all_castes() -> list[str]:
    schema = get_schema()
    castes = schema.get("distinct_values", {}).get("Caste", [])
    if not castes:
        castes = schema.get("lookup_values", {}).get("caste", [])
    return castes


def get_all_religions() -> list[str]:
    schema = get_schema()
    rels = schema.get("distinct_values", {}).get("Religion", [])
    if not rels:
        rels = schema.get("lookup_values", {}).get("religion", [])
    return rels


def get_all_cities() -> list[str]:
    return get_schema().get("distinct_values", {}).get("City", [])


def get_all_educations() -> list[str]:
    schema = get_schema()
    edu = schema.get("distinct_values", {}).get("Education", [])
    if not edu:
        edu = schema.get("lookup_values", {}).get("education", [])
    return edu


def get_all_occupations() -> list[str]:
    schema = get_schema()
    occ = schema.get("distinct_values", {}).get("Occupation", [])
    if not occ:
        occ = schema.get("lookup_values", {}).get("occupation", [])
    return occ


REGISTER_COLUMN_CATEGORIES = {
    "Identity & Basic": ["MatriID", "Name", "Gender", "Age", "DOB", "Maritalstatus"],
    "Religion & Caste": ["Religion", "Caste", "Subcaste", "Gothram", "Manglik", "Star", "Moonsign"],
    "Contact & Location": ["Mobile", "Email", "Phone", "City", "Dist", "State", "Country", "Residencystatus", "Nationality"],
    "Education & Career": ["Education", "EducationDetails", "Occupation", "Employedin", "Annualincome"],
    "Physical Attributes": ["Height", "Weight", "BloodGroup", "Bodytype", "Complexion"],
    "Lifestyle": ["Diet", "Smoke", "Drink", "Language", "Hobbies", "Interests"],
    "Family": ["Fathername", "Mothersname", "Fathersoccupation", "Mothersoccupation", "noofbrothers", "noofsisters", "Familyvalues", "FamilyType", "FamilyStatus"],
    "Horoscope": ["Birthplace", "Birthtime", "Nakshatra", "Charan", "Rasi", "Gan", "Nadi"],
    "Photos & System": ["Photo1", "Photo2", "Photo3", "Photo4", "Photo5", "Status", "Regdate", "RegEmail", "Username"],
    "About": ["AboutMyself", "PartnerExpectations"],
}


def build_schema_context() -> str:
    schema = get_schema()
    lines = ["## Database Schema (register table — member profiles) ##", ""]

    for category, cols in REGISTER_COLUMN_CATEGORIES.items():
        existing = [c for c in cols if any(tc["name"] == c for tc in schema.get("tables", {}).get("register", []))]
        if existing:
            lines.append(f"  {category}: {', '.join(existing)}")

    for table, cols in schema.get("tables", {}).items():
        if table in ("ignore", "register") or len(cols) > 30:
            continue
        col_names = [c["name"] for c in cols[:10]]
        lines.append(f"  {table}: {', '.join(col_names)}")

    lines.append("")
    lines.append("## Valid DISTINCT values for key columns ##")
    lines.append("")
    lines.append("Castes: " + ", ".join(get_all_castes()[:50]))
    lines.append("Religions: " + ", ".join(get_all_religions()))
    cities = get_all_cities()
    if cities:
        lines.append("Cities: " + ", ".join(cities[:40]))
    edu = get_all_educations()
    if edu:
        lines.append("Education: " + ", ".join(edu[:25]))
    occ = get_all_occupations()
    if occ:
        lines.append("Occupation: " + ", ".join(occ[:25]))
    diet = get_distinct_values("Diet")
    if diet:
        lines.append("Diet values: " + ", ".join(diet))
    manglik = get_distinct_values("Manglik")
    if manglik:
        lines.append("Manglik values: " + ", ".join(manglik))
    marital = get_distinct_values("Maritalstatus")
    if marital:
        lines.append("Marital Status values: " + ", ".join(marital))

    return "\n".join(lines)


def get_register_column_names() -> list[str]:
    all_cols = []
    for cols in REGISTER_COLUMN_CATEGORIES.values():
        all_cols.extend(cols)
    return all_cols
