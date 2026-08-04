"""Rule-based decision-tree partner-preference questionnaire.

Zero LLM calls: every question, option and branch is defined in code below.
Answers map directly to profile-search filter keys (see DEFAULT_FILTERS in
extraction_service / FIELD_MAP in query_builder).
"""

from typing import Optional

BUILD_ORDER = [
    "gender",
    "age_range",
    "marital_status",
    "religion",
    "caste",
    "subcaste",
    "education",
    "occupation",
    "city",
    "manglik",
    "complexion",
]

CATEGORY_LABELS = {
    "gender": "लिंग",
    "age_range": "वयोगट",
    "marital_status": "वैवाहिक स्थिती",
    "religion": "धर्म",
    "caste": "जात",
    "subcaste": "उपजात",
    "education": "शिक्षण",
    "occupation": "व्यवसाय",
    "city": "स्थान",
    "manglik": "मांगलिक",
    "complexion": "रंग/वर्ण",
}

DONE = "__done__"

CUSTOM = "custom"
ANY = "any"
KEEP = "keep"
CHANGE = "change"
SKIP = "skip"


class QuestionnaireError(ValueError):
    pass


def _opt(option_id: str, label: str, filters: dict, jump: str | None = None) -> dict:
    option = {"id": option_id, "label": label, "filters": filters}
    if jump:
        option["jump"] = jump
    return option


def _next_key(key: str) -> str:
    idx = BUILD_ORDER.index(key)
    return BUILD_ORDER[idx + 1] if idx + 1 < len(BUILD_ORDER) else DONE


def _confirm_node(category: str, value_text: str, pe_filters: dict, clear_keys: list[str]) -> dict:
    next_key = _next_key(category)
    return {
        "id": f"{category}_confirm",
        "category": category,
        "category_label": CATEGORY_LABELS[category],
        "question": f"तुमची जतन केलेली पसंती ही {value_text} आहे. ती कायम ठेवायची?",
        "type": "confirm",
        "options": [
            _opt(KEEP, "कायम ठेवा", {}, jump=next_key),
            _opt(CHANGE, "बदला", {}, jump=f"{category}_fresh"),
            _opt(SKIP, "वगळा", {k: None for k in clear_keys}, jump=next_key),
        ],
        "known_value": value_text,
    }


def _text_node(category: str, question: str, text_key: str, placeholder: str, options: list[dict]) -> dict:
    return {
        "id": f"{category}_fresh",
        "category": category,
        "category_label": CATEGORY_LABELS[category],
        "question": question,
        "type": "text",
        "text_key": text_key,
        "placeholder": placeholder,
        "options": options,
    }


def _single_node(category: str, question: str, options: list[dict]) -> dict:
    return {
        "id": f"{category}_fresh",
        "category": category,
        "category_label": CATEGORY_LABELS[category],
        "question": question,
        "type": "single",
        "options": options,
    }


def _fresh_node(category: str, pe_filters: dict) -> dict:
    if category == "gender":
        return _single_node(
            "gender",
            "तुम्हाला कोणत्या लिंगाची साथी हवी आहे?",
            [
                _opt("male", "पुरुष", {"gender": "Male"}, jump=_next_key("gender")),
                _opt("female", "महिला", {"gender": "Female"}, jump=_next_key("gender")),
            ],
        )
    if category == "age_range":
        return _single_node(
            "age_range",
            "तुमच्या जोडीदारासाठी कोणता वयोगट पसंत आहे?",
            [
                _opt("18_25", "18 - 25 वर्षे", {"age_min": "18", "age_max": "25"}, jump=_next_key("age_range")),
                _opt("26_30", "26 - 30 वर्षे", {"age_min": "26", "age_max": "30"}, jump=_next_key("age_range")),
                _opt("31_35", "31 - 35 वर्षे", {"age_min": "31", "age_max": "35"}, jump=_next_key("age_range")),
                _opt("36_40", "36 - 40 वर्षे", {"age_min": "36", "age_max": "40"}, jump=_next_key("age_range")),
                _opt("41_50", "41 - 50 वर्षे", {"age_min": "41", "age_max": "50"}, jump=_next_key("age_range")),
                _opt(ANY, "कोणताही वयोगट", {"age_min": None, "age_max": None}, jump=_next_key("age_range")),
            ],
        )
    if category == "marital_status":
        return _single_node(
            "marital_status",
            "तुमच्या जोडीदाराची वैवाहिक स्थिती कशी हवी?",
            [
                _opt("unmarried", "कधीही लग्न न केलेले", {"marital_status": "Unmarried"}, jump=_next_key("marital_status")),
                _opt("divorced", "घटस्फोटित", {"marital_status": "Divorced"}, jump=_next_key("marital_status")),
                _opt("widowed", "विधवा", {"marital_status": "Widowed"}, jump=_next_key("marital_status")),
                _opt("widower", "विधुर", {"marital_status": "Widower"}, jump=_next_key("marital_status")),
                _opt(ANY, "कोणतीही वैवाहिक स्थिती", {"marital_status": None}, jump=_next_key("marital_status")),
            ],
        )
    if category == "religion":
        return _single_node(
            "religion",
            "तुम्हाला धर्माची पसंती आहे का?",
            [
                _opt("hindu", "हिंदू", {"religion": "Hindu"}, jump=_next_key("religion")),
                _opt("muslim", "मुस्लिम", {"religion": "Muslim"}, jump=_next_key("religion")),
                _opt("christian", "ख्रिश्चन", {"religion": "Christian"}, jump=_next_key("religion")),
                _opt("sikh", "शीख", {"religion": "Sikh"}, jump=_next_key("religion")),
                _opt("jain", "जैन", {"religion": "Jain"}, jump=_next_key("religion")),
                _opt("buddhist", "बौद्ध", {"religion": "Buddhist"}, jump=_next_key("religion")),
                # "Any" religion makes caste/subcaste irrelevant: jump straight to education.
                _opt(ANY, "पसंती नाही", {"religion": None}, jump="education"),
            ],
        )
    if category == "caste":
        return _text_node(
            "caste",
            "तुम्हाला विशिष्ट जातीची पसंती आहे का?",
            "caste",
            "जात लिहा, उदा. मराठा",
            [_opt(ANY, "कोणतीही जात", {"caste": None}, jump="occupation")],
        )
    if category == "subcaste":
        return _text_node(
            "subcaste",
            "तुम्हाला उपजात (उदा. 96 कुळी) पसंती आहे का?",
            "subcaste",
            "उपजात लिहा, उदा. 96 कुळी",
            [_opt(ANY, "उपजात पसंती नाही", {"subcaste": None}, jump=_next_key("subcaste"))],
        )
    if category == "education":
        return _text_node(
            "education",
            "तुम्हाला जोडीदाराकडे किमान कोणते शिक्षण हवे आहे?",
            "education",
            "शिक्षण लिहा, उदा. B.E. / B.Tech",
            [
                _opt("tenth_twelfth", "दहावी / बारावी", {"education": "10th"}, jump=_next_key("education")),
                _opt("diploma", "डिप्लोमा", {"education": "Diploma"}, jump=_next_key("education")),
                _opt("graduate", "पदवीधर", {"education": "Graduate"}, jump=_next_key("education")),
                _opt("postgrad", "पदव्युत्तर", {"education": "Post Graduate"}, jump=_next_key("education")),
                _opt(ANY, "कोणतेही शिक्षण", {"education": None}, jump=_next_key("education")),
            ],
        )
    if category == "occupation":
        return _text_node(
            "occupation",
            "तुम्हाला व्यवसायाची पसंती आहे का?",
            "occupation",
            "व्यवसाय लिहा, उदा. Software Engineer",
            [_opt(ANY, "कोणताही व्यवसाय", {"occupation": None}, jump=_next_key("occupation"))],
        )
    if category == "city":
        return _text_node(
            "city",
            "तुम्हाला शहर/स्थानाची पसंती आहे का?",
            "city",
            "शहर लिहा, उदा. पुणे",
            [_opt(ANY, "कोणतेही स्थान", {"city": None, "state": None}, jump=_next_key("city"))],
        )
    if category == "manglik":
        return _single_node(
            "manglik",
            "तुमची मांगलिक पसंती काय आहे?",
            [
                _opt("yes", "मांगलिक", {"manglik": "Yes"}, jump=_next_key("manglik")),
                _opt("no", "अमांगलिक", {"manglik": "No"}, jump=_next_key("manglik")),
                _opt(ANY, "पसंती नाही", {"manglik": None}, jump=_next_key("manglik")),
            ],
        )
    if category == "complexion":
        return _single_node(
            "complexion",
            "तुम्हाला रंग/वर्णाची पसंती आहे का?",
            [
                _opt("very_fair", "अतिशय गोरा", {"complexion": "Very Fair"}, jump=_next_key("complexion")),
                _opt("fair", "गोरा", {"complexion": "Fair"}, jump=_next_key("complexion")),
                _opt("wheatish", "गहूवर्णी", {"complexion": "Wheatish"}, jump=_next_key("complexion")),
                _opt("wheatish_medium", "गहूवर्णी मध्यम", {"complexion": "Wheatish Medium"}, jump=_next_key("complexion")),
                _opt("dark", "सावळा", {"complexion": "Dark"}, jump=_next_key("complexion")),
                _opt(ANY, "पसंती नाही", {"complexion": None}, jump=_next_key("complexion")),
            ],
        )
    raise QuestionnaireError(f"Unknown category: {category}")


def _known_value_text(category: str, pe_filters: dict) -> Optional[tuple[str, list[str]]]:
    if category == "gender":
        value = pe_filters.get("gender")
        return (f"{value} जोडीदार", ["gender"]) if value else None
    if category == "age_range":
        low = pe_filters.get("age_min")
        high = pe_filters.get("age_max")
        if low or high:
            text = f"{low or '?'} - {high or '?'} वर्षे वयोगट"
            return (text, ["age_min", "age_max"])
        return None
    if category == "city":
        value = pe_filters.get("city")
        return (f"{value} मधील जोडीदार", ["city", "state"]) if value else None
    key = {
        "marital_status": "marital_status",
        "religion": "religion",
        "caste": "caste",
        "subcaste": "subcaste",
        "education": "education",
        "occupation": "occupation",
        "manglik": "manglik",
        "complexion": "complexion",
    }.get(category)
    if not key:
        return None
    value = pe_filters.get(key)
    return (f"{value}", [key]) if value else None


def build_nodes(pe_filters: dict, missing_only: bool = False) -> tuple[list[dict], dict, int]:
    """Build the decision tree for the partner-preference questionnaire.

    With ``missing_only=False`` (profile-page path) every known preference gets a
    keep/change/skip confirm node. With ``missing_only=True`` (chat onboarding
    path, CF-3) known preferences are auto-applied silently and only missing
    categories are asked — the "कायम ठेवा?" confirm steps never appear in chat.
    """
    pe_filters = pe_filters or {}
    nodes: list[dict] = []
    entry_seqs: dict[str, int] = {}
    for category in BUILD_ORDER:
        if category == "gender" and pe_filters.get("gender"):
            # Partner gender is already known (derived from the member's own
            # gender in the matrimony DB), so auto-apply it and never ask.
            continue
        known = _known_value_text(category, pe_filters)
        if known and missing_only:
            # Auto-apply the known value silently; ask only missing categories.
            continue
        if known:
            value_text, clear_keys = known
            confirm = _confirm_node(category, value_text, pe_filters, clear_keys)
            entry_seqs[category] = len(nodes)
            nodes.append(confirm)
            entry_seqs[f"{category}_fresh"] = len(nodes)
            nodes.append(_fresh_node(category, pe_filters))
        else:
            entry_seqs[category] = len(nodes)
            nodes.append(_fresh_node(category, pe_filters))
    return nodes, entry_seqs, len(nodes)


def is_viable_search(filters: dict, strategy: str = "gender_plus_core") -> bool:
    """Decide whether the accumulated partner filters are enough to start
    searching early (CF-3 search-early). Strategies:
    - ``gender_only``: partner gender alone is enough.
    - ``full_only``: never search early (current pre-CF-3 behaviour).
    - ``gender_plus_core`` (default): partner gender plus at least one of
      age/city/education/occupation."""
    if strategy == "gender_only":
        return bool(filters.get("gender"))
    if strategy == "full_only":
        return False
    if not filters.get("gender"):
        return False
    core = ["age_min", "city", "education", "occupation"]
    return any(filters.get(key) for key in core)


def _find_node(nodes: list[dict], node_id: str) -> dict | None:
    for node in nodes:
        if node["id"] == node_id:
            return node
    return None


def _find_option(node: dict, option_id: str) -> dict | None:
    for option in node.get("options", []):
        if option["id"] == option_id:
            return option
    return None


def current_node(nodes: list[dict], entry_seqs: dict, answers: list[dict]) -> dict | None:
    if not nodes:
        return None
    answered = {a.get("node_id"): a for a in answers or []}
    seq = None
    for category in BUILD_ORDER:
        if category in entry_seqs:
            seq = entry_seqs[category]
            break
    while seq is not None and seq < len(nodes):
        node = nodes[seq]
        if node["id"] not in answered:
            return node
        answer = answered[node["id"]]
        option = _find_option(node, answer.get("option_id"))
        if option is None:
            if node.get("type") == "text" and answer.get("option_id") == CUSTOM:
                seq = seq + 1
                continue
            return node
        jump = option.get("jump")
        if jump == DONE:
            return None
        seq = entry_seqs.get(jump) if jump else seq + 1
    return None


def apply_answers(nodes: list[dict], answers: list[dict], base: dict | None = None) -> dict:
    result = dict(base or {})
    for answer in answers or []:
        node = _find_node(nodes, answer.get("node_id"))
        if node is None:
            continue
        option = _find_option(node, answer.get("option_id"))
        if node.get("type") == "text" and answer.get("option_id") == CUSTOM:
            value = (answer.get("value") or "").strip()
            text_key = node.get("text_key")
            if text_key:
                if value:
                    result[text_key] = value
                else:
                    result.pop(text_key, None)
            continue
        if option is None:
            continue
        for key, value in option.get("filters", {}).items():
            if value is None or value == "":
                result.pop(key, None)
            else:
                result[key] = str(value)
    return result


def validate_answer(node: dict, answer: dict) -> str | None:
    option_id = answer.get("option_id")
    option = _find_option(node, option_id)
    if option is not None:
        return None
    if node.get("type") == "text" and option_id == CUSTOM:
        if node.get("text_key") and (answer.get("value") or "").strip():
            return None
        return "कृपया या उत्तरासाठी मूल्य लिहा."
    return "या प्रश्नासाठी चुकीचा पर्याय निवडला."


def serialize_node(node: dict, index: int, total: int, filters_so_far: dict) -> dict:
    return {
        "node_id": node["id"],
        "category": node["category"],
        "category_label": node.get("category_label"),
        "question": node["question"],
        "type": node["type"],
        "text_key": node.get("text_key"),
        "placeholder": node.get("placeholder"),
        "known_value": node.get("known_value"),
        "options": [
            {"id": o["id"], "label": o["label"], "jump": o.get("jump")}
            for o in node.get("options", [])
        ],
        "progress": {"current": index + 1, "total": total},
        "filters_so_far": filters_so_far,
    }
