from typing import Any


FIELD_MAP = {
    "gender": "Gender",
    "caste": "Caste",
    "religion": "Religion",
    "marital_status": "Maritalstatus",
    "education": "Education",
    "occupation": "Occupation",
    "subcaste": "Subcaste",
    "gotra": "Gothram",
    "gothram": "Gothram",
    "manglik": "Manglik",
    "complexion": "Complexion",
    "diet": "Diet",
    "smoke": "Smoke",
    "drink": "Drink",
    "body_type": "Bodytype",
    "blood_group": "BloodGroup",
    "employed_in": "Employedin",
    "language": "Language",
    "mother_tongue": "Language",
    "residency_status": "Residencystatus",
    "family_values": "Familyvalues",
    "family_type": "FamilyType",
    "family_status": "FamilyStatus",
}

DETAIL_COLUMNS = [
    "MatriID", "Name", "Age", "Gender", "Maritalstatus",
    "Education", "EducationDetails", "Occupation", "Employedin", "Annualincome",
    "Religion", "Caste", "Subcaste", "Gothram", "Language",
    "Star", "Moonsign", "Manglik",
    "Height", "Weight", "BloodGroup", "Bodytype", "Complexion",
    "Diet", "Smoke", "Drink",
    "City", "Dist", "State", "Country", "Residencystatus",
    "Familyvalues", "FamilyType", "FamilyStatus",
    "Fathername", "Mothersname", "Fathersoccupation", "Mothersoccupation",
    "noofbrothers", "noofsisters",
    "Hobbies", "Interests",
    "AboutMyself", "PartnerExpectations",
]

COLUMN_GROUPS = {
    "education": ["Education", "EducationDetails"],
    "career": ["Occupation", "Employedin", "Annualincome"],
    "income": ["Annualincome"],
    "family": ["Familyvalues", "FamilyType", "FamilyStatus", "Fathername",
               "Mothersname", "Fathersoccupation", "Mothersoccupation",
               "noofbrothers", "noofsisters"],
    "horoscope": ["Star", "Moonsign", "Manglik", "Gothram"],
    "manglik": ["Manglik"],
    "gotra": ["Gothram"],
    "gothram": ["Gothram"],
    "location": ["City", "Dist", "State", "Country", "Residencystatus"],
    "physical": ["Height", "Weight", "BloodGroup", "Bodytype", "Complexion"],
    "lifestyle": ["Diet", "Smoke", "Drink", "Hobbies", "Interests"],
    "photo": ["Photo1"],
    "contact": ["Mobile"],
    "all": DETAIL_COLUMNS + ["Photo1", "Mobile"],
}

SEARCH_SSL = "SELECT Photo1, Name, Age, Gender, Maritalstatus, Religion, Caste, City, Status "


def _resolve_columns(fields: list[str] | None) -> list[str]:
    if not fields:
        return DETAIL_COLUMNS[:7]
    cols = []
    for f in fields:
        f_lower = f.lower().strip()
        if f_lower in COLUMN_GROUPS:
            cols.extend(COLUMN_GROUPS[f_lower])
        else:
            for key, column in FIELD_MAP.items():
                if f_lower == key or f_lower == column.lower():
                    cols.append(column)
                    break
    return list(dict.fromkeys(cols)) if cols else DETAIL_COLUMNS[:7]


def build_profile_query(filters: dict, limit: int = 10) -> tuple[str, list]:
    conditions = ["LOWER(Status) = LOWER('Active')"]
    params: list[Any] = []

    for key, column in FIELD_MAP.items():
        value = filters.get(key)
        if value:
            conditions.append(f"LOWER({column}) = LOWER(?)")
            params.append(str(value))

    city = filters.get("city")
    if city:
        conditions.append(
            "(LOWER(City) LIKE LOWER(?) OR LOWER(Dist) LIKE LOWER(?) OR LOWER(State) LIKE LOWER(?))"
        )
        like_val = f"%{city}%"
        params.extend([like_val, like_val, like_val])

    dist = filters.get("dist")
    if dist and not city:
        conditions.append(
            "(LOWER(City) LIKE LOWER(?) OR LOWER(Dist) LIKE LOWER(?) OR LOWER(State) LIKE LOWER(?))"
        )
        like_val = f"%{dist}%"
        params.extend([like_val, like_val, like_val])

    state = filters.get("state")
    if state and not city and not dist:
        conditions.append(
            "(LOWER(City) LIKE LOWER(?) OR LOWER(Dist) LIKE LOWER(?) OR LOWER(State) LIKE LOWER(?))"
        )
        like_val = f"%{state}%"
        params.extend([like_val, like_val, like_val])

    subcaste = filters.get("subcaste")
    if subcaste:
        conditions.append("LOWER(Caste) LIKE LOWER(?)")
        params.append(f"%{subcaste}%")

    age_min = filters.get("age_min")
    if age_min is not None:
        conditions.append("CAST(Age AS SIGNED) >= ?")
        params.append(int(age_min))

    age_max = filters.get("age_max")
    if age_max is not None:
        conditions.append("CAST(Age AS SIGNED) <= ?")
        params.append(int(age_max))

    education = filters.get("education")
    if education:
        conditions.append("LOWER(Education) LIKE LOWER(?)")
        params.append(f"%{education}%")

    occupation = filters.get("occupation")
    if occupation:
        conditions.append("LOWER(Occupation) LIKE LOWER(?)")
        params.append(f"%{occupation}%")

    sql = SEARCH_SSL + f"FROM register WHERE {' AND '.join(conditions)} ORDER BY Regdate DESC LIMIT ?"
    params.append(limit)

    return sql, params


def build_detail_query(
    matri_id: str | None = None,
    name: str | None = None,
    fields: list[str] | None = None,
    limit: int = 1,
) -> tuple[str, list]:
    cols = _resolve_columns(fields)
    cols_sql = ", ".join(cols)
    conditions = ["LOWER(Status) = LOWER('Active')"]
    params: list[Any] = []

    if matri_id:
        conditions.append("MatriID = ?")
        params.append(matri_id)
    if name:
        conditions.append("LOWER(Name) LIKE LOWER(?)")
        params.append(f"%{name}%")

    sql = f"SELECT {cols_sql} FROM register WHERE {' AND '.join(conditions)} LIMIT ?"
    params.append(limit)
    return sql, params
