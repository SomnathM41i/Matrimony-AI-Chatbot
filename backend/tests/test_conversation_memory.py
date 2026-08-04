"""Unit tests for the CF-4 conversation memory (chat_service).

Covers:
- _load_history restoring the explicit memory fields (last_topic, viewed_profiles,
  compared_pairs, last_filters) plus the questionnaire_searched flag.
- _enrich_memory deriving those fields from raw assistant metadata.
- _welcome_back returning a Marathi prefix + context-aware chips for a linked
  returning user on a brand-new conversation (and None for guests, continuing
  conversations, or first-ever chats).
- _last_topic_across_conversations scanning the most recent prior conversation.
- The streaming path streaming the prefix first and carrying suggestions in the
  done event, while persisting the memory fields in the assistant metadata.
"""
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_service import (
    GENERIC_WELCOME_BACK_SUGGESTIONS,
    WELCOME_BACK_PREFIX,
    WELCOME_BACK_SUGGESTIONS,
    ChatService,
    _enrich_memory,
)


class FakeUser:
    def __init__(self, matri_id="ES92669", matri_name="Ravi Kumar", name="Ravi"):
        self.id = 1
        self.matri_id = matri_id
        self.matri_name = matri_name
        self.name = name


class EnrichMemoryTests(unittest.TestCase):
    def test_derives_memory_fields_from_raw_metadata(self):
        meta = _enrich_memory(
            {
                "profile_candidates": [
                    {"MatriID": "P1", "Name": "A"},
                    {"MatriID": "P2", "Name": "B"},
                    {"MatriID": "P3", "Name": None},
                ],
                "accumulated_filters": {"gender": "Female", "city": "Pune"},
                "compared_pair": [
                    {"MatriID": "P1", "Name": "A"},
                    {"MatriID": "P2", "Name": "B"},
                ],
            },
            "comparison",
        )
        self.assertEqual(meta["last_topic"], "comparison")
        self.assertEqual(
            meta["viewed_profiles"],
            [{"MatriID": "P1", "Name": "A"}, {"MatriID": "P2", "Name": "B"}],
        )
        self.assertEqual(
            meta["compared_pairs"],
            [meta["compared_pair"]],
        )
        self.assertEqual(meta["last_filters"], {"gender": "Female", "city": "Pune"})

    def test_does_not_overwrite_existing_memory_fields(self):
        meta = _enrich_memory(
            {
                "last_topic": "profile_detail",
                "viewed_profiles": [{"MatriID": "P9", "Name": "Z"}],
                "last_filters": {"city": "Nagpur"},
                "profile_candidates": [{"MatriID": "P1", "Name": "A"}],
                "accumulated_filters": {"city": "Mumbai"},
            },
            "comparison",
        )
        self.assertEqual(meta["last_topic"], "profile_detail")
        self.assertEqual(meta["viewed_profiles"], [{"MatriID": "P9", "Name": "Z"}])
        self.assertEqual(meta["last_filters"], {"city": "Nagpur"})

    def test_none_metadata_returns_empty_mapping(self):
        self.assertEqual(_enrich_memory(None, None), {})

    def test_last_topic_set_only_when_label_given(self):
        self.assertEqual(_enrich_memory({}, None), {})
        self.assertEqual(_enrich_memory({}, "general")["last_topic"], "general")


class LoadHistoryMemoryTests(unittest.IsolatedAsyncioTestCase):
    def _msg(self, metadata: dict | None) -> MagicMock:
        return MagicMock(
            metadata_json=json.dumps(metadata) if metadata is not None else None
        )

    async def test_restores_memory_fields_across_turns(self):
        service = ChatService(db=AsyncMock())
        msgs = [
            self._msg({
                "last_topic": "profile_search",
                "viewed_profiles": [{"MatriID": "P1", "Name": "A"}],
                "selected_profile": {"MatriID": "P1", "Name": "A"},
            }),
            self._msg({"compared_pairs": [{"MatriID": "P1", "Name": "A"}, {"MatriID": "P2", "Name": "B"}]}),
            self._msg({"last_filters": {"gender": "Female", "city": "Pune"}}),
            self._msg({"questionnaire_searched": True}),
        ]
        service.msg_repo = MagicMock()
        service.msg_repo.list_by_conversation = AsyncMock(return_value=msgs)

        history, ctx = await service._load_history(42)

        self.assertEqual(ctx["last_topic"], "profile_search")
        self.assertEqual(ctx["viewed_profiles"], [{"MatriID": "P1", "Name": "A"}])
        self.assertEqual(ctx["compared_pairs"], [{"MatriID": "P1", "Name": "A"}, {"MatriID": "P2", "Name": "B"}])
        self.assertEqual(ctx["last_filters"], {"gender": "Female", "city": "Pune"})
        self.assertTrue(ctx["questionnaire_searched"])
        self.assertTrue(any(m.get("role") == "system" for m in history))

    async def test_ignores_invalid_metadata(self):
        service = ChatService(db=AsyncMock())
        msgs = [MagicMock(metadata_json="not-json")]
        service.msg_repo = MagicMock()
        service.msg_repo.list_by_conversation = AsyncMock(return_value=msgs)
        history, ctx = await service._load_history(42)
        self.assertEqual(ctx["last_topic"], None)
        self.assertEqual(ctx["viewed_profiles"], None)


class WelcomeBackUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_guest_gets_none(self):
        service = ChatService(db=AsyncMock())
        result = await service._welcome_back(FakeUser(matri_id=None), 1, None)
        self.assertIsNone(result)

    async def test_continuing_conversation_gets_none(self):
        service = ChatService(db=AsyncMock())
        result = await service._welcome_back(FakeUser(), 1, 7)
        self.assertIsNone(result)

    async def test_first_ever_chat_gets_none(self):
        service = ChatService(db=AsyncMock())
        service.conv_repo = MagicMock()
        service.conv_repo.count_by_user = AsyncMock(return_value=1)
        result = await service._welcome_back(FakeUser(), 1, None)
        self.assertIsNone(result)

    async def test_returning_user_gets_prefix_and_topic_suggestions(self):
        service = ChatService(db=AsyncMock())
        service.conv_repo = MagicMock()
        service.conv_repo.count_by_user = AsyncMock(return_value=3)
        service._last_topic_across_conversations = AsyncMock(
            return_value="profile_search"
        )
        result = await service._welcome_back(FakeUser(), 1, None)
        self.assertIsNotNone(result)
        self.assertEqual(result["prefix"], WELCOME_BACK_PREFIX.format(name="Ravi"))
        self.assertEqual(
            result["suggestions"], WELCOME_BACK_SUGGESTIONS["profile_search"]
        )

    async def test_returning_user_unknown_topic_uses_generic(self):
        service = ChatService(db=AsyncMock())
        service.conv_repo = MagicMock()
        service.conv_repo.count_by_user = AsyncMock(return_value=2)
        service._last_topic_across_conversations = AsyncMock(return_value=None)
        result = await service._welcome_back(FakeUser(), 1, None)
        self.assertEqual(result["suggestions"], GENERIC_WELCOME_BACK_SUGGESTIONS)

    async def test_count_by_user_not_int_falls_through(self):
        service = ChatService(db=AsyncMock())
        service.conv_repo = MagicMock()
        service.conv_repo.count_by_user = AsyncMock(return_value=AsyncMock())
        result = await service._welcome_back(FakeUser(), 1, None)
        self.assertIsNone(result)


class LastTopicAcrossConversationsTests(unittest.IsolatedAsyncioTestCase):
    def _msg(self, last_topic: str | None) -> MagicMock:
        return MagicMock(
            metadata_json=json.dumps({"last_topic": last_topic})
            if last_topic
            else "{}"
        )

    async def test_scans_newest_prior_conversation_first(self):
        service = ChatService(db=AsyncMock())
        service.conv_repo = MagicMock()
        service.msg_repo = MagicMock()
        service.conv_repo.list_by_user = AsyncMock(
            return_value=[MagicMock(id=7), MagicMock(id=6), MagicMock(id=5)]
        )

        def fake_list(conv_id):
            if conv_id == 7:
                return []  # current conversation has no topic yet
            if conv_id == 6:
                return [self._msg("profile_search"), self._msg(None)]
            return [self._msg("comparison")]

        service.msg_repo.list_by_conversation = AsyncMock(side_effect=fake_list)

        result = await service._last_topic_across_conversations(1)
        self.assertEqual(result, "profile_search")

    async def test_returns_none_when_no_topic_found(self):
        service = ChatService(db=AsyncMock())
        service.conv_repo = MagicMock()
        service.msg_repo = MagicMock()
        service.conv_repo.list_by_user = AsyncMock(return_value=[MagicMock(id=7)])
        service.msg_repo.list_by_conversation = AsyncMock(return_value=[])
        self.assertIsNone(await service._last_topic_across_conversations(1))


def _make_stream_service():
    service = ChatService(db=AsyncMock())
    service.conv_repo = MagicMock()
    service.conv_repo.create = AsyncMock(return_value=MagicMock(id=7))
    service.conv_repo.update = AsyncMock(return_value=None)
    service.conv_repo.count_by_user = AsyncMock(return_value=3)
    service.conv_repo.list_by_user = AsyncMock(
        return_value=[MagicMock(id=7), MagicMock(id=6)]
    )
    service.msg_repo = MagicMock()
    service.msg_repo.create = AsyncMock(side_effect=[MagicMock(id=1), MagicMock(id=2)])

    def fake_list(conv_id):
        if conv_id == 7:
            return []
        return [
            MagicMock(metadata_json=json.dumps({"last_topic": "profile_search"}))
        ]

    service.msg_repo.list_by_conversation = AsyncMock(side_effect=fake_list)
    service.db = AsyncMock()
    service.db.commit = AsyncMock(return_value=None)
    service.db.flush = AsyncMock(return_value=None)
    return service


class WelcomeBackStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_returning_user_streams_prefix_and_done_suggestions(self):
        service = _make_stream_service()
        user = FakeUser()
        service.db.merge = AsyncMock(return_value=user)

        async def fake_general(message, history, db):
            yield None, None
            yield "बोला, मी ऐकत आहे.", {
                "content": "बोला, मी ऐकत आहे.",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "events": [],
            }

        with patch(
            "app.services.extraction_service.extract_search_params",
            new=AsyncMock(return_value={"intent": "general", "intent_label": "general"}),
        ), patch(
            "app.services.llm_service.stream_general_response", new=fake_general
        ), patch.object(
            service, "_load_user_preferences", new=AsyncMock(return_value={})
        ):
            events = []
            async for chunk in service.stream_process_message(
                1, "आजची स्थिती कशी आहे?", None, user=user
            ):
                events.append(chunk)

        first = json.loads(events[0][len("data: "):])
        self.assertEqual(first["type"], "token")
        self.assertEqual(first["content"], WELCOME_BACK_PREFIX.format(name="Ravi"))

        done = json.loads(events[-1][len("data: "):])
        self.assertEqual(done["type"], "done")
        self.assertEqual(done["suggestions"], WELCOME_BACK_SUGGESTIONS["profile_search"])

        self.assertEqual(len(service.msg_repo.create.await_args_list), 2)
        meta_json = service.msg_repo.create.await_args_list[1].kwargs["metadata_json"]
        self.assertIn('"last_topic": "general"', meta_json)
        self.assertIn('"suggestions"', meta_json)

    async def test_first_ever_user_gets_no_prefix(self):
        service = _make_stream_service()
        service.conv_repo.count_by_user = AsyncMock(return_value=1)
        user = FakeUser()
        service.db.merge = AsyncMock(return_value=user)

        async def fake_general(message, history, db):
            yield None, None
            yield "बोला, मी ऐकत आहे.", {
                "content": "बोला, मी ऐकत आहे.",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "events": [],
            }

        with patch(
            "app.services.extraction_service.extract_search_params",
            new=AsyncMock(return_value={"intent": "general", "intent_label": "general"}),
        ), patch(
            "app.services.llm_service.stream_general_response", new=fake_general
        ), patch.object(
            service, "_load_user_preferences", new=AsyncMock(return_value={})
        ):
            events = []
            async for chunk in service.stream_process_message(
                1, "आजची स्थिती कशी आहे?", None, user=user
            ):
                events.append(chunk)

        first = json.loads(events[0][len("data: "):])
        self.assertEqual(first["type"], "status")
        done = json.loads(events[-1][len("data: "):])
        # CF-5: every reply now carries deterministic follow-up chips (generic
        # here — a "general" topic for a first-ever linked user).
        self.assertEqual(done["suggestions"], GENERIC_WELCOME_BACK_SUGGESTIONS)


if __name__ == "__main__":
    unittest.main()
