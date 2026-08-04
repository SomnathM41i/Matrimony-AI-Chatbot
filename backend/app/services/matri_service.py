import re
from app.config import settings
from app.core.logger import logger
from app.services.db_query_service import execute_param_query


MATRI_ID_PATTERN = re.compile(r"^[A-Za-z0-9]+$")

_ANY_VALUES = {"", "any", "anyone", "not specified", "not specifed", "not applicable", "na", "none", "-", "0"}

REGISTER_PE_COLUMNS = [
    "MatriID", "Name", "Gender", "Age", "Photo1",
    "PE_FromAge", "PE_ToAge", "PE_HaveChildren",
    "PE_from_Height", "PE_to_Height", "PE_Height2",
    "PE_Complexion", "PE_MotherTongue", "PE_Religion", "PE_Caste",
    "PE_subcaste", "PE_Education", "PE_Occupation",
    "PE_Countrylivingin", "PE_Residentstatus", "PE_State", "PE_City",
    "PE_income_from", "PE_income_to", "PartnerExpectations",
]

# Rich member-profile columns (CF-2) — all verified to exist in the live
# register table. Used for the zero-LLM Marathi profile summary.
REGISTER_PROFILE_COLUMNS = list(dict.fromkeys([
    "MatriID", "Name", "Gender", "Age", "Photo1",
    "Maritalstatus", "Height", "Weight",
    "Education", "EducationDetails", "Occupation", "Employedin", "Annualincome",
    "Religion", "Caste", "Subcaste", "Gothram", "Manglik", "Language",
    "Diet", "Smoke", "Drink",
    "City", "Dist", "State", "Country", "Residencystatus",
    "Familyvalues", "FamilyType", "FamilyStatus",
    "Fathername", "Mothersname",
    "Hobbies",
] + REGISTER_PE_COLUMNS))

SAVED_SEARCH_COLUMNS = {
    "advance_saveandsearch": [
        "maritialstatus", "fromage", "toage", "fromheight", "toheight",
        "religion", "caste", "subcaste", "education", "occupation",
        "country", "state", "district", "city",
    ],
    "basic_saveandsearch": [
        "fromage", "toage", "religion", "education", "occupation",
        "Maritial_status", "caste", "subcaste",
    ],
}


class MatriLinkError(ValueError):
    pass


def normalize_matri_id(matri_id: str | None) -> str:
    value = (matri_id or "").strip()
    if not value:
        raise MatriLinkError("MatriID is required")
    if len(value) > 15:
        raise MatriLinkError("MatriID is too long")
    if not MATRI_ID_PATTERN.match(value):
        raise MatriLinkError("MatriID can contain only letters and numbers")
    return value.upper()


def _clean(value):
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lower() in _ANY_VALUES:
            return None
        return stripped
    return value


def _partner_gender(gender: str | None) -> str | None:
    if not gender:
        return None
    g = gender.lower()
    if g in ("male", "m", "men"):
        return "Female"
    if g in ("female", "f", "women"):
        return "Male"
    return None


def _photo_url(value) -> str:
    photo = (value or "").strip()
    if photo and photo.lower() != "nophoto.jpg":
        return settings.PHOTO_BASE_URL.rstrip("/") + "/" + photo.lstrip("/")
    return ""


async def _fetch_register_row(matri_id: str) -> dict | None:
    sql = (
        f"SELECT {', '.join(REGISTER_PROFILE_COLUMNS)} "
        "FROM register WHERE MatriID = %s LIMIT 1"
    )
    result = await execute_param_query(sql, [matri_id])
    rows = result.get("rows") or []
    return rows[0] if rows else None


async def _fetch_latest_saved_search(matri_id: str) -> dict | None:
    for table, columns in SAVED_SEARCH_COLUMNS.items():
        sql = (
            f"SELECT {', '.join(columns)} "
            f"FROM {table} WHERE MatriID = %s ORDER BY id DESC LIMIT 1"
        )
        result = await execute_param_query(sql, [matri_id])
        rows = result.get("rows") or []
        if rows:
            return {"source": table, **rows[0]}
    return None


_PE_TO_FILTER = {
    "PE_FromAge": "age_min",
    "PE_ToAge": "age_max",
    "PE_from_Height": "height_min",
    "PE_to_Height": "height_max",
    "PE_Complexion": "complexion",
    "PE_MotherTongue": "language",
    "PE_Religion": "religion",
    "PE_Caste": "caste",
    "PE_subcaste": "subcaste",
    "PE_Education": "education",
    "PE_Occupation": "occupation",
    "PE_Countrylivingin": "country",
    "PE_Residentstatus": "residency_status",
    "PE_State": "state",
    "PE_City": "city",
    "PE_income_from": "income_min",
    "PE_income_to": "income_max",
}

_PE_DISPLAY = {
    "PE_FromAge": "Partner Age From",
    "PE_ToAge": "Partner Age To",
    "PE_from_Height": "Partner Height From",
    "PE_to_Height": "Partner Height To",
    "PE_Complexion": "Complexion",
    "PE_MotherTongue": "Mother Tongue",
    "PE_Religion": "Religion",
    "PE_Caste": "Caste",
    "PE_subcaste": "Subcaste",
    "PE_Education": "Education",
    "PE_Occupation": "Occupation",
    "PE_Countrylivingin": "Country",
    "PE_Residentstatus": "Residency Status",
    "PE_State": "State",
    "PE_City": "City",
    "PE_income_from": "Income From",
    "PE_income_to": "Income To",
    "PE_HaveChildren": "Accepted Children",
}


def _extract_pe_filters(row: dict) -> dict:
    filters = {}
    for pe_col, filter_key in _PE_TO_FILTER.items():
        value = _clean(row.get(pe_col))
        if value is not None:
            filters[filter_key] = value
    partner_gender = _partner_gender(row.get("Gender"))
    if partner_gender:
        filters["gender"] = partner_gender
    return filters


def _extract_pe_summary(row: dict) -> dict:
    summary = {}
    for pe_col, label in _PE_DISPLAY.items():
        value = _clean(row.get(pe_col))
        if value is not None:
            summary[label] = value
    return summary


# Marathi profile + partner-preference labels for the zero-LLM chat summary.
_PROFILE_LABELS_MR = [
    ("Name", "नाव"),
    ("Age", "वय"),
    ("Maritalstatus", "वैवाहिक स्थिती"),
    ("Height", "उंची"),
    ("Education", "शिक्षण"),
    ("Occupation", "व्यवसाय"),
    ("Employedin", "रोजगार"),
    ("Annualincome", "वार्षिक उत्पन्न"),
    ("Religion", "धर्म"),
    ("Caste", "जात"),
    ("Subcaste", "उपजात"),
    ("Gothram", "गोत्र"),
    ("Manglik", "मांगलिक"),
    ("Language", "मातृभाषा"),
    ("Diet", "आहार"),
    ("Smoke", "धूम्रपान"),
    ("Drink", "मद्यपान"),
    ("City", "शहर"),
    ("Dist", "जिल्हा"),
    ("State", "राज्य"),
    ("Country", "देश"),
    ("Residencystatus", "निवासस्थान"),
    ("Familyvalues", "कौटुंबिक मूल्ये"),
    ("FamilyType", "कुटुंब प्रकार"),
    ("FamilyStatus", "कौटुंबिक स्थिती"),
    ("Fathername", "वडिलांचे नाव"),
    ("Mothersname", "आईचे नाव"),
    ("Hobbies", "छंद"),
]

_PE_LABELS_MR = {
    "PE_FromAge": "जोडीदाराचे किमान वय",
    "PE_ToAge": "जोडीदाराचे कमाल वय",
    "PE_from_Height": "जोडीदाराची किमान उंची",
    "PE_to_Height": "जोडीदाराची कमाल उंची",
    "PE_Complexion": "जोडीदाराची त्वचा/रंग",
    "PE_MotherTongue": "जोडीदाराची मातृभाषा",
    "PE_Religion": "जोडीदाराचा धर्म",
    "PE_Caste": "जोडीदाराची जात",
    "PE_subcaste": "जोडीदाराची उपजात",
    "PE_Education": "जोडीदाराचे शिक्षण",
    "PE_Occupation": "जोडीदाराचा व्यवसाय",
    "PE_Countrylivingin": "जोडीदाराचा देश",
    "PE_Residentstatus": "जोडीदाराची निवासी स्थिती",
    "PE_State": "जोडीदाराचे राज्य",
    "PE_City": "जोडीदाराचे शहर",
    "PE_income_from": "जोडीदाराचे उत्पन्न (किमान)",
    "PE_income_to": "जोडीदाराचे उत्पन्न (कमाल)",
    "PE_HaveChildren": "मुले स्वीकार्य",
}


def _extract_profile_summary(row: dict) -> dict:
    profile = {}
    for col, _label in _PROFILE_LABELS_MR:
        value = _clean(row.get(col))
        if value is not None:
            profile[col] = value
    return profile


def _extract_pe_summary_mr(row: dict) -> dict:
    summary = {}
    for pe_col, label in _PE_LABELS_MR.items():
        value = _clean(row.get(pe_col))
        if value is not None:
            summary[label] = value
    return summary


def format_user_profile_summary(profile: dict, pe_summary_mr: dict | None = None) -> str:
    """Zero-LLM Marathi member + partner-preference summary, shown once after a
    successful MatriID link. Returns "" when there is nothing meaningful to show."""
    lines = []
    profile_items = [
        (label, _clean(profile.get(col)))
        for col, label in _PROFILE_LABELS_MR
    ]
    profile_items = [(label, value) for label, value in profile_items if value is not None]
    if profile_items:
        lines.append("📋 **तुमचे प्रोफाइल:**")
        lines.extend(f"• {label}: {value}" for label, value in profile_items)

    pe_items = [
        (label, _clean(value))
        for label, value in (pe_summary_mr or {}).items()
    ]
    pe_items = [(label, value) for label, value in pe_items if value is not None]
    if pe_items:
        if lines:
            lines.append("")
        lines.append("🎯 **तुमच्या जोडीदाराच्या पसंती:**")
        lines.extend(f"• {label}: {value}" for label, value in pe_items)

    return "\n".join(lines)


_BIODATA_EXTRA_LABELS_MR = {
    "EducationDetails": "शिक्षणाचा तपशील",
    "Star": "तारा (जन्म नक्षत्र)",
    "Moonsign": "राशी",
    "Complexion": "त्वचा/रंग",
    "BloodGroup": "रक्तगट",
    "Bodytype": "शरीर प्रकार",
    "Fathersoccupation": "वडिलांचा व्यवसाय",
    "Mothersoccupation": "आईचा व्यवसाय",
    "noofbrothers": "भाऊ",
    "noofsisters": "बहिणी",
    "Interests": "आवडी",
}

_BIODATA_LABELS_MR = dict(_PROFILE_LABELS_MR)
_BIODATA_LABELS_MR.update(_BIODATA_EXTRA_LABELS_MR)

# CF-6: sections of the chat-embedded rich biodata. Rendered zero-LLM from a full
# register row; the chip (emoji + title) is clickable and maps to the section key.
BIODATA_SECTIONS = [
    {"key": "basic", "emoji": "👤", "title": "मूलभूत माहिती",
     "fields": ["Age", "Maritalstatus", "Height"]},
    {"key": "education", "emoji": "📚", "title": "शिक्षण व करिअर",
     "fields": ["Education", "EducationDetails", "Occupation", "Employedin", "Annualincome"]},
    {"key": "family", "emoji": "👨‍👩‍👧‍👦", "title": "कौटुंबिक माहिती",
     "fields": ["Familyvalues", "FamilyType", "FamilyStatus", "Fathername",
                "Mothersname", "Fathersoccupation", "Mothersoccupation",
                "noofbrothers", "noofsisters"]},
    {"key": "physical", "emoji": "🏋️", "title": "शारीरिक माहिती",
     "fields": ["Weight", "Bodytype", "Complexion", "BloodGroup"]},
    {"key": "lifestyle", "emoji": "🌿", "title": "जीवनशैली",
     "fields": ["Diet", "Smoke", "Drink", "Hobbies", "Interests"]},
    {"key": "horoscope", "emoji": "🔮", "title": "जन्मकुंडली व मांगलिक",
     "fields": ["Star", "Moonsign", "Manglik", "Gothram", "Language"]},
    {"key": "partner", "emoji": "🎯", "title": "जोडीदाराच्या पसंती",
     "fields": list(_PE_LABELS_MR)},
    {"key": "location", "emoji": "📍", "title": "स्थान",
     "fields": ["City", "Dist", "State", "Country", "Residencystatus"]},
]

BIODATA_SECTION_ROUTES = {
    f"{section['emoji']} {section['title']}": section["key"]
    for section in BIODATA_SECTIONS
}

BIODATA_SECTION_CHIPS = list(BIODATA_SECTION_ROUTES)


def _format_biodata_section(row: dict, section: dict) -> str | None:
    items = []
    for col in section["fields"]:
        label = _BIODATA_LABELS_MR.get(col) or _PE_LABELS_MR.get(col)
        value = _clean(row.get(col))
        if label and value is not None:
            items.append(f"• {label}: {value}")
    if not items:
        return None
    return f"{section['emoji']} **{section['title']}:**\n" + "\n".join(items)


def format_profile_section(row: dict, section_key: str) -> str | None:
    """Zero-LLM Marathi block for a single biodata section, or None when the row
    has no non-empty value for any field in the section."""
    section = next(
        (s for s in BIODATA_SECTIONS if s["key"] == section_key), None
    )
    if section is None:
        return None
    return _format_biodata_section(row, section)


def format_profile_biodata(row: dict) -> str:
    """Zero-LLM sectioned Marathi biodata for any register profile, rendered
    embedded in chat. Returns a header + photo + all non-empty sections."""
    name = _clean(row.get("Name")) or "प्रोफाइल"
    matri_id = _clean(row.get("MatriID")) or ""
    photo = _photo_url(row.get("Photo1"))
    parts = [f"👤 **{name}**" + (f" · {matri_id}" if matri_id else "")]
    if photo:
        parts.append(f"![{name}]({photo})")
    for section in BIODATA_SECTIONS:
        block = _format_biodata_section(row, section)
        if block:
            parts.append(block)
    return "\n\n".join(parts)


def _merge_saved_search(filters: dict, saved: dict | None) -> dict:
    if not saved:
        return filters
    mapping = {
        "maritialstatus": "marital_status",
        "Maritial_status": "marital_status",
        "fromage": "age_min",
        "toage": "age_max",
        "fromheight": "height_min",
        "toheight": "height_max",
        "religion": "religion",
        "caste": "caste",
        "subcaste": "subcaste",
        "education": "education",
        "occupation": "occupation",
        "country": "country",
        "state": "state",
        "district": "dist",
        "city": "city",
    }
    for col, filter_key in mapping.items():
        if filter_key in filters and filters[filter_key]:
            continue
        value = _clean(saved.get(col))
        if value is not None:
            filters[filter_key] = value
    return filters


async def fetch_partner_expectations(matri_id: str) -> dict:
    row = await _fetch_register_row(matri_id)
    if not row:
        raise MatriLinkError("No member found with this MatriID")

    filters = _extract_pe_filters(row)
    saved = await _fetch_latest_saved_search(matri_id)
    merged = _merge_saved_search(dict(filters), saved)

    return {
        "member": {
            "matri_id": row.get("MatriID"),
            "name": row.get("Name"),
            "gender": row.get("Gender"),
            "age": row.get("Age"),
            "photo_url": _photo_url(row.get("Photo1")),
        },
        "filters": merged,
        "summary": _extract_pe_summary(row),
        "profile": _extract_profile_summary(row),
        "pe_summary_mr": _extract_pe_summary_mr(row),
        "saved_search_used": bool(saved),
        "saved_search_source": saved.get("source") if saved else None,
    }


async def link_matri_id(matri_id: str) -> dict:
    normalized = normalize_matri_id(matri_id)
    result = await fetch_partner_expectations(normalized)
    logger.info("MatriID linked: %s (%s)", normalized, result["member"].get("name"))
    return result


async def link_matri_id_to_user(db, user, matri_id: str) -> dict:
    """Link a MatriID to a user account and persist the extracted partner
    expectations. The caller owns the surrounding transaction."""
    from datetime import datetime, timezone
    from app.repositories.preference_repository import PreferenceRepository

    result = await link_matri_id(matri_id)
    user.matri_id = normalize_matri_id(matri_id)
    user.matri_name = result["member"].get("name")
    user.matri_synced_at = datetime.now(timezone.utc)
    await PreferenceRepository(db).replace_all(
        user.id, result["filters"], source="pe", matri_id=user.matri_id
    )
    await db.flush()
    return result


def start_questionnaire(pe_filters: dict | None = None) -> dict:
    from app.core.questionnaire import build_nodes, current_node, apply_answers, serialize_node, QuestionnaireError

    try:
        nodes, entry_seqs, total = build_nodes(pe_filters or {})
    except QuestionnaireError:
        raise
    node = current_node(nodes, entry_seqs, [])
    if node is None:
        return {"done": True, "filters": {}, "node": None}
    index = nodes.index(node)
    return {
        "done": False,
        "node": serialize_node(node, index, total, apply_answers(nodes, [], pe_filters)),
    }


def advance_questionnaire(pe_filters: dict | None, answers: list[dict]) -> dict:
    from app.core.questionnaire import (
        build_nodes, current_node, apply_answers, serialize_node,
        validate_answer, _find_node, QuestionnaireError,
    )

    nodes, entry_seqs, total = build_nodes(pe_filters or {})

    for answer in answers or []:
        node = _find_node(nodes, answer.get("node_id"))
        if node is None:
            raise QuestionnaireError("Answer references an unknown question.")
        error = validate_answer(node, answer)
        if error:
            raise QuestionnaireError(error)

    filters = apply_answers(nodes, answers, pe_filters)
    node = current_node(nodes, entry_seqs, answers)
    if node is None:
        return {"done": True, "filters": filters, "node": None}
    index = nodes.index(node)
    return {
        "done": False,
        "node": serialize_node(node, index, total, filters),
    }

