"""Unit tests for the CF-1 identity gate (chat_service._apply_identity_gate).

Soft mode welcomes the first message of a brand-new conversation from a user
with no linked MatriID (persisting ``matri_id_prompted`` + suggestion chips)
and then allows guest browsing; hard mode blocks every message until a
MatriID is linked. ID-looking messages always fall through to auto-link.
"""
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_service import (
    WELCOME_MESSAGE,
    WELCOME_SUGGESTIONS,
    ChatService,
)


class FakeUser:
    def __init__(self, matri_id="ES92669", matri_name="Ravi Kumar", name="Ravi"):
        self.id = 1
        self.matri_id = matri_id
        self.matri_name = matri_name
        self.name = name


class IdentityGateUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_matri_id_new_conversation_returns_welcome(self):
        service = ChatService(db=AsyncMock())
        result = await service._apply_identity_gate(
            FakeUser(matri_id=None), "पुण्यातील 5 मुलींची प्रोफाइल दाखवा", None
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["reply"], WELCOME_MESSAGE)
        self.assertTrue(result["metadata"]["matri_id_prompted"])
        self.assertEqual(result["metadata"]["suggestions"], WELCOME_SUGGESTIONS)

    async def test_linked_user_skips_gate(self):
        service = ChatService(db=AsyncMock())
        result = await service._apply_identity_gate(
            FakeUser(), "पुण्यातील 5 मुलींची प्रोफाइल दाखवा", None
        )
        self.assertIsNone(result)

    async def test_none_user_skips_gate(self):
        service = ChatService(db=AsyncMock())
        result = await service._apply_identity_gate(None, "हाय", None)
        self.assertIsNone(result)

    async def test_id_message_skips_gate(self):
        service = ChatService(db=AsyncMock())
        result = await service._apply_identity_gate(
            FakeUser(matri_id=None), "ES92669", None
        )
        self.assertIsNone(result)

    async def test_soft_mode_skips_existing_conversation(self):
        service = ChatService(db=AsyncMock())
        result = await service._apply_identity_gate(
            FakeUser(matri_id=None), "पुण्यातील 5 मुलींची प्रोफाइल दाखवा", 7
        )
        self.assertIsNone(result)

    async def test_hard_mode_blocks_existing_conversation(self):
        service = ChatService(db=AsyncMock())
        with patch("app.services.chat_service.settings.MATRI_ID_GATE_MODE", "hard"):
            result = await service._apply_identity_gate(
                FakeUser(matri_id=None), "पुण्यातील 5 मुलींची प्रोफाइल दाखवा", 7
            )
        self.assertIsNotNone(result)
        self.assertTrue(result["metadata"]["matri_id_prompted"])


def _make_stream_service():
    service = ChatService(db=AsyncMock())
    service.conv_repo = MagicMock()
    service.conv_repo.create = AsyncMock(return_value=MagicMock(id=7))
    service.conv_repo.update = AsyncMock(return_value=None)
    service.msg_repo = MagicMock()
    service.msg_repo.create = AsyncMock(side_effect=[MagicMock(id=1), MagicMock(id=2)])
    service.db = AsyncMock()
    service.db.commit = AsyncMock(return_value=None)
    return service


class IdentityGateStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_soft_gate_streams_welcome_then_done_with_suggestions(self):
        service = _make_stream_service()
        user = FakeUser(matri_id=None)
        service.db.merge = AsyncMock(return_value=user)

        events = []
        async for chunk in service.stream_process_message(
            1, "पुण्यातील 5 मुलींची प्रोफाइल दाखवा", None, user=user
        ):
            events.append(chunk)

        self.assertEqual(len(events), 2)
        token = json.loads(events[0][len("data: "):])
        done = json.loads(events[1][len("data: "):])
        self.assertEqual(token["type"], "token")
        self.assertEqual(token["content"], WELCOME_MESSAGE)
        self.assertEqual(done["type"], "done")
        self.assertEqual(done["conversation_id"], 7)
        self.assertEqual(done["message_id"], 2)
        self.assertEqual(done["suggestions"], WELCOME_SUGGESTIONS)

        self.assertEqual(len(service.msg_repo.create.await_args_list), 2)
        meta_json = service.msg_repo.create.await_args_list[1].kwargs["metadata_json"]
        self.assertIn('"matri_id_prompted": true', meta_json)
        self.assertIn('"suggestions"', meta_json)

    async def test_hard_mode_blocks_existing_conversation_with_welcome(self):
        service = _make_stream_service()
        service.conv_repo.get_by_id = AsyncMock(
            return_value=MagicMock(id=7, user_id=1)
        )
        user = FakeUser(matri_id=None)
        service.db.merge = AsyncMock(return_value=user)

        with patch("app.services.chat_service.settings.MATRI_ID_GATE_MODE", "hard"):
            events = []
            async for chunk in service.stream_process_message(
                1, "पुण्यातील 5 मुलींची प्रोफाइल दाखवा", 7, user=user
            ):
                events.append(chunk)

        self.assertEqual(len(events), 2)
        token = json.loads(events[0][len("data: "):])
        done = json.loads(events[1][len("data: "):])
        self.assertEqual(token["content"], WELCOME_MESSAGE)
        self.assertEqual(done["conversation_id"], 7)


if __name__ == "__main__":
    unittest.main()
