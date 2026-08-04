"""Unit tests for the chat-driven questionnaire flow (chat_service._process_questionnaire).

These tests exercise session auto-start (fresh chat + linked ID + no saved
prefs), per-answer advance/re-ask, and the completion step that saves the
preferences and runs a profile search.
"""
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_service import (
    QUESTIONNAIRE_DONE_PREFIX,
    ChatService,
)


class FakeUser:
    def __init__(self, matri_id="ES92669", matri_name="Ravi Kumar", name="Ravi"):
        self.id = 1
        self.matri_id = matri_id
        self.matri_name = matri_name
        self.name = name


def _make_service():
    service = ChatService(db=AsyncMock())
    service.db.flush = AsyncMock(return_value=None)
    return service


PE = {"gender": "Female"}

# Answers that reach the final (complexion) question.
ANSWERS_BEFORE_LAST = [
    {"node_id": "age_range_fresh", "option_id": "26_30"},
    {"node_id": "marital_status_fresh", "option_id": "unmarried"},
    {"node_id": "religion_fresh", "option_id": "hindu"},
    {"node_id": "caste_fresh", "option_id": "custom", "value": "Maratha"},
    {"node_id": "subcaste_fresh", "option_id": "any"},
    {"node_id": "education_fresh", "option_id": "graduate"},
    {"node_id": "occupation_fresh", "option_id": "custom", "value": "Engineer"},
    {"node_id": "city_fresh", "option_id": "custom", "value": "Pune"},
    {"node_id": "manglik_fresh", "option_id": "no"},
]


def _active_session():
    return {
        "questionnaire_answers": [],
        "questionnaire_pe_filters": PE,
        "questionnaire_done": False,
    }


class QuestionnaireFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_matri_id_falls_through(self):
        service = _make_service()
        result = await service._process_questionnaire(
            FakeUser(matri_id=None), 1, "26", _active_session(), 7, [],
        )
        self.assertIsNone(result)

    async def test_done_session_falls_through(self):
        service = _make_service()
        ctx = {**_active_session(), "questionnaire_done": True}
        result = await service._process_questionnaire(FakeUser(), 1, "26", ctx, 7, [])
        self.assertIsNone(result)

    async def test_fresh_chat_auto_start_asks_age(self):
        service = _make_service()
        result = await service._process_questionnaire(
            FakeUser(), 1, "नमस्कार", {"default_filters": dict(PE)}, None, [],
        )
        self.assertIsNotNone(result)
        self.assertIn("Ravi", result["reply"])
        self.assertIn("वयोगट", result["reply"])
        self.assertEqual(result["metadata"]["questionnaire_answers"], [])
        self.assertFalse(result["metadata"]["questionnaire_done"])

    async def test_fresh_chat_with_saved_prefs_starts_missing_only(self):
        service = _make_service()
        ctx = {"default_filters": {"gender": "Female", "city": "Pune"}}
        result = await service._process_questionnaire(FakeUser(), 1, "नमस्कार", ctx, None, [])
        # Missing-only onboarding auto-applies the known city and asks the first
        # missing category (age range), not a keep/change confirm.
        self.assertIsNotNone(result)
        self.assertIn("वयोगट", result["reply"])
        self.assertNotIn("कायम ठेवा", result["reply"])

    async def test_fresh_chat_without_gender_does_not_start(self):
        service = _make_service()
        result = await service._process_questionnaire(
            FakeUser(), 1, "नमस्कार", {"default_filters": {}}, None, [],
        )
        self.assertIsNone(result)

    async def test_existing_conversation_without_session_does_not_start(self):
        service = _make_service()
        result = await service._process_questionnaire(
            FakeUser(), 1, "नमस्कार", {"default_filters": dict(PE)}, 7, [],
        )
        self.assertIsNone(result)

    async def test_advance_parses_numbered_answer(self):
        service = _make_service()
        result = await service._process_questionnaire(FakeUser(), 1, "26", _active_session(), 7, [])
        self.assertIsNotNone(result)
        self.assertIn("वैवाहिक", result["reply"])
        answers = result["metadata"]["questionnaire_answers"]
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]["option_id"], "26_30")
        self.assertFalse(result["metadata"]["questionnaire_done"])

    async def test_advance_parses_marathi_synonym(self):
        service = _make_service()
        ctx = _active_session()
        ctx["questionnaire_answers"] = [{"node_id": "age_range_fresh", "option_id": "26_30"}]
        result = await service._process_questionnaire(FakeUser(), 1, "घटस्फोटित", ctx, 7, [])
        self.assertIsNotNone(result)
        self.assertEqual(result["metadata"]["questionnaire_answers"][1]["option_id"], "divorced")

    async def test_reask_on_unparsed_answer(self):
        service = _make_service()
        result = await service._process_questionnaire(FakeUser(), 1, "blah blah", _active_session(), 7, [])
        self.assertIsNotNone(result)
        self.assertIn("समजले नाही", result["reply"])
        self.assertIn("वयोगट", result["reply"])
        self.assertEqual(result["metadata"]["questionnaire_answers"], [])
        self.assertFalse(result["metadata"]["questionnaire_done"])

    async def test_auto_start_skipped_when_user_has_prior_conversations(self):
        service = _make_service()
        service.conv_repo.count_by_user = AsyncMock(return_value=3)
        result = await service._process_questionnaire(
            FakeUser(), 1, "नमस्कार", {"default_filters": dict(PE)}, None, [],
        )
        self.assertIsNone(result)

    async def test_search_early_prepends_matches_above_next_question(self):
        service = _make_service()
        ctx = dict(_active_session())
        search_result = {
            "matched": "some",
            "content": "**उपलब्ध प्रोफाइल:** Ravi's picks",
            "metadata": {
                "profile_candidates": [{"MatriID": "P1", "Name": "A"}],
                "selected_profile": None,
                "accumulated_filters": {"gender": "Female", "age_min": "26", "age_max": "30"},
            },
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        with patch(
            "app.services.chat_service.handle_profile_search",
            new=AsyncMock(return_value=search_result),
        ):
            result = await service._process_questionnaire(FakeUser(), 1, "26", ctx, 7, [])

        self.assertIsNotNone(result)
        self.assertIn("Ravi's picks", result["reply"])
        self.assertIn("वैवाहिक", result["reply"])
        self.assertTrue(result["metadata"]["questionnaire_searched"])
        self.assertEqual(result["metadata"]["profile_candidates"][0]["MatriID"], "P1")

    async def test_search_early_does_not_repeat_in_same_session(self):
        service = _make_service()
        ctx = dict(_active_session())
        search_result = {
            "matched": "some",
            "content": "**उपलब्ध प्रोफाइल:** Ravi's picks",
            "metadata": {
                "profile_candidates": [{"MatriID": "P1", "Name": "A"}],
                "selected_profile": None,
                "accumulated_filters": {},
            },
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        with patch(
            "app.services.chat_service.handle_profile_search",
            new=AsyncMock(return_value=search_result),
        ) as search:
            first = await service._process_questionnaire(FakeUser(), 1, "26", ctx, 7, [])
            ctx2 = dict(first["metadata"])
            second = await service._process_questionnaire(FakeUser(), 1, "2", ctx2, 7, [])

        self.assertEqual(search.await_count, 1)
        self.assertIsNotNone(second)
        self.assertNotIn("Ravi's picks", second["reply"])

    async def test_flow_completion_saves_prefs_and_searches(self):
        service = _make_service()
        search_result = {
            "content": "येथे 2 जोडीदार आहेत",
            "matched": "some",
            "metadata": {
                "profile_candidates": [{"MatriID": "F1", "Name": "A"}],
                "selected_profile": None,
                "accumulated_filters": {"gender": "Female"},
            },
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }
        with patch(
            "app.services.chat_service.handle_profile_search",
            new=AsyncMock(return_value=search_result),
        ) as mock_search:
            with patch(
                "app.repositories.preference_repository.PreferenceRepository.replace_all",
                new=AsyncMock(return_value=None),
            ) as mock_replace:
                result = await service._process_questionnaire(
                    FakeUser(), 1, "1",
                    {**_active_session(), "questionnaire_answers": ANSWERS_BEFORE_LAST},
                    7, [],
                )

        self.assertIsNotNone(result)
        self.assertTrue(result["metadata"]["questionnaire_done"])
        self.assertTrue(result["reply"].startswith(QUESTIONNAIRE_DONE_PREFIX.format(name="Ravi")))
        self.assertIn("येथे 2 जोडीदार आहेत", result["reply"])
        mock_replace.assert_awaited_once()
        mock_search.assert_awaited_once()

        filters = mock_replace.await_args.args[1]
        self.assertEqual(filters["gender"], "Female")
        self.assertEqual(filters["age_min"], "26")
        self.assertEqual(filters["age_max"], "30")
        self.assertEqual(filters["marital_status"], "Unmarried")
        self.assertEqual(filters["religion"], "Hindu")
        self.assertEqual(filters["caste"], "Maratha")
        self.assertEqual(filters["education"], "Graduate")
        self.assertEqual(filters["occupation"], "Engineer")
        self.assertEqual(filters["city"], "Pune")
        self.assertEqual(filters["manglik"], "No")
        self.assertEqual(filters["complexion"], "Very Fair")

        mock_search.assert_awaited_once()
        searched_filters = mock_search.await_args.args[1]
        self.assertEqual(searched_filters, filters)

    async def test_usage_surfaces_from_search(self):
        service = _make_service()
        with patch(
            "app.services.chat_service.handle_profile_search",
            new=AsyncMock(return_value={
                "content": "ok",
                "metadata": {},
                "usage": {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11},
            }),
        ), patch(
            "app.repositories.preference_repository.PreferenceRepository.replace_all",
            new=AsyncMock(return_value=None),
        ):
            result = await service._process_questionnaire(
                FakeUser(), 1, "1",
                {**_active_session(), "questionnaire_answers": ANSWERS_BEFORE_LAST},
                7, [],
            )
        self.assertEqual(result["usage"]["total_tokens"], 11)

    async def test_auto_start_metadata_includes_clickable_options(self):
        service = _make_service()
        result = await service._process_questionnaire(
            FakeUser(), 1, "नमस्कार", {"default_filters": dict(PE)}, None, [],
        )
        self.assertIsNotNone(result)
        opts = result["metadata"]["questionnaire_options"]
        self.assertTrue(opts)
        self.assertIn("label", opts[0])
        self.assertEqual(
            result["metadata"]["questionnaire_progress"],
            {"current": 1, "total": 10},
        )

    async def test_advance_metadata_includes_options(self):
        service = _make_service()
        result = await service._process_questionnaire(FakeUser(), 1, "26", _active_session(), 7, [])
        self.assertIsNotNone(result)
        self.assertTrue(result["metadata"]["questionnaire_options"])
        self.assertEqual(result["metadata"]["questionnaire_progress"]["current"], 2)


def _make_stream_service():
    service = ChatService(db=AsyncMock())
    service.conv_repo = AsyncMock()
    service.msg_repo = AsyncMock()
    service.conv_repo.get_by_id = AsyncMock(return_value=MagicMock(id=7, user_id=1))
    service.conv_repo.update = AsyncMock(return_value=None)
    service.db = AsyncMock()
    service.db.commit = AsyncMock(return_value=None)
    return service


class StreamQuestionnaireTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_questionnaire_emits_token_then_done_with_options(self):
        service = _make_stream_service()
        service.msg_repo.create = AsyncMock(side_effect=[MagicMock(id=1), MagicMock(id=2)])
        flow_result = {
            "reply": "तुमच्या जोडीदाराची वैवाहिक स्थिती कशी हवी?\n1. कधीही लग्न न केलेले\n2. घटस्फोटित\n",
            "metadata": {
                "questionnaire_answers": [{"node_id": "age_range_fresh", "option_id": "26_30"}],
                "questionnaire_pe_filters": PE,
                "questionnaire_done": False,
                "questionnaire_options": [
                    {"id": "unmarried", "label": "कधीही लग्न न केलेले"},
                    {"id": "divorced", "label": "घटस्फोटित"},
                ],
                "questionnaire_progress": {"current": 2, "total": 14},
            },
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        with patch.object(service, "_load_history", new=AsyncMock(return_value=([], {}))), \
             patch.object(service, "_load_user_preferences", new=AsyncMock(return_value={})), \
             patch.object(service, "_process_questionnaire", new=AsyncMock(return_value=flow_result)):
            events = []
            async for chunk in service.stream_process_message(1, "1", 7, user=FakeUser()):
                events.append(chunk)

        self.assertEqual(len(events), 2)
        token = json.loads(events[0][len("data: "):])
        done = json.loads(events[1][len("data: "):])
        self.assertEqual(token["type"], "token")
        self.assertIn("कधीही लग्न", token["content"])
        self.assertEqual(done["type"], "done")
        self.assertEqual(done["conversation_id"], 7)
        self.assertEqual(done["message_id"], 2)
        self.assertEqual(done["questionnaire"]["options"][0]["label"], "कधीही लग्न न केलेले")
        self.assertEqual(done["questionnaire"]["progress"], {"current": 2, "total": 14})

    async def test_stream_completion_done_has_no_options(self):
        service = _make_stream_service()
        service.msg_repo.create = AsyncMock(side_effect=[MagicMock(id=1), MagicMock(id=2)])
        flow_result = {
            "reply": "धन्यवाद! येथे प्रोफाइल आहेत.",
            "metadata": {
                "questionnaire_answers": [{"node_id": "x_fresh", "option_id": "y"}],
                "questionnaire_pe_filters": PE,
                "questionnaire_done": True,
            },
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        with patch.object(service, "_load_history", new=AsyncMock(return_value=([], {}))), \
             patch.object(service, "_load_user_preferences", new=AsyncMock(return_value={})), \
             patch.object(service, "_process_questionnaire", new=AsyncMock(return_value=flow_result)):
            events = []
            async for chunk in service.stream_process_message(1, "1", 7, user=FakeUser()):
                events.append(chunk)
        done = json.loads(events[-1][len("data: "):])
        self.assertNotIn("questionnaire", done)

    async def test_stream_auto_link_done_carries_questionnaire(self):
        service = _make_stream_service()
        linked_result = {
            "reply": "नमस्कार Ravi! ... प्रश्न 1/14",
            "conversation_id": 7,
            "message_id": 9,
            "metadata": {
                "questionnaire_answers": [],
                "questionnaire_pe_filters": PE,
                "questionnaire_done": False,
                "questionnaire_options": [{"id": "26_30", "label": "26 - 30 वर्षे"}],
                "questionnaire_progress": {"current": 1, "total": 14},
            },
        }
        with patch.object(service, "_try_auto_link_matri", new=AsyncMock(return_value=linked_result)):
            events = []
            async for chunk in service.stream_process_message(1, "ES92669", None, user=FakeUser()):
                events.append(chunk)
        done = json.loads(events[-1][len("data: "):])
        self.assertEqual(done["message_id"], 9)
        self.assertEqual(done["questionnaire"]["options"][0]["label"], "26 - 30 वर्षे")


def _chunk(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


class ProcessMessageMergeTests(unittest.IsolatedAsyncioTestCase):
    """The non-streaming entry point must reassemble the single streaming
    pipeline's events into the legacy dict shape."""

    async def test_reassembles_tokens_and_done(self):
        service = _make_stream_service()

        async def fake_stream(*args, **kwargs):
            yield _chunk({"type": "token", "content": "नमस्कार"})
            yield _chunk({"type": "status", "step": "think"})
            yield _chunk({"type": "token", "content": " तुम्हाला कशी मदत करू?"})
            yield _chunk({
                "type": "done",
                "conversation_id": 7,
                "message_id": 42,
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            })

        with patch.object(service, "stream_process_message", new=fake_stream):
            result = await service.process_message(1, "hi", None, user=FakeUser())

        self.assertEqual(result["reply"], "नमस्कार तुम्हाला कशी मदत करू?")
        self.assertEqual(result["conversation_id"], 7)
        self.assertEqual(result["message_id"], 42)
        self.assertEqual(result["usage"]["total_tokens"], 3)
        self.assertTrue(result["request_id"])

    async def test_error_event_persists_reply(self):
        service = _make_stream_service()
        service.msg_repo.create = AsyncMock(return_value=MagicMock(id=99))
        service.conv_repo.get_by_id = AsyncMock(return_value=MagicMock(id=7, user_id=1))
        service.conv_repo.update = AsyncMock(return_value=None)

        async def fake_stream(*args, **kwargs):
            yield _chunk({"type": "error", "content": "क्षमस्व, डेटाबेस उपलब्ध नाही.", "conversation_id": 7})

        with patch.object(service, "stream_process_message", new=fake_stream):
            result = await service.process_message(1, "show girls", 7, user=FakeUser())

        self.assertEqual(result["reply"], "क्षमस्व, डेटाबेस उपलब्ध नाही.")
        self.assertEqual(result["message_id"], 99)
        self.assertEqual(result["conversation_id"], 7)
        self.assertEqual(result["usage"]["total_tokens"], 0)

    async def test_empty_stream_returns_graceful_dict(self):
        service = _make_stream_service()

        async def fake_stream(*args, **kwargs):
            return
            yield

        with patch.object(service, "stream_process_message", new=fake_stream):
            result = await service.process_message(1, "hi", None, user=FakeUser())

        self.assertEqual(result["reply"], "")
        self.assertEqual(result["conversation_id"], None)
        self.assertEqual(result["message_id"], None)


if __name__ == "__main__":
    unittest.main()
