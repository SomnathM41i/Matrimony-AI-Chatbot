"""Offline AI-evaluation harness for the MyVivahAI chat pipeline (P10).

This is NOT collected by pytest (no ``test_``-prefixed functions) and does not
need a live MySQL / Qdrant / Groq connection — the DB access and LLM boundaries
are mocked exactly as in the unit suites, so the harness scores real service
behaviour deterministically and offline.

Run:
    cd backend
    .\\venv\\Scripts\\python -m tests.eval_harness        (or: python tests/eval_harness.py)

Rubric dimensions scored per scenario:
    marathi_first   - the prose reply contains Devanagari (data tokens may be English)
    no_hallucination- when the DB returns nothing, no profile names/photo cards are
                      fabricated and the reply offers next steps
    routing         - the expected intent/route path was taken (LLM boundaries that
                      must NOT run are patched to raise)
    deterministic   - CF-5/CF-6 zero-LLM renderers emit sectioned biodata / photo cards
    suggestions     - done events carry routed suggestion chips
    identity        - never "chatbot" / "Dishavadhuvar AI"

Exit code 0 iff every scenario passes.
"""
import asyncio
import json
import re
import sys
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_service import (
    GENERIC_WELCOME_BACK_SUGGESTIONS,
    WELCOME_BACK_SUGGESTIONS,
    WELCOME_MESSAGE,
    WELCOME_SUGGESTIONS,
    ChatService,
)
from app.services.matri_service import BIODATA_SECTION_CHIPS

DEVANAGARI = re.compile(r"[\u0900-\u097F]")


class FakeUser:
    def __init__(self, matri_id="ES92669", matri_name="Ravi Kumar", name="Ravi"):
        self.id = 1
        self.matri_id = matri_id
        self.matri_name = matri_name
        self.name = name


def _service(count_by_user=1, prior_convs=None):
    service = ChatService(db=AsyncMock())
    service.conv_repo = MagicMock()
    service.conv_repo.create = AsyncMock(return_value=MagicMock(id=7))
    service.conv_repo.update = AsyncMock(return_value=None)
    service.conv_repo.count_by_user = AsyncMock(return_value=count_by_user)
    service.conv_repo.list_by_user = AsyncMock(return_value=prior_convs or [])
    service.msg_repo = MagicMock()
    service.msg_repo.create = AsyncMock(side_effect=[MagicMock(id=1), MagicMock(id=2)])
    service.msg_repo.list_by_conversation = AsyncMock(return_value=[])
    service.db = AsyncMock()
    service.db.commit = AsyncMock(return_value=None)
    service.db.flush = AsyncMock(return_value=None)
    return service


def _reply(events) -> str:
    return "".join(
        (json.loads(e[len("data: "):]).get("content") or "")
        for e in events if e.startswith("data: ")
    )


def _done(events) -> dict:
    for e in events:
        if e.startswith("data: "):
            payload = json.loads(e[len("data: "):])
            if payload["type"] == "done":
                return payload
    return {}


def _check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))
    return name, ok, detail


async def scenario_guest_welcome_gate():
    service = _service(count_by_user=0)
    user = FakeUser(matri_id=None)
    service.db.merge = AsyncMock(return_value=user)
    events = []
    async for chunk in service.stream_process_message(
        1, "पुण्यातील मुलींची प्रोफाइल दाखवा", None, user=user
    ):
        events.append(chunk)
    reply = _reply(events)
    done = _done(events)
    return _check(
        "guest welcome gate: WELCOME_MESSAGE + chips + matri_id_prompted",
        done.get("suggestions") == WELCOME_SUGGESTIONS
        and reply == WELCOME_MESSAGE
        and bool(DEVANAGARI.search(reply)),
        "reply/suggestions mismatch",
    )


async def scenario_greeting_branded_marathi():
    service = _service()
    user = FakeUser()
    service.db.merge = AsyncMock(return_value=user)
    events = []
    async for chunk in service.stream_process_message(1, "नमस्कार", None, user=user):
        events.append(chunk)
    reply = _reply(events)
    low = reply.lower()
    return _check(
        "greeting: Marathi, branded (never chatbot/Dishavadhuvar AI)",
        bool(reply) and bool(DEVANAGARI.search(reply))
        and "chatbot" not in low and "dishavadhuvar ai" not in low,
        "empty / English / wrong brand",
    )


async def scenario_identity_persona():
    service = _service()
    user = FakeUser()
    service.db.merge = AsyncMock(return_value=user)
    events = []
    async for chunk in service.stream_process_message(1, "तुम्ही कोण आहात", None, user=user):
        events.append(chunk)
    reply = _reply(events)
    low = reply.lower()
    return _check(
        "identity question: consultant persona, never chatbot",
        bool(reply) and bool(DEVANAGARI.search(reply))
        and "chatbot" not in low and "dishavadhuvar ai" not in low,
        "wrong persona",
    )


async def scenario_resume_search_deterministic():
    service = _service()
    user = FakeUser()
    service.db.merge = AsyncMock(return_value=user)
    rows = [{
        "MatriID": "F1", "Name": "Anita", "Age": "27", "Gender": "Female",
        "City": "Pune", "Caste": "Maratha", "Religion": "Hindu",
        "Occupation": "Engineer", "Education": "BE", "PhotoURL": "https://x.in/f1.jpg",
    }]
    with patch.object(service, "_load_history",
                      new=AsyncMock(return_value=([], {"accumulated_filters": {
                          "city": "Pune", "gender": "Female"}}))), \
         patch.object(service, "_load_user_preferences", new=AsyncMock(return_value={})), \
         patch("app.services.extraction_service.extract_search_params",
               new=AsyncMock(side_effect=AssertionError("chip route must skip LLM extraction"))), \
         patch("app.services.query_builder.build_profile_query",
               return_value=("SELECT 1", ())), \
         patch("app.services.db_query_service.execute_param_query",
               new=AsyncMock(return_value={"sql": "mock", "rows": rows, "row_count": 1})):
        events = []
        async for chunk in service.stream_process_message(
            1, "मागील सर्च चालू ठेवा", None, user=user
        ):
            events.append(chunk)
    reply = _reply(events)
    done = _done(events)
    return _check(
        "resume-search route: Marathi photo cards, no LLM, topic chips",
        bool(DEVANAGARI.search(reply))
        and "Anita" in reply and "![Anita]" in reply
        and done.get("suggestions") == WELCOME_BACK_SUGGESTIONS["profile_search"],
        "routing/format/suggestions mismatch",
    )


async def scenario_no_match_notice():
    service = _service()
    user = FakeUser()
    service.db.merge = AsyncMock(return_value=user)
    with patch.object(service, "_load_history",
                      new=AsyncMock(return_value=([], {"accumulated_filters": {
                          "city": "Pune", "gender": "Female"}}))), \
         patch.object(service, "_load_user_preferences", new=AsyncMock(return_value={})), \
         patch("app.services.extraction_service.extract_search_params",
               new=AsyncMock(side_effect=AssertionError("chip route must skip LLM extraction"))), \
         patch("app.services.query_builder.build_profile_query",
               return_value=("SELECT 1", ())), \
         patch("app.services.db_query_service.execute_param_query",
               new=AsyncMock(return_value={"sql": "mock", "rows": [], "row_count": 0})):
        events = []
        async for chunk in service.stream_process_message(
            1, "मागील सर्च चालू ठेवा", None, user=user
        ):
            events.append(chunk)
    reply = _reply(events)
    no_hallucination = "सापडली नाही" in reply and "सल्ला:" in reply
    return _check(
        "no-match: honest notice + advice, zero fabricated profiles",
        bool(DEVANAGARI.search(reply)) and no_hallucination and "![" not in reply,
        "fabricated data or missing advice",
    )


async def scenario_first_candidate_biodata():
    service = _service()
    user = FakeUser()
    service.db.merge = AsyncMock(return_value=user)
    candidates = [{"MatriID": "P1", "Name": "Anita"}]
    with patch.object(service, "_load_history",
                      new=AsyncMock(return_value=([], {"profile_candidates": candidates}))), \
         patch.object(service, "_load_user_preferences", new=AsyncMock(return_value={})), \
         patch("app.services.extraction_service.extract_search_params",
               new=AsyncMock(side_effect=AssertionError("chip route must skip LLM extraction"))), \
         patch("app.services.query_builder.build_detail_query", return_value=("SELECT 1", ())), \
         patch("app.services.db_query_service.execute_param_query",
               new=AsyncMock(return_value={"sql": "mock",
                                           "rows": [dict(candidates[0], Education="BE")],
                                           "row_count": 1})), \
         patch("app.services.llm_service.stream_format_db_result",
               new=AsyncMock(side_effect=AssertionError("CF-6 detail must be zero-LLM"))):
        events = []
        async for chunk in service.stream_process_message(
            1, "आधी पाहिलेले प्रोफाइल पुन्हा पाहा", None, user=user
        ):
            events.append(chunk)
    reply = _reply(events)
    done = _done(events)
    return _check(
        "first-candidate detail: sectioned Marathi biodata, no LLM, biodata chips",
        "शिक्षण व करिअर" in reply and bool(DEVANAGARI.search(reply))
        and done.get("suggestions") == BIODATA_SECTION_CHIPS,
        "detail not rendered deterministically",
    )


async def scenario_section_chip_biodata():
    service = _service()
    user = FakeUser()
    service.db.merge = AsyncMock(return_value=user)
    candidates = [{"MatriID": "P1", "Name": "Anita"}]
    with patch.object(service, "_load_history",
                      new=AsyncMock(return_value=([], {"profile_candidates": candidates,
                                                       "selected_profile": candidates[0]}))), \
         patch.object(service, "_load_user_preferences", new=AsyncMock(return_value={})), \
         patch("app.services.extraction_service.extract_search_params",
               new=AsyncMock(side_effect=AssertionError("section chip must skip LLM"))), \
         patch("app.services.query_builder.build_detail_query", return_value=("SELECT 1", ())), \
         patch("app.services.db_query_service.execute_param_query",
               new=AsyncMock(return_value={"sql": "mock",
                                           "rows": [dict(candidates[0], Education="BE",
                                                         Occupation="Engineer")],
                                           "row_count": 1})), \
         patch("app.services.llm_service.stream_format_db_result",
               new=AsyncMock(side_effect=AssertionError("CF-6 detail must be zero-LLM"))):
        events = []
        async for chunk in service.stream_process_message(
            1, "📚 शिक्षण व करिअर", None, user=user
        ):
            events.append(chunk)
    reply = _reply(events)
    return _check(
        "section chip: only that section, Marathi, no LLM",
        "शिक्षण व करिअर" in reply and "• शिक्षण: BE" in reply
        and "मूलभूत" not in reply and bool(DEVANAGARI.search(reply)),
        "wrong section or leaked other sections",
    )


async def scenario_welcome_back_returning():
    service = _service(count_by_user=3, prior_convs=[MagicMock(id=7), MagicMock(id=6)])

    def fake_list(conv_id):
        if conv_id == 7:
            return []
        return [MagicMock(metadata_json=json.dumps({"last_topic": "profile_search"}))]

    service.msg_repo.list_by_conversation = AsyncMock(side_effect=fake_list)
    user = FakeUser()
    service.db.merge = AsyncMock(return_value=user)

    async def fake_general(message, history, db):
        yield None, None
        yield "बोला, मी ऐकत आहे.", {
            "content": "बोला, मी ऐकत आहे.",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "events": [],
        }

    with patch("app.services.extraction_service.extract_search_params",
               new=AsyncMock(return_value={"intent": "general", "intent_label": "general"})), \
         patch("app.services.llm_service.stream_general_response", new=fake_general), \
         patch.object(service, "_load_user_preferences", new=AsyncMock(return_value={})):
        events = []
        async for chunk in service.stream_process_message(
            1, "आजची स्थिती कशी आहे?", None, user=user
        ):
            events.append(chunk)
    reply = _reply(events)
    done = _done(events)
    return _check(
        "welcome-back: परत स्वागत prefix + topic-aware chips",
        "परत स्वागत" in reply
        and done.get("suggestions") == WELCOME_BACK_SUGGESTIONS["profile_search"],
        "prefix/chips missing",
    )


async def scenario_llm_profile_search_marathi():
    service = _service()
    user = FakeUser()
    service.db.merge = AsyncMock(return_value=user)

    async def fake_format(message, sql_result, history, db):
        content = "येथे 1 जोडीदार आहे — पुणे मधील मुलगी."
        yield content, {
            "content": content,
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            "events": [],
        }

    with patch.object(service, "_load_history", new=AsyncMock(return_value=([], {}))), \
         patch.object(service, "_load_user_preferences", new=AsyncMock(return_value={})), \
         patch("app.services.extraction_service.extract_search_params",
               new=AsyncMock(return_value={"intent": "profile_search",
                                           "intent_label": "profile_search",
                                           "filters": {"gender": "Female", "city": "Pune"},
                                           "limit": 10})), \
         patch("app.services.query_builder.build_profile_query", return_value=("SELECT 1", ())), \
         patch("app.services.db_query_service.execute_param_query",
               new=AsyncMock(return_value={"sql": "mock",
                                           "rows": [{"MatriID": "F1", "Name": "Anita",
                                                     "City": "Pune"}],
                                           "row_count": 1})), \
         patch("app.services.llm_service.stream_format_db_result", new=fake_format):
        events = []
        async for chunk in service.stream_process_message(
            1, "पुण्यातील मुली दाखवा", None, user=user
        ):
            events.append(chunk)
    reply = _reply(events)
    done = _done(events)
    return _check(
        "LLM-extraction search: Marathi-first reply + non-empty routed chips",
        bool(DEVANAGARI.search(reply)) and "मुलगी" in reply
        and bool(done.get("suggestions")),
        "non-Marathi reply or missing suggestions",
    )


async def scenario_comparison_route():
    service = _service()
    user = FakeUser()
    service.db.merge = AsyncMock(return_value=user)
    with patch.object(service, "_load_history", new=AsyncMock(return_value=([], {}))), \
         patch.object(service, "_load_user_preferences", new=AsyncMock(return_value={})), \
         patch("app.services.extraction_service.extract_search_params",
               new=AsyncMock(side_effect=AssertionError("comparison chip must skip LLM"))), \
         patch("app.services.db_query_service.handle_profile_comparison",
               new=AsyncMock(return_value={
                   "content": "तुलना: अजय व स्मिता",
                   "metadata": {"compared_pair": ["P1", "P2"]},
                   "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                   "events": [],
               })):
        events = []
        async for chunk in service.stream_process_message(
            1, "आणखी दोन प्रोफाइलची तुलना करा", None, user=user
        ):
            events.append(chunk)
    reply = _reply(events)
    done = _done(events)
    return _check(
        "comparison route: routed deterministically, Marathi, chips",
        "तुलना" in reply and bool(DEVANAGARI.search(reply))
        and bool(done.get("suggestions")),
        "comparison routing failed",
    )


SCENARIOS = [
    scenario_guest_welcome_gate,
    scenario_greeting_branded_marathi,
    scenario_identity_persona,
    scenario_resume_search_deterministic,
    scenario_no_match_notice,
    scenario_first_candidate_biodata,
    scenario_section_chip_biodata,
    scenario_welcome_back_returning,
    scenario_llm_profile_search_marathi,
    scenario_comparison_route,
]


def run_harness() -> bool:
    print("=" * 70)
    print("MyVivahAI OFFLINE AI EVAL (P10) — rubric: marathi_first, no_hallucination,")
    print("routing, deterministic rendering, suggestions, identity")
    print("=" * 70)
    results = []
    for scenario in SCENARIOS:
        try:
            results.append(asyncio.run(scenario()))
        except Exception as exc:  # noqa: BLE001 - harness reports the failure
            print(f"  [ERROR] {scenario.__name__}: {exc!r}")
            results.append((scenario.__name__, False, repr(exc)))
    passed = sum(1 for _, ok, _ in results if ok)
    print("-" * 70)
    print(f"RESULTS: {passed}/{len(results)} scenarios passed")
    print("=" * 70)
    return passed == len(results)


if __name__ == "__main__":
    sys.exit(0 if run_harness() else 1)
