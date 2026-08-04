"""Unit tests for chat-time MatriID detection and auto-linking."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_service import (
    MATRI_ID_ERROR,
    MATRI_ID_NOT_FOUND,
    MATRI_ID_SUCCESS,
    ChatService,
    _extract_matri_id,
)
from app.services.matri_service import MatriLinkError


class FakeUser:
    def __init__(self, matri_id=None, matri_name=None):
        self.id = 1
        self.matri_id = matri_id
        self.matri_name = matri_name


class ExtractMatriIdTests(unittest.TestCase):
    def test_bare_id_token(self):
        self.assertEqual(_extract_matri_id("ES92669"), "ES92669")

    def test_lowercase_bare_id_uppercased(self):
        self.assertEqual(_extract_matri_id("es92669"), "ES92669")

    def test_id_with_hint(self):
        self.assertEqual(_extract_matri_id("my id is ES92669"), "ES92669")

    def test_matrimony_hint(self):
        self.assertEqual(_extract_matri_id("my matrimony id is wp12345"), "WP12345")

    def test_marathi_aydi_hint(self):
        self.assertEqual(_extract_matri_id("माझा आयडी ES92669 आहे"), "ES92669")

    def test_hint_skips_short_words(self):
        self.assertEqual(_extract_matri_id("id is es92669"), "ES92669")

    def test_no_id_returns_none(self):
        self.assertIsNone(_extract_matri_id("show me profiles in pune"))

    def test_empty_returns_none(self):
        self.assertIsNone(_extract_matri_id("  "))

    def test_too_short_token_returns_none(self):
        self.assertIsNone(_extract_matri_id("ab"))

    def test_too_long_bare_token_returns_none(self):
        self.assertIsNone(_extract_matri_id("A" * 20))

    def test_hint_before_plain_word_ignored(self):
        self.assertIsNone(_extract_matri_id("show me profiles with id male"))

    def test_hint_before_short_word_then_id(self):
        self.assertEqual(_extract_matri_id("my id is wp12345"), "WP12345")


def _make_service():
    service = ChatService(db=AsyncMock())
    service.conv_repo = AsyncMock()
    service.msg_repo = AsyncMock()
    service.conv_repo.create = AsyncMock(return_value=MagicMock(id=99))
    service.msg_repo.create = AsyncMock(side_effect=[MagicMock(id=1), MagicMock(id=5)])
    service.conv_repo.update = AsyncMock(return_value=None)
    service.db = AsyncMock()
    service.db.commit = AsyncMock(return_value=None)
    return service


async def _fake_link_ok(db, user, matri_id):
    user.matri_id = matri_id.upper()
    user.matri_name = "Ravi Kumar"
    return {
        "member": {"name": "Ravi Kumar"},
        "filters": {},
        "summary": {},
        "saved_search_used": False,
        "saved_search_source": None,
    }


class AutoLinkTests(unittest.IsolatedAsyncioTestCase):
    async def test_links_id_and_returns_success_reply(self):
        service = _make_service()
        user = FakeUser()
        with patch(
            "app.services.chat_service.link_matri_id_to_user",
            new=AsyncMock(side_effect=_fake_link_ok),
        ):
            result = await service._try_auto_link_matri(user, "ES92669", None)

        self.assertIsNotNone(result)
        self.assertEqual(result["conversation_id"], 99)
        self.assertEqual(result["message_id"], 5)
        self.assertEqual(user.matri_id, "ES92669")
        self.assertEqual(result["reply"], MATRI_ID_SUCCESS.format(id="ES92669", name="Ravi Kumar"))

    async def test_invalid_id_returns_not_found_reply(self):
        service = _make_service()
        user = FakeUser()
        with patch(
            "app.services.chat_service.link_matri_id_to_user",
            new=AsyncMock(side_effect=MatriLinkError("No member found with this MatriID")),
        ):
            result = await service._try_auto_link_matri(user, "ES00000", None)

        self.assertIsNotNone(result)
        self.assertEqual(result["reply"], MATRI_ID_NOT_FOUND.format(id="ES00000"))

    async def test_database_error_returns_generic_reply(self):
        service = _make_service()
        user = FakeUser()
        with patch(
            "app.services.chat_service.link_matri_id_to_user",
            new=AsyncMock(side_effect=RuntimeError("connection refused")),
        ):
            result = await service._try_auto_link_matri(user, "ES92669", None)

        self.assertIsNotNone(result)
        self.assertEqual(result["reply"], MATRI_ID_ERROR)

    async def test_user_already_linked_falls_through(self):
        service = _make_service()
        user = FakeUser(matri_id="ES92669")
        result = await service._try_auto_link_matri(user, "show me profiles", None)
        self.assertIsNone(result)

    async def test_non_id_message_falls_through(self):
        service = _make_service()
        user = FakeUser()
        result = await service._try_auto_link_matri(user, "नमस्कार", None)
        self.assertIsNone(result)

    async def test_uses_existing_conversation(self):
        service = _make_service()
        service.conv_repo.get_by_id = AsyncMock(return_value=MagicMock(id=7, user_id=1))
        user = FakeUser()
        with patch(
            "app.services.chat_service.link_matri_id_to_user",
            new=AsyncMock(side_effect=_fake_link_ok),
        ):
            result = await service._try_auto_link_matri(user, "id ES92669", 7)

        self.assertEqual(result["conversation_id"], 7)
        service.conv_repo.get_by_id.assert_awaited_once_with(7)

    async def test_link_reply_prepends_profile_and_pe_summary(self):
        service = _make_service()
        user = FakeUser()

        async def _fake_link_with_summary(db, user, matri_id):
            user.matri_id = matri_id.upper()
            user.matri_name = "Ravi Kumar"
            return {
                "member": {"name": "Ravi Kumar"},
                "filters": {},
                "summary": {},
                "profile": {"Name": "Ravi Kumar", "Age": "32", "City": "Pune"},
                "pe_summary_mr": {"जोडीदाराचा धर्म": "Hindu"},
                "saved_search_used": False,
                "saved_search_source": None,
            }

        with patch(
            "app.services.chat_service.link_matri_id_to_user",
            new=AsyncMock(side_effect=_fake_link_with_summary),
        ):
            result = await service._try_auto_link_matri(user, "ES92669", None)

        self.assertIsNotNone(result)
        self.assertIn("📋 **तुमचे प्रोफाइल:**", result["reply"])
        self.assertIn("• नाव: Ravi Kumar", result["reply"])
        self.assertIn("🎯 **तुमच्या जोडीदाराच्या पसंती:**", result["reply"])
        self.assertIn("• जोडीदाराचा धर्म: Hindu", result["reply"])
        self.assertIn("यशस्वीरित्या लिंक झाला", result["reply"])

    async def test_pe_empty_starts_questionnaire_flow(self):
        service = _make_service()
        user = FakeUser()

        async def _fake_link_pe_empty(db, user, matri_id):
            user.matri_id = matri_id.upper()
            user.matri_name = "Ravi Kumar"
            return {
                "member": {"name": "Ravi Kumar"},
                "filters": {"gender": "Female"},
                "summary": {},
                "saved_search_used": False,
                "saved_search_source": None,
            }

        with patch(
            "app.services.chat_service.link_matri_id_to_user",
            new=AsyncMock(side_effect=_fake_link_pe_empty),
        ):
            result = await service._try_auto_link_matri(user, "ES92669", None)

        self.assertIsNotNone(result)
        self.assertNotEqual(result["reply"], MATRI_ID_SUCCESS.format(id="ES92669", name="Ravi Kumar"))
        self.assertIn("Ravi", result["reply"])
        self.assertIn("वयोगट", result["reply"])
        self.assertIn("प्रश्न 1/", result["reply"])
        self.assertEqual(user.matri_id, "ES92669")

    async def test_pe_present_flow_starts_at_first_missing_category(self):
        service = _make_service()
        user = FakeUser()

        async def _fake_link_pe_present(db, user, matri_id):
            user.matri_id = matri_id.upper()
            user.matri_name = "Ravi Kumar"
            return {
                "member": {"name": "Ravi Kumar"},
                "filters": {"gender": "Female", "age_min": "18", "age_max": "25"},
                "summary": {},
                "saved_search_used": False,
                "saved_search_source": None,
            }

        with patch(
            "app.services.chat_service.link_matri_id_to_user",
            new=AsyncMock(side_effect=_fake_link_pe_present),
        ):
            result = await service._try_auto_link_matri(user, "ES92669", None)

        self.assertIsNotNone(result)
        # Missing-only onboarding auto-applies the known age and asks the first
        # missing category (marital status) — no "कायम ठेवा?" confirm step.
        self.assertNotIn("कायम ठेवा", result["reply"])
        self.assertIn("वैवाहिक", result["reply"])
        self.assertIn("प्रश्न 1/", result["reply"])


if __name__ == "__main__":
    unittest.main()
