"""Unit tests for the CF-5 suggestions engine (chat_service).

Covers:
- build_suggestions(context) — deterministic Marathi chips based on matri link,
  questionnaire completion, and last topic (no LLM).
- SUGGESTION_ROUTES — exact-phrase click routing that skips LLM extraction
  entirely and drives deterministic profile search / detail / comparison from
  conversation memory.
- The done event carrying follow-up chips after every reply.
"""
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_service import (
    GENERIC_WELCOME_BACK_SUGGESTIONS,
    QUESTIONNAIRE_DONE_SUGGESTIONS,
    SUGGESTION_ROUTES,
    WELCOME_BACK_SUGGESTIONS,
    WELCOME_SUGGESTIONS,
    ChatService,
    build_suggestions,
)
from app.services.matri_service import BIODATA_SECTION_CHIPS


class FakeUser:
    def __init__(self, matri_id="ES92669", matri_name="Ravi Kumar", name="Ravi"):
        self.id = 1
        self.matri_id = matri_id
        self.matri_name = matri_name
        self.name = name


class BuildSuggestionsTests(unittest.TestCase):
    def test_no_matri_id_returns_welcome_chips(self):
        self.assertEqual(build_suggestions({"matri_id": None}), WELCOME_SUGGESTIONS)

    def test_questionnaire_done_returns_done_chips(self):
        result = build_suggestions({"matri_id": "ES1", "questionnaire_done": True})
        self.assertEqual(result, QUESTIONNAIRE_DONE_SUGGESTIONS)

    def test_last_topic_maps_to_topic_chips(self):
        self.assertEqual(
            build_suggestions({"matri_id": "ES1", "last_topic": "profile_search"}),
            WELCOME_BACK_SUGGESTIONS["profile_search"],
        )

    def test_unknown_topic_returns_generic_chips(self):
        self.assertEqual(
            build_suggestions({"matri_id": "ES1", "last_topic": "general"}),
            GENERIC_WELCOME_BACK_SUGGESTIONS,
        )

    def test_empty_context_returns_welcome_chips(self):
        self.assertEqual(build_suggestions({}), WELCOME_SUGGESTIONS)


class SuggestionRoutesTests(unittest.TestCase):
    def test_all_done_chips_have_a_route(self):
        for chip in QUESTIONNAIRE_DONE_SUGGESTIONS:
            self.assertIn(chip, SUGGESTION_ROUTES, f"no route for {chip!r}")

    def test_deterministic_chips_are_covered(self):
        covered = set()
        for values in WELCOME_BACK_SUGGESTIONS.values():
            covered.update(values)
        for chip in sorted(covered):
            self.assertIn(chip, SUGGESTION_ROUTES, f"no route for {chip!r}")


def _make_stream_service():
    service = ChatService(db=AsyncMock())
    service.conv_repo = MagicMock()
    service.conv_repo.create = AsyncMock(return_value=MagicMock(id=7))
    service.conv_repo.update = AsyncMock(return_value=None)
    service.conv_repo.count_by_user = AsyncMock(return_value=1)
    service.conv_repo.list_by_user = AsyncMock(return_value=[])
    service.msg_repo = MagicMock()
    service.msg_repo.create = AsyncMock(side_effect=[MagicMock(id=1), MagicMock(id=2)])
    service.msg_repo.list_by_conversation = AsyncMock(return_value=[])
    service.db = AsyncMock()
    service.db.commit = AsyncMock(return_value=None)
    service.db.flush = AsyncMock(return_value=None)
    return service


class SuggestionRouteStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_resume_search_routes_without_llm_extraction(self):
        service = _make_stream_service()
        user = FakeUser()
        service.db.merge = AsyncMock(return_value=user)
        service.conv_repo.count_by_user = AsyncMock(return_value=1)

        sql_result = {
            "sql": "mock",
            "rows": [{"MatriID": "P1", "Name": "A"}, {"MatriID": "P2", "Name": "B"}],
            "row_count": 2,
        }

        with patch(
            "app.services.extraction_service.extract_search_params",
            new=AsyncMock(side_effect=AssertionError("route must skip LLM extraction")),
        ), patch(
            "app.services.query_builder.build_profile_query",
            return_value=("SELECT 1", ()),
        ), patch(
            "app.services.db_query_service.execute_param_query",
            new=AsyncMock(return_value=sql_result),
        ) as execute, patch.object(
            service, "_load_user_preferences", new=AsyncMock(return_value={})
        ):
            events = []
            async for chunk in service.stream_process_message(
                1, "मागील सर्च चालू ठेवा", None, user=user
            ):
                events.append(chunk)

        done = json.loads(events[-1][len("data: "):])
        self.assertEqual(done["type"], "done")
        self.assertEqual(done["conversation_id"], 7)
        # last_topic profile_search -> topic-specific follow-up chips
        self.assertEqual(done["suggestions"], WELCOME_BACK_SUGGESTIONS["profile_search"])

        execute.assert_awaited_once()
        self.assertTrue(any(
            "A" in (json.loads(e[len("data: "):]).get("content") or "")
            for e in events if e.startswith("data: ")
        ))

    async def test_new_search_route_resets_accumulated_filters(self):
        service = _make_stream_service()
        user = FakeUser()
        service.db.merge = AsyncMock(return_value=user)

        sql_result = {"sql": "mock", "rows": [{"MatriID": "P1", "Name": "A"}], "row_count": 1}

        with patch.object(
            service, "_load_history",
            new=AsyncMock(return_value=([], {"accumulated_filters": {"city": "Pune"}})),
        ), patch(
            "app.services.extraction_service.extract_search_params",
            new=AsyncMock(side_effect=AssertionError("route must skip LLM extraction")),
        ), patch(
            "app.services.query_builder.build_profile_query",
            return_value=("SELECT 1", ()),
        ) as build_query, patch(
            "app.services.db_query_service.execute_param_query",
            new=AsyncMock(return_value=sql_result),
        ), patch.object(
            service, "_load_user_preferences", new=AsyncMock(return_value={})
        ):
            events = []
            async for chunk in service.stream_process_message(
                1, "नवीन सर्च सुरू करा", None, user=user
            ):
                events.append(chunk)

        filters = build_query.call_args[0][0]
        self.assertNotIn("city", filters)

    async def test_first_candidate_detail_route_resolves_from_candidates(self):
        service = _make_stream_service()
        user = FakeUser()
        service.db.merge = AsyncMock(return_value=user)
        candidates = [{"MatriID": "P1", "Name": "A"}, {"MatriID": "P2", "Name": "B"}]

        with patch.object(
            service, "_load_history",
            new=AsyncMock(return_value=([], {"profile_candidates": candidates})),
        ), patch(
            "app.services.extraction_service.extract_search_params",
            new=AsyncMock(side_effect=AssertionError("route must skip LLM extraction")),
        ), patch(
            "app.services.query_builder.build_detail_query",
            return_value=("SELECT 1", ()),
        ), patch(
            "app.services.db_query_service.execute_param_query",
            new=AsyncMock(return_value={"sql": "mock", "rows": [dict(candidates[0], Education="BE")], "row_count": 1}),
        ), patch(
            "app.services.llm_service.stream_format_db_result",
            new=AsyncMock(side_effect=AssertionError("CF-6 detail renders biodata without the LLM formatter")),
        ), patch.object(
            service, "_load_user_preferences", new=AsyncMock(return_value={})
        ):
            events = []
            async for chunk in service.stream_process_message(
                1, "आधी पाहिलेले प्रोफाइल पुन्हा पाहा", None, user=user
            ):
                events.append(chunk)

        done = json.loads(events[-1][len("data: "):])
        self.assertEqual(done["type"], "done")
        self.assertEqual(done["suggestions"], BIODATA_SECTION_CHIPS)
        reply = "".join(
            json.loads(e[len("data: "):]).get("content") or ""
            for e in events if e.startswith("data: ")
        )
        self.assertIn("👤 **A** · P1", reply)
        self.assertIn("📚 **शिक्षण व करिअर:**", reply)


if __name__ == "__main__":
    unittest.main()
