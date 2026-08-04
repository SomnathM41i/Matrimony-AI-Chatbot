from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.chat_repository import ChatRepository
from app.services.db_query_service import DatabaseQueryError, accumulate_usage, handle_profile_search, format_no_matches_notice, TOO_MANY_NOTICE, format_profile_results_markdown
from app.services.matri_service import (
    BIODATA_SECTION_ROUTES,
    BIODATA_SECTION_CHIPS,
    MatriLinkError,
    format_profile_biodata,
    format_profile_section,
    format_user_profile_summary,
    link_matri_id_to_user,
)
from app.services.questionnaire_chat import first_name, format_question, parse_answer
from app.services.extraction_service import rule_based_extract
from app.core.logger import logger, StepTimer
from datetime import datetime, timezone
import asyncio
import httpx
import json
import re
import uuid


def user_facing_error(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 429:
        return (
            "क्षमस्व, आत्ता खूप विनंत्यांमुळे assistant व्यस्त आहे. "
            "कृपया थोडा वेळ थांबून पुन्हा प्रयत्न करा."
        )
    if isinstance(error, httpx.TimeoutException):
        return "क्षमस्व, विनंतीवर प्रक्रिया करण्यास बराच वेळ लागला. कृपया पुन्हा प्रयत्न करा."
    if isinstance(error, DatabaseQueryError):
        return (
            "क्षमस्व, सध्या प्रोफाइल डेटाबेसमध्ये प्रवेश करता आला नाही. "
            "थोड्या वेळाने पुन्हा प्रयत्न करा."
        )
    if isinstance(error, ValueError) and str(error) == "Could not convert request into a database query.":
        return (
            "क्षमस्व, मला तुमची विनंती या संदर्भात समजली नाही. "
            "कृपया ती वेगळ्या शब्दांत लिहा — उदा. 'मागील उत्तर मराठीत सांगा' "
            "किंवा 'पुण्यातील 5 मुलींची प्रोफाइल दाखवा'."
        )
    return "क्षमस्व, आत्ता तुमची विनंती प्रक्रिया होऊ शकली नाही. कृपया पुन्हा प्रयत्न करा किंवा वेगळ्या शब्दांत विचारा."


def _word_in(text: str, word: str) -> bool:
    return bool(re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', text))

MATRI_ID_PROMPT = (
    f"मी {settings.ASSISTANT_NAME} आहे — तुमचा वैयक्तिक विवाह सल्लागार. "
    f"{settings.PLATFORM_NAME} वरील तुमचे प्रोफाइल समजून घेण्यासाठी कृपया तुमचा Matri ID शेअर करा "
    "(उदा. ES92669), जेणेकरून मी तुमचा perfect partner शोधून देऊ शकेन! 🙏"
)

WELCOME_MESSAGE = (
    f"👋 नमस्कार!\n\n"
    f"मी {settings.ASSISTANT_NAME} आहे — तुमचा वैयक्तिक विवाह सल्लागार.\n\n"
    f"मी {settings.PLATFORM_NAME} वरील तुमचे प्रोफाइल समजून घेईन, तुमच्या पसंतीनुसार योग्य "
    f"स्थळे शोधून देईन, प्रत्येक प्रोफाइल समजावून सांगेन आणि योग्य निर्णय घेण्यासाठी मार्गदर्शन करेन.\n\n"
    f"सुरुवात करण्यासाठी कृपया तुमचा Matri ID सांगा."
)

WELCOME_SUGGESTIONS = [
    "मला Matri ID जोडायचा आहे",
    "पुण्यातील 5 मुलींची प्रोफाइल दाखवा",
    "माझ्या जोडीदाराच्या पसंती सांगा",
    "success stories दाखवा",
]

# CF-4: welcome-back greeting for a linked user starting a brand-new
# conversation. The chips are picked from WELCOME_BACK_SUGGESTIONS based on the
# last_topic memory of their most recent prior conversation.
WELCOME_BACK_PREFIX = "परत स्वागत, {name}! 🙏\n\n"

WELCOME_BACK_SUGGESTIONS = {
    "profile_search": [
        "मागील सर्च चालू ठेवा",
        "पुढील प्रोफाइल दाखवा",
        "नवीन सर्च सुरू करा",
    ],
    "profile_detail": [
        "आधी पाहिलेले प्रोफाइल पुन्हा पाहा",
        "पुढील प्रोफाइल दाखवा",
        "माझ्या पसंतीनुसार नवीन सर्च",
    ],
    "comparison": [
        "आणखी दोन प्रोफाइलची तुलना करा",
        "पुढील प्रोफाइल दाखवा",
        "माझ्या पसंतीनुसार प्रोफाइल दाखवा",
    ],
    "questionnaire": [
        "माझ्या पसंतीनुसार प्रोफाइल दाखवा",
        "मागील सर्च चालू ठेवा",
        "आधी पाहिलेले प्रोफाइल पुन्हा पाहा",
    ],
}

GENERIC_WELCOME_BACK_SUGGESTIONS = [
    "माझ्या जोडीदाराच्या पसंती सांगा",
    "पुण्यातील 5 मुलींची प्रोफाइल दाखवा",
    "माझ्या पसंतीनुसार प्रोफाइल दाखवा",
]

QUESTIONNAIRE_DONE_SUGGESTIONS = [
    "माझ्या पसंतीनुसार प्रोफाइल दाखवा",
    "मागील सर्च चालू ठेवा",
    "नवीन सर्च सुरू करा",
]

# CF-5: deterministic click routing for suggestion chips — an exact phrase match
# skips LLM extraction entirely and drives the flow straight from conversation
# memory (last filters / saved prefs / candidates). No LLM involved.
SUGGESTION_ROUTES: dict[str, dict] = {
    "मागील सर्च चालू ठेवा": {
        "intent": "profile_search", "limit": 10, "deterministic": True,
    },
    "नवीन सर्च सुरू करा": {
        "intent": "profile_search", "limit": 10, "deterministic": True,
        "reset_filters": True,
    },
    "पुढील प्रोफाइल दाखवा": {
        "intent": "profile_search", "limit": 10, "deterministic": True,
        "next_batch": True,
    },
    "माझ्या पसंतीनुसार नवीन सर्च": {
        "intent": "profile_search", "limit": 10, "deterministic": True,
        "reset_filters": True,
    },
    "माझ्या पसंतीनुसार प्रोफाइल दाखवा": {
        "intent": "profile_search", "limit": 10, "deterministic": True,
    },
    "आणखी दोन प्रोफाइलची तुलना करा": {
        "intent": "comparison", "deterministic": True,
    },
    "आधी पाहिलेले प्रोफाइल पुन्हा पाहा": {
        "intent": "profile_detail", "fields": ["all"], "selected_index": 1,
        "deterministic": True,
    },
}

# CF-6: biodata section chips drill into the currently viewed profile
# (current_selected from memory) without any LLM call.
SUGGESTION_ROUTES.update({
    chip: {
        "intent": "profile_detail", "fields": ["all"],
        "biodata_section": section_key,
        "selected_index": None, "selected_reference": None,
        "deterministic": True,
    }
    for chip, section_key in BIODATA_SECTION_ROUTES.items()
})

MATRI_ID_SUCCESS = (
    "तुमचा matrimony ID \"{id}\" यशस्वीरित्या लिंक झाला! 🙏\n"
    "आता मी तुमच्या partner expectations नुसार तुम्हाला perfect partner शोधून देईन. "
    "तुम्हाला कोणती मुलगी/मुलगा हवी आहे ते सांगा — उदा. \"पुण्यातील मुली दाखवा\"."
)

MATRI_ID_NOT_FOUND = (
    "क्षमस्व, \"{id}\" हा matrimony ID सापडला नाही. "
    "कृपया तुमचा योग्य ID पुन्हा लिहा."
)

MATRI_ID_ERROR = (
    "क्षमस्व, matrimony डेटाबेसशी संपर्क होऊ शकला नाही. "
    "थोड्या वेळाने पुन्हा प्रयत्न करा."
)

MATRI_ID_FLOW_START = (
    "नमस्कार {name}! 🙏 तुमचा matrimony ID \"{id}\" यशस्वीरित्या लिंक झाला आहे. "
    "तुमच्या perfect partner साठी काही प्रश्नांची उत्तरे द्या — "
    "मी तुमच्या उत्तरांनुसार जोडीदार शोधून देईन:\n\n"
)

QUESTIONNAIRE_REASK = (
    "क्षमस्व, मला तुमचे उत्तर समजले नाही. "
    "कृपया पर्यायावर क्लिक करा किंवा थेट मजकूर टाइप करा:\n\n{question}"
)

QUESTIONNAIRE_DONE_PREFIX = (
    "धन्यवाद {name}! 🙏 तुमच्या पसंती जतन झाल्या आहेत. "
    "येथे तुमच्या perfect partner साठी काही प्रोफाइल आहेत:\n\n"
)

QUESTIONNAIRE_DONE_NO_MATCH_PREFIX = "धन्यवाद {name}! 🙏 तुमच्या पसंती जतन झाल्या आहेत.\n\n"


def _questionnaire_options(node: dict) -> list[dict]:
    return [{"id": o["id"], "label": o["label"]} for o in node.get("options", [])]


def _enrich_memory(metadata: dict | None, intent_label: str | None) -> dict:
    """CF-4: annotate assistant metadata with explicit memory fields so a later
    turn (or the welcome-back greeting on the next conversation) can restore the
    user's last topic, viewed profiles, compared pair and last search filters.
    Existing explicit keys are never overwritten."""
    metadata = dict(metadata or {})
    if intent_label and not metadata.get("last_topic"):
        metadata["last_topic"] = intent_label
    if metadata.get("profile_candidates") and not metadata.get("viewed_profiles"):
        metadata["viewed_profiles"] = [
            {"MatriID": p.get("MatriID"), "Name": p.get("Name")}
            for p in metadata["profile_candidates"]
            if p.get("Name")
        ]
    if metadata.get("compared_pair") and not metadata.get("compared_pairs"):
        metadata["compared_pairs"] = [metadata["compared_pair"]]
    if metadata.get("accumulated_filters") and not metadata.get("last_filters"):
        metadata["last_filters"] = metadata["accumulated_filters"]
    return metadata


def build_suggestions(context: dict) -> list[str]:
    """CF-5: deterministic Marathi follow-up chips for a reply, derived from the
    conversation memory/context (matri link, questionnaire completion, last
    topic). Pure code — no LLM. Every chip in the returned list that carries a
    deterministic action is covered by ``SUGGESTION_ROUTES``."""
    if not (context or {}).get("matri_id"):
        return list(WELCOME_SUGGESTIONS)
    if context.get("questionnaire_done"):
        return list(QUESTIONNAIRE_DONE_SUGGESTIONS)
    last_topic = context.get("last_topic")
    if last_topic in WELCOME_BACK_SUGGESTIONS:
        return list(WELCOME_BACK_SUGGESTIONS[last_topic])
    return list(GENERIC_WELCOME_BACK_SUGGESTIONS)


def _done_event(conversation_id: int, message_id: int, usage: dict, metadata: dict | None = None) -> str:
    payload = {
        "type": "done",
        "conversation_id": conversation_id,
        "message_id": message_id,
        "usage": usage,
    }
    q_options = (metadata or {}).get("questionnaire_options")
    if q_options:
        payload["questionnaire"] = {
            "options": q_options,
            "progress": (metadata or {}).get("questionnaire_progress"),
        }
    suggestions = (metadata or {}).get("suggestions")
    if suggestions:
        payload["suggestions"] = suggestions
    return f"data: {json.dumps(payload)}\n\n"


def _questionnaire_start(pe_filters: dict, missing_only: bool = False) -> tuple[str, dict] | None:
    """Build the questionnaire session opener for the given partner-expectation
    filters. Returns (question_text, metadata) or None when there is nothing to
    ask. Partner gender is never asked — it is derived from the member and is
    required to exist before a flow may start. ``missing_only`` (chat onboarding)
    auto-applies known preferences and asks only missing categories."""
    if not (pe_filters or {}).get("gender"):
        return None
    from app.core.questionnaire import build_nodes, current_node
    nodes, entry_seqs, total = build_nodes(pe_filters or {}, missing_only=missing_only)
    node = current_node(nodes, entry_seqs, [])
    if node is None:
        return None
    index = nodes.index(node)
    metadata = {
        "questionnaire_answers": [],
        "questionnaire_pe_filters": pe_filters or {},
        "questionnaire_done": False,
        "questionnaire_options": _questionnaire_options(node),
        "questionnaire_progress": {"current": index + 1, "total": total},
    }
    return format_question(node, index + 1, total), metadata


def _extract_matri_id(message: str) -> str | None:
    """Return a MatriID candidate when the message is a bare ID token or
    contains an explicit id / matri / आयडी hint followed by an ID-like token."""
    text = message.strip().rstrip(".!?,")
    if not text:
        return None
    if re.fullmatch(r"[A-Za-z0-9]{3,15}", text):
        return text.upper()
    tokens = re.findall(r"[A-Za-z0-9\u0900-\u097F]+", text)
    hint_words = {"id", "matri", "matrimony", "matriid", "आयडी", "मॅट्रिमोनी"}
    for i, token in enumerate(tokens):
        if token.lower() in hint_words:
            for candidate in tokens[i + 1:]:
                if not candidate.isascii():
                    continue
                if len(candidate) > 15:
                    return None
                if 3 <= len(candidate) <= 15 and re.search(r"\d", candidate):
                    return candidate.upper()
            return None
    return None


def _is_profile_query(message: str, history: list[dict] | None = None) -> bool:
    msg = message.lower()
    profile_keywords = {
        "profile", "profiles", "member", "members", "bride", "groom",
        "girl", "girls", "boy", "boys", "woman", "women", "man", "men",
        "mulgi", "muli", "मुलगी", "मुली", "महिला",
        "mula", "mule", "मुलगा", "मुले", "पुरुष",
        "वधू", "वर", "प्रोफाइल", "सदस्य",
        "ladki", "ladkiyan", "लड़की", "लड़कियां",
        "unmarried", "divorced", "widow", "marital",
    }
    community_keywords = {
        "maratha", "brahmin", "mali", "kunbi", "dhangar",
        "hindu", "muslim", "buddhist", "jain", "christian", "sikh",
        "मराठा", "ब्राह्मण", "माळी", "हिंदू",
        "jat", "जात", "धर्म", "caste", "religion",
        "kuli", "कुळी",
    }
    has_profile_words = any(_word_in(msg, kw) for kw in profile_keywords)
    has_community_words = any(_word_in(msg, kw) for kw in community_keywords)
    has_search_verb = any(
        _word_in(msg, w) for w in [
            "show", "search", "find", "list", "दाखवा", "शोधा",
            "show me", "need", "want", "looking", "require",
            "हवी", "हवे", "पाहिजे",
        ]
    )
    return has_profile_words or has_community_words or has_search_verb


GREETING_RESPONSES: dict[str, str] = {
    "hi": "नमस्कार! मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार. मी तुम्हाला कशी मदत करू?",
    "hello": "नमस्कार! मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार. मी तुम्हाला कशी मदत करू?",
    "hey": "नमस्कार! मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार. मी तुम्हाला कशी मदत करू?",
    "नमस्कार": "नमस्कार! मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार. मी तुम्हाला कशी मदत करू?",
    "नमस्ते": "नमस्कार! मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार. मी तुम्हाला कशी मदत करू?",
    "हॅलो": "नमस्कार! मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार. मी तुम्हाला कशी मदत करू?",
    "namaste": "नमस्कार! मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार. मी तुम्हाला कशी मदत करू?",
    "good morning": "सुप्रभात! मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार. मी तुम्हाला कशी मदत करू?",
    "good afternoon": "शुभ दुपार! मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार. मी तुम्हाला कशी मदत करू?",
    "good evening": "शुभ संध्याकाळ! मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार. मी तुम्हाला कशी मदत करू?",
}

IDENTITY_RESPONSES: dict[str, str] = {
    "who are you": (
        "मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार. मी Dishavadhuvar Matrimony "
        "प्लॅटफॉर्मवर तुमचे प्रोफाइल समजून घेऊन तुमच्या पसंतीनुसार योग्य स्थळे शोधून देतो. "
        "मी तुम्हाला कशी मदत करू?"
    ),
    "what is your name": (
        "मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार. मी Dishavadhuvar Matrimony "
        "प्लॅटफॉर्मवर काम करतो."
    ),
    "tell me about yourself": (
        "मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार. मी Dishavadhuvar Matrimony "
        "प्लॅटफॉर्मवर तुमचे प्रोफाइल समजून घेऊन तुमच्या पसंतीनुसार योग्य स्थळे शोधून देतो, "
        "प्रत्येक प्रोफाइल समजावून सांगतो आणि योग्य निर्णय घेण्यासाठी मार्गदर्शन करतो."
    ),
    "aap kaun ho": (
        "मैं MyVivahAI हूँ — आपका निजी विवाह सल्लागार. मैं Dishavadhuvar Matrimony प्लेटफॉर्म "
        "पर काम करता हूँ."
    ),
    "तुम्ही कोण आहात": (
        "मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार. मी Dishavadhuvar Matrimony "
        "प्लॅटफॉर्मवर काम करतो."
    ),
    "तुमचे नाव काय आहे": (
        "मी MyVivahAI आहे — तुमचा वैयक्तिक विवाह सल्लागार."
    ),
}


def _is_greeting_only(message: str) -> str | None:
    msg = message.lower().strip().rstrip(".!?,")
    for greeting, response in GREETING_RESPONSES.items():
        if msg == greeting:
            return response
    return None


def _is_identity_question(message: str) -> str | None:
    msg = message.lower().strip().rstrip(".!?,")
    return IDENTITY_RESPONSES.get(msg)


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


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conv_repo = ConversationRepository(db)
        self.msg_repo = ChatRepository(db)

    async def _load_user_preferences(self, user_id: int) -> dict:
        from app.repositories.preference_repository import PreferenceRepository
        prefs = await PreferenceRepository(self.db).list_by_user(user_id)
        return PreferenceRepository.to_filter_dict(prefs)

    @staticmethod
    def _safe_metadata(metadata_json: str | None) -> dict | None:
        if not metadata_json:
            return None
        try:
            return json.loads(metadata_json)
        except (TypeError, ValueError):
            return None

    async def _attach_user(self, user) -> object | None:
        """Return a copy of the authenticated ``user`` tracked by this request's
        session, or None when there is nothing to attach.

        FastAPI tears down ``yield``-based DB dependencies before a
        StreamingResponse generator runs, so the ``user`` object handed to
        ``stream_process_message`` is detached from its original session by the
        time chat logic executes. Mutations like ``user.matri_id = ...`` on that
        detached object would silently never persist. Merging it back into
        ``self.db``'s session makes those mutations tracked and committed."""
        if user is None or not getattr(user, "id", None):
            return user
        return await self.db.merge(user)

    async def _load_history(self, conversation_id: int) -> tuple[list[dict], dict]:
        msgs = await self.msg_repo.list_by_conversation(conversation_id)
        history = []
        selected_profile = None
        accumulated_filters = None
        cached_profile_data = None
        profile_candidates = None
        questionnaire_answers = None
        questionnaire_pe_filters = None
        questionnaire_done = None
        questionnaire_searched = None
        last_topic = None
        viewed_profiles = None
        compared_pairs = None
        last_filters = None
        search_offset = None
        for m in reversed(msgs):
            if not m.metadata_json:
                continue
            try:
                metadata = json.loads(m.metadata_json)
                if selected_profile is None:
                    selected_profile = metadata.get("selected_profile")
                if accumulated_filters is None:
                    accumulated_filters = metadata.get("accumulated_filters")
                if cached_profile_data is None:
                    cached_profile_data = metadata.get("cached_profile_data")
                if profile_candidates is None:
                    profile_candidates = metadata.get("profile_candidates")
                if questionnaire_answers is None:
                    questionnaire_answers = metadata.get("questionnaire_answers")
                if questionnaire_pe_filters is None:
                    questionnaire_pe_filters = metadata.get("questionnaire_pe_filters")
                if questionnaire_done is None:
                    questionnaire_done = metadata.get("questionnaire_done")
                if questionnaire_searched is None:
                    questionnaire_searched = metadata.get("questionnaire_searched")
                if last_topic is None:
                    last_topic = metadata.get("last_topic")
                if viewed_profiles is None:
                    viewed_profiles = metadata.get("viewed_profiles")
                if compared_pairs is None:
                    compared_pairs = metadata.get("compared_pairs")
                if last_filters is None:
                    last_filters = metadata.get("last_filters")
                if search_offset is None:
                    search_offset = metadata.get("search_offset")
            except (TypeError, ValueError):
                continue
            if None not in (
                selected_profile, accumulated_filters, cached_profile_data,
                profile_candidates, questionnaire_answers,
                questionnaire_pe_filters, questionnaire_done,
                questionnaire_searched, last_topic, viewed_profiles,
                compared_pairs, last_filters, search_offset,
            ):
                break

        if selected_profile:
            history.append({
                "role": "system",
                "content": (
                "Persistent conversation state: the most recently resolved profile is "
                f"Name={selected_profile.get('Name', '')}, "
                f"MatriID={selected_profile.get('MatriID', '')}. "
                "Use this to resolve contextual references like 'her', 'she', 'this profile'."
                ),
            })

        for m in msgs[-settings.CHAT_HISTORY_LIMIT:]:
            history.append({"role": m.role, "content": m.content})
        return history, {
            "accumulated_filters": accumulated_filters,
            "selected_profile": selected_profile,
            "cached_profile_data": cached_profile_data,
            "profile_candidates": profile_candidates,
            "questionnaire_answers": questionnaire_answers,
            "questionnaire_pe_filters": questionnaire_pe_filters,
            "questionnaire_done": questionnaire_done,
            "questionnaire_searched": questionnaire_searched,
            "last_topic": last_topic,
            "viewed_profiles": viewed_profiles,
            "compared_pairs": compared_pairs,
            "last_filters": last_filters,
            "search_offset": search_offset,
        }

    async def _persist_matri_reply(
        self,
        user_id: int,
        message: str,
        conversation_id: int | None,
        reply: str,
        metadata_json: str | None = None,
    ) -> tuple[object, object]:
        """Create/update the conversation and store the user message plus the
        MatriID-link assistant reply. Returns (conversation, assistant_message)."""
        if conversation_id:
            conv = await self.conv_repo.get_by_id(conversation_id)
            if not conv or conv.user_id != user_id:
                raise ValueError("Conversation not found")
        else:
            n = settings.CHAT_TITLE_TRUNCATION
            title = message[:n] + ("..." if len(message) > n else "")
            conv = await self.conv_repo.create(user_id=user_id, title=title)
        _ = await self.msg_repo.create(
            conversation_id=conv.id, user_id=user_id,
            role="user", content=message,
        )
        assistant_msg = await self.msg_repo.create(
            conversation_id=conv.id, user_id=user_id,
            role="assistant", content=reply,
            metadata_json=metadata_json,
            prompt_tokens=0, completion_tokens=0, total_tokens=0,
        )
        await self.conv_repo.update(conv, updated_at=datetime.now(timezone.utc))
        await self.db.commit()
        return conv, assistant_msg

    async def _try_auto_link_matri(
        self, user, message: str, conversation_id: int | None
    ) -> dict | None:
        """When the user has no linked MatriID yet and the message looks like an
        ID (or an explicit ID hint), link it and return a dict with the Marathi
        reply and conversation info. Returns None when the message should fall
        through to normal processing."""
        if user is not None and not getattr(user, "matri_id", None):
            matri_id = _extract_matri_id(message)
            if matri_id:
                metadata = None
                try:
                    result = await link_matri_id_to_user(self.db, user, matri_id)
                except MatriLinkError:
                    reply = MATRI_ID_NOT_FOUND.format(id=matri_id)
                except Exception:
                    logger.exception("MatriID auto-link failed")
                    reply = MATRI_ID_ERROR
                else:
                    summary = format_user_profile_summary(
                        (result or {}).get("profile") or {},
                        (result or {}).get("pe_summary_mr") or {},
                    )
                    pe_filters = (result or {}).get("filters")
                    start = _questionnaire_start(pe_filters, missing_only=True) if pe_filters else None
                    if start and conversation_id is None:
                        prior = await self.conv_repo.count_by_user(user.id)
                        if isinstance(prior, int) and prior > 0:
                            start = None
                    if start:
                        question, metadata = start
                        reply = (
                            MATRI_ID_FLOW_START.format(
                                name=first_name(user.matri_name or user.name),
                                id=matri_id,
                            )
                            + question
                        )
                    else:
                        reply = MATRI_ID_SUCCESS.format(id=matri_id, name=user.matri_name or matri_id)
                    if summary:
                        reply = summary + "\n\n" + reply
                conv, assistant_msg = await self._persist_matri_reply(
                    user.id, message, conversation_id, reply,
                    metadata_json=json.dumps(metadata) if metadata else None,
                )
                return {
                    "reply": reply,
                    "conversation_id": conv.id,
                    "message_id": assistant_msg.id,
                    "metadata": metadata,
                }
        return None

    async def _apply_identity_gate(
        self, user, message: str, conversation_id: int | None
    ) -> dict | None:
        """CF-1 identity gate: for a user with no linked MatriID, the first
        message of a brand-new conversation (or every message in hard mode) is
        answered with the WELCOME_MESSAGE plus suggestion chips, persisting a
        ``matri_id_prompted`` flag so the welcome is only asked once. In soft
        mode the guest then proceeds with normal browsing; hard mode blocks all
        service until a MatriID is linked. Returns a reply dict or None to fall
        through to normal processing."""
        if user is None or getattr(user, "matri_id", None):
            return None
        if _extract_matri_id(message):
            return None
        mode = settings.MATRI_ID_GATE_MODE
        if mode != "hard" and conversation_id is not None:
            return None
        return {
            "reply": WELCOME_MESSAGE,
            "metadata": {
                "matri_id_prompted": True,
                "suggestions": WELCOME_SUGGESTIONS,
            },
        }

    async def _last_topic_across_conversations(self, user_id: int) -> str | None:
        """Find the last topic the user was working on by scanning their most
        recent conversations (newest first) for the latest assistant message
        that carries a ``last_topic`` memory field. The just-created current
        conversation yields nothing, so the scan naturally lands on the prior
        conversation."""
        conversations = await self.conv_repo.list_by_user(user_id)
        for conv in conversations:
            messages = await self.msg_repo.list_by_conversation(conv.id)
            for m in reversed(messages):
                metadata = self._safe_metadata(m.metadata_json)
                if metadata and metadata.get("last_topic"):
                    return metadata["last_topic"]
        return None

    async def _welcome_back(
        self, user, user_id: int, conversation_id: int | None
    ) -> dict | None:
        """CF-4: for a linked returning user starting a brand-new conversation,
        return a Marathi welcome-back prefix plus context-aware suggestion chips
        derived from the last topic of their most recent prior conversation.
        Returns None for guests, continuing conversations, or first-ever chats."""
        if user is None or not getattr(user, "matri_id", None):
            return None
        if conversation_id is not None:
            return None
        prior = await self.conv_repo.count_by_user(user_id)
        if not isinstance(prior, int) or prior <= 1:
            return None
        last_topic = await self._last_topic_across_conversations(user_id)
        suggestions = WELCOME_BACK_SUGGESTIONS.get(
            last_topic, GENERIC_WELCOME_BACK_SUGGESTIONS
        )
        return {
            "prefix": WELCOME_BACK_PREFIX.format(
                name=first_name(user.matri_name or user.name)
            ),
            "suggestions": suggestions,
        }

    async def _process_questionnaire(
        self, user, user_id: int, message: str,
        conversation_context: dict, conversation_id: int | None, history: list[dict],
    ) -> dict | None:
        """Drive the guided partner-preference questionnaire from chat messages.

        Returns a dict with "reply"/"metadata"/"usage" when the message was
        consumed by the flow (advancing an active session, re-asking, or
        auto-starting one for a linked user with no meaningful saved
        preferences), else None so the caller falls through to normal chat."""
        if user is None or not getattr(user, "matri_id", None):
            return None
        if conversation_context.get("questionnaire_done"):
            return None

        answers = list(conversation_context.get("questionnaire_answers") or [])
        pe_filters = conversation_context.get("questionnaire_pe_filters")

        if not answers and pe_filters is None:
            # Auto-start (chat onboarding): fresh chat for a linked MatriID on the
            # user's FIRST-ever conversation. Known preferences are auto-applied
            # silently; only missing categories are asked (CF-3).
            if conversation_id is not None:
                return None
            prior = await self.conv_repo.count_by_user(user_id)
            if isinstance(prior, int) and prior > 1:
                return None
            prefs = conversation_context.get("default_filters") or {}
            if not prefs.get("gender"):
                return None
            # A concrete profile request ("पुण्यातील 5 मुलींची प्रोफाइल दाखवा")
            # should be answered directly, not hijacked into the questionnaire.
            rule = rule_based_extract(message)
            if rule and (rule.get("limit") is not None or any(k != "gender" for k in rule["filters"])):
                return None
            start = _questionnaire_start(prefs, missing_only=True)
            if start is None:
                return None
            question, metadata = start
            return {
                "reply": MATRI_ID_FLOW_START.format(
                    name=first_name(user.matri_name or user.name), id=user.matri_id
                ) + question,
                "metadata": metadata,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }

        if pe_filters is None:
            return None

        from app.core.questionnaire import build_nodes, current_node, apply_answers, validate_answer, is_viable_search

        nodes, entry_seqs, total = build_nodes(pe_filters, missing_only=True)
        current = current_node(nodes, entry_seqs, answers)
        if current is None:
            return None

        answer = parse_answer(current, message)
        if answer is None or validate_answer(current, answer):
            index = nodes.index(current)
            return {
                "reply": QUESTIONNAIRE_REASK.format(
                    question=format_question(current, index + 1, total)
                ),
                "metadata": {
                    "questionnaire_answers": answers,
                    "questionnaire_pe_filters": pe_filters,
                    "questionnaire_done": False,
                    "questionnaire_options": _questionnaire_options(current),
                    "questionnaire_progress": {"current": index + 1, "total": total},
                },
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }

        new_answers = answers + [answer]
        next_node = current_node(nodes, entry_seqs, new_answers)
        if next_node is None:
            filters = apply_answers(nodes, new_answers, pe_filters)
            from app.repositories.preference_repository import PreferenceRepository
            await PreferenceRepository(self.db).replace_all(
                user_id, filters, source="questionnaire", matri_id=user.matri_id
            )
            await self.db.flush()
            search = await handle_profile_search(
                "माझ्या पसंतीनुसार योग्य जोडीदार दाखवा",
                filters, 10, history, self.db,
                deterministic=True,
            )
            search_metadata = search.get("metadata") or {}
            metadata = {
                "questionnaire_answers": new_answers,
                "questionnaire_pe_filters": pe_filters,
                "questionnaire_done": True,
                "profile_candidates": search_metadata.get("profile_candidates"),
                "selected_profile": search_metadata.get("selected_profile"),
                "accumulated_filters": search_metadata.get("accumulated_filters"),
            }
            if search.get("matched") == "some":
                reply = QUESTIONNAIRE_DONE_PREFIX.format(
                    name=first_name(user.matri_name or user.name)
                ) + (search.get("content") or "")
            else:
                reply = QUESTIONNAIRE_DONE_NO_MATCH_PREFIX.format(
                    name=first_name(user.matri_name or user.name)
                ) + (search.get("content") or "")
            usage = search.get("usage") or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            return {"reply": reply, "metadata": metadata, "usage": usage}

        index = nodes.index(next_node)
        reply = format_question(next_node, index + 1, total)
        metadata = {
            "questionnaire_answers": new_answers,
            "questionnaire_pe_filters": pe_filters,
            "questionnaire_done": False,
            "questionnaire_options": _questionnaire_options(next_node),
            "questionnaire_progress": {"current": index + 1, "total": total},
        }
        # Search-early (CF-3): once the accumulated filters are "viable" for the
        # configured strategy, show matches above the next question (once per
        # session). Refinement chips come with CF-5.
        if not conversation_context.get("questionnaire_searched"):
            filters_so_far = apply_answers(nodes, new_answers, pe_filters)
            if is_viable_search(filters_so_far, settings.ONBOARDING_SEARCH_STRATEGY):
                early = await handle_profile_search(
                    "माझ्या पसंतीनुसार योग्य जोडीदार दाखवा",
                    filters_so_far, 10, history, self.db,
                    deterministic=True,
                )
                early_metadata = early.get("metadata") or {}
                metadata.update({
                    "questionnaire_searched": True,
                    "profile_candidates": early_metadata.get("profile_candidates"),
                    "selected_profile": early_metadata.get("selected_profile"),
                    "accumulated_filters": early_metadata.get("accumulated_filters"),
                })
                if early.get("matched") == "some" and (early.get("content") or ""):
                    reply = early["content"] + "\n\n" + reply
        return {
            "reply": reply,
            "metadata": metadata,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    async def stream_process_message(
        self, user_id: int, message: str, conversation_id: int | None = None, user=None
    ):
        user = await self._attach_user(user)
        greeting_reply = _is_greeting_only(message) or _is_identity_question(message)
        if greeting_reply and not conversation_id:
            if user is not None and not getattr(user, "matri_id", None):
                greeting_reply = greeting_reply + "\n\n" + MATRI_ID_PROMPT
            n = settings.CHAT_TITLE_TRUNCATION
            title = message[:n] + ("..." if len(message) > n else "")
            conv = await self.conv_repo.create(user_id=user_id, title=title)
            _ = await self.msg_repo.create(
                conversation_id=conv.id, user_id=user_id,
                role="user", content=message,
            )
            assistant_msg = await self.msg_repo.create(
                conversation_id=conv.id, user_id=user_id,
                role="assistant", content=greeting_reply,
            )
            await self.conv_repo.update(conv, updated_at=datetime.now(timezone.utc))
            await self.db.commit()
            yield f"data: {json.dumps({'type': 'token', 'content': greeting_reply})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conv.id, 'message_id': assistant_msg.id, 'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}})}\n\n"
            return

        linked = await self._try_auto_link_matri(user, message, conversation_id)
        if linked:
            yield f"data: {json.dumps({'type': 'token', 'content': linked['reply']})}\n\n"
            yield _done_event(
                linked["conversation_id"],
                linked["message_id"],
                {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                linked.get("metadata"),
            )
            return

        gate = await self._apply_identity_gate(user, message, conversation_id)
        if gate:
            conv, assistant_msg = await self._persist_matri_reply(
                user.id, message, conversation_id, gate["reply"],
                metadata_json=json.dumps(gate["metadata"]),
            )
            yield f"data: {json.dumps({'type': 'token', 'content': gate['reply']})}\n\n"
            yield _done_event(
                conv.id,
                assistant_msg.id,
                {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                gate["metadata"],
            )
            return

        request_id = uuid.uuid4().hex
        timer = StepTimer(request_id=request_id)
        timer.begin("context")
        if conversation_id:
            conv = await self.conv_repo.get_by_id(conversation_id)
            if not conv or conv.user_id != user_id:
                raise ValueError("Conversation not found")
        else:
            n = settings.CHAT_TITLE_TRUNCATION
            title = message[:n] + ("..." if len(message) > n else "")
            conv = await self.conv_repo.create(user_id=user_id, title=title)

        conv_id = conv.id
        history, conversation_context = await self._load_history(conv.id)
        conversation_context["default_filters"] = await self._load_user_preferences(user_id)

        welcome_back = None
        if conversation_id is None:
            welcome_back = await self._welcome_back(user, user_id, conversation_id)

        user_msg = await self.msg_repo.create(
            conversation_id=conv.id,
            user_id=user_id,
            role="user",
            content=message,
        )
        await self.db.commit()

        flow = await self._process_questionnaire(
            user, user_id, message, conversation_context, conversation_id, history,
        )
        if flow:
            reply_text = flow["reply"]
            response_metadata = _enrich_memory(flow.get("metadata"), "questionnaire")
            if not (response_metadata or {}).get("suggestions") and response_metadata.get("questionnaire_done"):
                response_metadata["suggestions"] = build_suggestions({
                    "matri_id": getattr(user, "matri_id", None),
                    "questionnaire_done": True,
                })
            usage = flow.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
            intent = "questionnaire"
            timer.log_summary("questionnaire")
            assistant_msg = await self.msg_repo.create(
                conversation_id=conv.id, user_id=user_id, role="assistant",
                content=reply_text,
                metadata_json=json.dumps(response_metadata) if response_metadata else None,
                prompt_tokens=usage["prompt_tokens"], completion_tokens=usage["completion_tokens"], total_tokens=usage["total_tokens"],
            )
            await self.conv_repo.update(conv, updated_at=datetime.now(timezone.utc))
            await self.db.commit()
            yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
            yield _done_event(conv.id, assistant_msg.id, usage, response_metadata)
            return

        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        events = []
        response_metadata = None
        reply_text = ""
        collected_tokens = []
        intent_label = None

        if welcome_back and welcome_back.get("prefix"):
            yield f"data: {json.dumps({'type': 'token', 'content': welcome_back['prefix']})}\n\n"

        try:
            from app.services.extraction_service import extract_search_params
            from app.services.query_builder import build_profile_query
            from app.services.llm_service import stream_general_response, stream_format_db_result, format_db_notice
            from app.services.db_query_service import execute_param_query

            timer.begin("analyze")
            yield f"data: {json.dumps({'type': 'status', 'step': 'analyze'})}\n\n"

            route = SUGGESTION_ROUTES.get(message.strip())
            if route:
                extracted = {
                    "intent": route["intent"],
                    "intent_label": route.get("intent_label") or route["intent"],
                    "filters": {},
                    "limit": route.get("limit", 10),
                    "deterministic": route.get("deterministic", True),
                    "selected_index": route.get("selected_index"),
                    "selected_reference": route.get("selected_reference"),
                    "fields": route.get("fields"),
                    "biodata_section": route.get("biodata_section"),
                    "next_batch": route.get("next_batch", False),
                }
                if route.get("reset_filters"):
                    conversation_context["accumulated_filters"] = {}
            else:
                extracted = await extract_search_params(message, history=history, db=self.db)
            intent = extracted.get("intent", "general")
            intent_label = extracted.get("intent_label") or intent

            if intent_label == "comparison":
                from app.services.db_query_service import handle_profile_comparison
                ctx = conversation_context or {}
                comparison = await handle_profile_comparison(
                    message,
                    extracted.get("selected_index"),
                    extracted.get("selected_reference"),
                    history, self.db,
                    ctx.get("profile_candidates"),
                    ctx.get("selected_profile"),
                )
                reply_text = comparison.get("content") or ""
                response_metadata = comparison.get("metadata")
                usage = accumulate_usage(usage, comparison.get("usage", {}))
                events.extend(comparison.get("events", []))
                if reply_text:
                    yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
            elif intent in ("profile_search", "profile_detail"):
                ctx = conversation_context or {}
                accumulated_filters = ctx.get("accumulated_filters") or {}
                selected_profile = ctx.get("selected_profile")
                candidates = ctx.get("profile_candidates")

                if intent == "profile_detail":
                    selected_index = extracted.get("selected_index")
                    selected_reference = extracted.get("selected_reference")

                    resolved, clarification = resolve_contextual_profile(
                        selected_index, selected_reference, candidates, selected_profile
                    )
                    if clarification:
                        reply_text = clarification
                        yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                        response_metadata = {
                            "selected_profile": selected_profile,
                            "accumulated_filters": accumulated_filters,
                            "profile_candidates": candidates,
                        }
                    else:
                        selected_profile = resolved
                        matri_id = selected_profile.get("MatriID") if selected_profile else None
                        name = selected_profile.get("Name") if selected_profile else None
                        biodata_section = extracted.get("biodata_section")
                        if not matri_id and not name:
                            reply_text = "तुम्हाला कोणत्या प्रोफाइलची माहिती हवी आहे? कृपया आधी एक प्रोफाइल निवडा."
                            yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                            response_metadata = {"selected_profile": None, "accumulated_filters": {}, "profile_candidates": candidates}
                        if not reply_text:
                            need_full = extracted.get("fields") in (None, ["all"]) or bool(biodata_section)
                            detail_fields = ["all"] if need_full else extracted.get("fields")
                            cached = ctx.get("cached_profile_data")
                            if cached and str(cached.get("MatriID")) == str(matri_id):
                                sql_result = {"sql": "cached", "rows": [cached], "row_count": 1}
                                from app.services.db_query_service import add_photo_url
                                for row in sql_result["rows"]:
                                    add_photo_url(row)
                            else:
                                from app.services.query_builder import build_detail_query
                                timer.begin("search")
                                yield f"data: {json.dumps({'type': 'status', 'step': 'search'})}\n\n"
                                sql, params = build_detail_query(matri_id=matri_id, name=name, fields=detail_fields, limit=extracted.get("limit", 1))
                                sql_result = await execute_param_query(sql, params)
                                if sql_result.get("rows"):
                                    from app.services.db_query_service import add_photo_url
                                    for row in sql_result["rows"]:
                                        add_photo_url(row)
                            if not sql_result.get("rows"):
                                reply_text = "प्रोफाइल सापडली नाही."
                                yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                            else:
                                row = sql_result["rows"][0]
                                if biodata_section:
                                    block = format_profile_section(row, biodata_section)
                                    reply_text = block if block else "या प्रोफाइलसाठी ही माहिती उपलब्ध नाही."
                                    yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                                elif extracted.get("fields") in (None, ["all"]):
                                    reply_text = format_profile_biodata(row)
                                    yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                                else:
                                    from app.services.db_query_service import message_asks_about_unavailable_attribute
                                    if message_asks_about_unavailable_attribute(message):
                                        notice = await format_db_notice(message, "ही माहिती डेटाबेसमध्ये उपलब्ध नाही.", history=history, db=self.db)
                                        reply_text = notice.get("content", "ही माहिती डेटाबेसमध्ये उपलब्ध नाही.")
                                        yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                                    else:
                                        timer.begin("format")
                                        yield f"data: {json.dumps({'type': 'status', 'step': 'format'})}\n\n"
                                        async for token, final in stream_format_db_result(message, sql_result, history=history, db=self.db):
                                            if token:
                                                collected_tokens.append(token)
                                                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                                            if final:
                                                usage = accumulate_usage(usage, final.get("usage", {}))
                                                events.extend(final.get("events", []))
                                                reply_text = final.get("content", "".join(collected_tokens))
                                profile_rows = [{"MatriID": r.get("MatriID"), "Name": r.get("Name")} for r in sql_result["rows"] if r.get("Name")]
                                response_metadata = {
                                    "selected_profile": selected_profile if selected_profile else (profile_rows[0] if profile_rows else None),
                                    "accumulated_filters": {},
                                    "cached_profile_data": sql_result["rows"][0] if sql_result.get("rows") else None,
                                    "profile_candidates": candidates if candidates else (profile_rows if profile_rows else None),
                                }
                                if extracted.get("fields") in (None, ["all"]) or biodata_section:
                                    response_metadata["suggestions"] = BIODATA_SECTION_CHIPS
                else:
                    new_filters = extracted.get("filters", {})
                    from app.services.db_query_service import merge_filters
                    default_filters = ctx.get("default_filters") or {}
                    filters = merge_filters(merge_filters(default_filters, accumulated_filters), new_filters)
                    limit = extracted.get("limit", 10)
                    deterministic = bool(extracted.get("deterministic"))
                    offset = 0
                    if deterministic and extracted.get("next_batch"):
                        offset = int(ctx.get("search_offset") or 0)
                    timer.begin("search")
                    yield f"data: {json.dumps({'type': 'status', 'step': 'search'})}\n\n"
                    sql, params = build_profile_query(filters, limit=limit, offset=offset)
                    sql_result = await execute_param_query(sql, params)
                    profile_rows = [{"MatriID": r.get("MatriID"), "Name": r.get("Name")} for r in sql_result["rows"] if r.get("Name")]
                    response_metadata = {"profile_candidates": profile_rows, "selected_profile": profile_rows[0] if profile_rows else None, "accumulated_filters": filters, "search_offset": offset + len(profile_rows)}

                    if deterministic:
                        if sql_result["row_count"] == 0:
                            reply_text = format_no_matches_notice(filters)
                        elif sql_result["row_count"] > settings.MAX_ROWS_BEFORE_NARROW:
                            reply_text = TOO_MANY_NOTICE.format(count=sql_result["row_count"])
                        else:
                            reply_text = format_profile_results_markdown(filters, sql_result)
                        yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                    elif sql_result["row_count"] == 0 and settings.VECTOR_FALLBACK_ENABLED:
                        from app.services.embedding_service import embed_text, build_profile_document, unload_embedding_model
                        from app.services.vector_service import search_with_filters
                        try:
                            timer.begin("ai_search")
                            yield f"data: {json.dumps({'type': 'status', 'step': 'ai_search'})}\n\n"
                            query_text = build_profile_document(filters)
                            query_vector = await embed_text(f"query: {message}. {query_text}", model_name=settings.EMBEDDING_MODEL)
                            # search_with_filters blocks on network I/O, so keep it off the event loop.
                            vector_rows = await asyncio.to_thread(search_with_filters, query_vector, filters, limit, settings.QDRANT_HOST, settings.QDRANT_PORT)
                            if vector_rows:
                                for row in vector_rows:
                                    from app.services.db_query_service import add_photo_url
                                    add_photo_url(row)
                                vector_result = {"sql": "vector_search", "rows": vector_rows, "row_count": len(vector_rows)}
                                profile_rows = [{"MatriID": r.get("MatriID"), "Name": r.get("Name")} for r in vector_rows if r.get("Name")]
                                response_metadata = {"profile_candidates": profile_rows, "selected_profile": profile_rows[0] if profile_rows else None, "accumulated_filters": filters, "search_offset": 0}
                                timer.begin("format")
                                yield f"data: {json.dumps({'type': 'status', 'step': 'format'})}\n\n"
                                async for token, final in stream_format_db_result(message, vector_result, history=history, db=self.db):
                                    if token:
                                        collected_tokens.append(token)
                                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                                    if final:
                                        usage = accumulate_usage(usage, final.get("usage", {}))
                                        events.extend(final.get("events", []))
                                        reply_text = final.get("content", "".join(collected_tokens))
                            else:
                                from app.services.db_query_service import format_notice_safe
                                reply_text = await format_notice_safe(message, "कोणतेही योग्य प्रोफाइल सापडले नाही. वेगळे शहर, जात किंवा वयोगट वापरून पाहण्याचा सल्ला द्या.", history, self.db, "तुमच्या निवडीनुसार कोणतेही योग्य प्रोफाइल सापडले नाही.")
                                yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                        except Exception:
                            logger.exception("Vector search fallback failed")
                            from app.services.db_query_service import format_notice_safe
                            msg = await format_notice_safe(message, "कोणतेही योग्य प्रोफाइल सापडले नाही. वेगळे शहर, जात किंवा वयोगट वापरून पाहण्याचा सल्ला द्या.", history, self.db, "तुमच्या निवडीनुसार कोणतेही योग्य प्रोफाइल सापडले नाही.")
                            reply_text = msg
                            yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                        finally:
                            unload_embedding_model()
                    elif sql_result["row_count"] > settings.MAX_ROWS_BEFORE_NARROW:
                        from app.services.db_query_service import format_notice_safe
                        msg = await format_notice_safe(message, f"सर्चमध्ये {sql_result['row_count']} परिणाम सापडले, खूप जास्त म्हणून सर्व दाखवणे शक्य नाही. अधिक criteria जोडण्याचा सल्ला द्या.", history, self.db, f"सर्चमध्ये {sql_result['row_count']} परिणाम सापडले, एकाच वेळी सर्व दाखवणे शक्य नाही. कृपया अधिक अचूक criteria निवडा.")
                        reply_text = msg
                        yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                    else:
                        timer.begin("format")
                        yield f"data: {json.dumps({'type': 'status', 'step': 'format'})}\n\n"
                        async for token, final in stream_format_db_result(message, sql_result, history=history, db=self.db):
                            if token:
                                collected_tokens.append(token)
                                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                            if final:
                                usage = accumulate_usage(usage, final.get("usage", {}))
                                events.extend(final.get("events", []))
                                reply_text = final.get("content", "".join(collected_tokens))
            else:
                if _is_profile_query(message, history):
                    timer.begin("think")
                    yield f"data: {json.dumps({'type': 'status', 'step': 'think'})}\n\n"
                    try:
                        notice = await format_db_notice(message, "कोणतेही योग्य प्रोफाइल सापडले नाही. वेगळे शहर, जात किंवा वयोगट वापरून पाहण्याचा सल्ला द्या.", history=history, db=self.db)
                        reply_text = notice.get("content", "तुमच्या निवडीनुसार कोणतेही योग्य प्रोफाइल सापडले नाही.")
                    except Exception:
                        reply_text = "तुमच्या निवडीनुसार कोणतेही योग्य प्रोफाइल सापडले नाही."
                    yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                else:
                    timer.begin("think")
                    yield f"data: {json.dumps({'type': 'status', 'step': 'think'})}\n\n"
                    async for token, final in stream_general_response(message, history=history, db=self.db):
                        if token:
                            collected_tokens.append(token)
                            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                        if final:
                            usage = accumulate_usage(usage, final.get("usage", {}))
                            events.extend(final.get("events", []))
                            reply_text = final.get("content", "".join(collected_tokens))

            if welcome_back and welcome_back.get("suggestions"):
                response_metadata = dict(response_metadata or {})
                response_metadata.setdefault("suggestions", welcome_back["suggestions"])
            if not (response_metadata or {}).get("suggestions"):
                response_metadata = dict(response_metadata or {})
                response_metadata["suggestions"] = build_suggestions({
                    "matri_id": getattr(user, "matri_id", None),
                    "last_topic": intent_label,
                    "questionnaire_done": conversation_context.get("questionnaire_done"),
                })
            response_metadata = _enrich_memory(response_metadata, intent_label)

            if not reply_text:
                reply_text = "".join(collected_tokens) if collected_tokens else ""

            assistant_msg = await self.msg_repo.create(
                conversation_id=conv.id, user_id=user_id, role="assistant",
                content=reply_text,
                metadata_json=json.dumps(response_metadata) if response_metadata else None,
                prompt_tokens=usage["prompt_tokens"], completion_tokens=usage["completion_tokens"], total_tokens=usage["total_tokens"],
            )
            await self.conv_repo.update(conv, updated_at=datetime.now(timezone.utc))
            await self.db.commit()
            timer.log_summary(intent)
            yield _done_event(conv_id, assistant_msg.id, usage, response_metadata)

        except Exception as e:
            logger.exception("Chat streaming error")
            # Timings are most useful when a request fails, so emit them here too.
            timer.log_summary("error")
            try:
                await self.db.rollback()
            except Exception:
                pass
            reply_text = user_facing_error(e)
            yield f"data: {json.dumps({'type': 'error', 'content': reply_text, 'conversation_id': conv_id})}\n\n"
    async def process_message(
        self, user_id: int, message: str, conversation_id: int | None = None, user=None
    ) -> dict:
        """Non-streaming entry point. Delegates to the single streaming pipeline
        and reassembles the final reply, mirroring the events it emits."""
        reply_parts: list[str] = []
        done_event = None
        error_event = None
        async for chunk in self.stream_process_message(user_id, message, conversation_id, user):
            if not chunk.startswith("data: "):
                continue
            try:
                event = json.loads(chunk[len("data: "):])
            except (ValueError, TypeError):
                continue
            event_type = event.get("type")
            if event_type == "token":
                reply_parts.append(event.get("content", ""))
            elif event_type == "done":
                done_event = event
            elif event_type == "error":
                error_event = event

        request_id = uuid.uuid4().hex
        zero_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        if done_event:
            return {
                "reply": "".join(reply_parts),
                "conversation_id": done_event.get("conversation_id"),
                "message_id": done_event.get("message_id"),
                "usage": done_event.get("usage", zero_usage),
                "request_id": request_id,
            }

        if error_event:
            reply_text = error_event.get("content", "")
            conv_id = error_event.get("conversation_id")
            assistant_msg = await self.msg_repo.create(
                conversation_id=conv_id, user_id=user_id, role="assistant",
                content=reply_text,
                prompt_tokens=0, completion_tokens=0, total_tokens=0,
            )
            if conv_id:
                conv = await self.conv_repo.get_by_id(conv_id)
                if conv and conv.user_id == user_id:
                    await self.conv_repo.update(conv, updated_at=datetime.now(timezone.utc))
            return {
                "reply": reply_text,
                "conversation_id": conv_id,
                "message_id": assistant_msg.id,
                "usage": zero_usage,
                "request_id": request_id,
            }

        return {
            "reply": "".join(reply_parts),
            "conversation_id": conversation_id,
            "message_id": None,
            "usage": zero_usage,
            "request_id": request_id,
        }
    async def get_conversation(self, user_id: int, conversation_id: int) -> dict:
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv or conv.user_id != user_id:
            raise ValueError("Conversation not found")
        messages = await self.msg_repo.list_by_conversation(conversation_id)
        return {
            "id": conv.id,
            "title": conv.title,
            "status": conv.status,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                    "metadata": self._safe_metadata(m.metadata_json),
                }
                for m in messages
            ],
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
        }

    async def list_conversations(self, user_id: int, page: int = 1, page_size: int = 20) -> dict:
        offset = (page - 1) * page_size
        items = await self.conv_repo.list_by_user_with_counts(user_id, limit=page_size, offset=offset)
        total = await self.conv_repo.count_by_user(user_id)
        for item in items:
            item["created_at"] = item["created_at"].isoformat() if item["created_at"] else None
            item["updated_at"] = item["updated_at"].isoformat() if item["updated_at"] else None
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    async def delete_conversation(self, user_id: int, conversation_id: int) -> None:
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv or conv.user_id != user_id:
            raise ValueError("Conversation not found")
        await self.conv_repo.delete(conv)

    async def update_conversation(
        self, user_id: int, conversation_id: int, title: str | None = None
    ) -> dict:
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv or conv.user_id != user_id:
            raise ValueError("Conversation not found")
        updates = {}
        if title is not None:
            updates["title"] = title
        updates["updated_at"] = datetime.now(timezone.utc)
        conv = await self.conv_repo.update(conv, **updates)
        return {
            "id": conv.id,
            "title": conv.title,
            "status": conv.status,
            "updated_at": conv.updated_at.isoformat(),
        }
