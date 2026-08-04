"""Unit tests for the CF-6 chat-embedded rich biodata.

Covers:
- format_profile_biodata(row) — zero-LLM sectioned Marathi biodata (header +
  photo + non-empty sections in order).
- format_profile_section(row, key) — single-section drill-down.
- BIODATA_SECTION_ROUTES / chips — every section chip routes deterministically
  to its section on the currently viewed profile (no LLM).
- Stream: a full biodata request renders deterministically with section chips in
  the done event; a section-chip click renders only that section and skips the
  LLM extraction + formatting.
"""
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_service import SUGGESTION_ROUTES, ChatService
from app.services.matri_service import (
    BIODATA_SECTION_CHIPS,
    BIODATA_SECTION_ROUTES,
    format_profile_biodata,
    format_profile_section,
)


class FakeUser:
    def __init__(self, matri_id="ES92669", matri_name="Ravi Kumar", name="Ravi"):
        self.id = 1
        self.matri_id = matri_id
        self.matri_name = matri_name
        self.name = name


ROW = {
    "MatriID": "P1",
    "Name": "Anita",
    "Age": "27",
    "Maritalstatus": "Unmarried",
    "Height": "5'4\"",
    "Education": "BE",
    "Occupation": "Engineer",
    "Employedin": "Private",
    "Annualincome": "6 LPA",
    "City": "Pune",
    "State": "Maharashtra",
    "Diet": "Veg",
    "Photo1": "anita.jpg",
    "PE_FromAge": "28",
    "PE_ToAge": "34",
    "PE_Religion": "Hindu",
}


class FormatBiodataTests(unittest.TestCase):
    def test_renders_header_and_photo(self):
        out = format_profile_biodata(ROW)
        self.assertIn("👤 **Anita** · P1", out)
        self.assertIn("![Anita](https://dishavadhuvar.in/gallary/anita.jpg)", out)

    def test_renders_sections_in_order_with_marathi_labels(self):
        out = format_profile_biodata(ROW)
        self.assertLess(out.index("📚 **शिक्षण व करिअर:**"), out.index("📍 **स्थान:**"))
        self.assertIn("• शिक्षण: BE", out)
        self.assertIn("• व्यवसाय: Engineer", out)
        self.assertIn("• जोडीदाराचा धर्म: Hindu", out)

    def test_empty_row_renders_only_header(self):
        out = format_profile_biodata({"MatriID": "P1", "Name": "Anita"})
        self.assertEqual(out, "👤 **Anita** · P1")

    def test_section_chips_exist_for_every_section(self):
        self.assertEqual(len(BIODATA_SECTION_CHIPS), len(BIODATA_SECTION_ROUTES))
        for chip in BIODATA_SECTION_CHIPS:
            self.assertIn(chip, BIODATA_SECTION_ROUTES)

    def test_section_returns_only_that_section(self):
        out = format_profile_section(ROW, "education")
        self.assertIsNotNone(out)
        self.assertIn("📚 **शिक्षण व करिअर:**", out)
        self.assertNotIn("मूलभूत", out)

    def test_section_none_for_unknown_or_empty(self):
        self.assertIsNone(format_profile_section(ROW, "nope"))
        self.assertIsNone(format_profile_section({"Name": "X"}, "horoscope"))

    def test_section_routes_use_current_selected_profile(self):
        for chip, section_key in BIODATA_SECTION_ROUTES.items():
            route = SUGGESTION_ROUTES[chip]
            self.assertEqual(route["intent"], "profile_detail")
            self.assertEqual(route["biodata_section"], section_key)
            self.assertIsNone(route["selected_index"])
            self.assertIsNone(route["selected_reference"])


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


class BiodataStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_biodata_streams_deterministically_with_section_chips(self):
        service = _make_stream_service()
        user = FakeUser()
        service.db.merge = AsyncMock(return_value=user)

        with patch.object(
            service, "_load_history",
            new=AsyncMock(return_value=([], {
                "selected_profile": {"MatriID": "P1", "Name": "Anita"},
                "profile_candidates": [],
            })),
        ), patch(
            "app.services.extraction_service.extract_search_params",
            new=AsyncMock(return_value={
                "intent": "profile_detail", "intent_label": "biodata",
                "fields": ["all"], "limit": 1,
            }),
        ), patch(
            "app.services.query_builder.build_detail_query",
            return_value=("SELECT 1", ()),
        ), patch(
            "app.services.db_query_service.execute_param_query",
            new=AsyncMock(return_value={"sql": "mock", "rows": [dict(ROW)], "row_count": 1}),
        ), patch(
            "app.services.llm_service.stream_format_db_result",
            new=AsyncMock(side_effect=AssertionError("biodata must not use the LLM formatter")),
        ), patch.object(
            service, "_load_user_preferences", new=AsyncMock(return_value={})
        ):
            events = []
            async for chunk in service.stream_process_message(
                1, "Anita चे बायोडाटा दाखवा", None, user=user
            ):
                events.append(chunk)

        done = json.loads(events[-1][len("data: "):])
        self.assertEqual(done["type"], "done")
        self.assertEqual(done["suggestions"], BIODATA_SECTION_CHIPS)
        reply = "".join(
            json.loads(e[len("data: "):]).get("content") or ""
            for e in events if e.startswith("data: ")
        )
        self.assertIn("👤 **Anita** · P1", reply)
        self.assertIn("📚 **शिक्षण व करिअर:**", reply)

    async def test_section_chip_click_renders_only_that_section(self):
        service = _make_stream_service()
        user = FakeUser()
        service.db.merge = AsyncMock(return_value=user)

        with patch.object(
            service, "_load_history",
            new=AsyncMock(return_value=([], {
                "selected_profile": {"MatriID": "P1", "Name": "Anita"},
                "profile_candidates": [{"MatriID": "P1", "Name": "Anita"}],
            })),
        ), patch(
            "app.services.extraction_service.extract_search_params",
            new=AsyncMock(side_effect=AssertionError("section chip must skip LLM extraction")),
        ), patch(
            "app.services.query_builder.build_detail_query",
            return_value=("SELECT 1", ()),
        ), patch(
            "app.services.db_query_service.execute_param_query",
            new=AsyncMock(return_value={"sql": "mock", "rows": [dict(ROW)], "row_count": 1}),
        ), patch(
            "app.services.llm_service.stream_format_db_result",
            new=AsyncMock(side_effect=AssertionError("section chip must not use the LLM formatter")),
        ), patch.object(
            service, "_load_user_preferences", new=AsyncMock(return_value={})
        ):
            events = []
            async for chunk in service.stream_process_message(
                1, "📚 शिक्षण व करिअर", None, user=user
            ):
                events.append(chunk)

        done = json.loads(events[-1][len("data: "):])
        self.assertEqual(done["type"], "done")
        self.assertEqual(done["suggestions"], BIODATA_SECTION_CHIPS)
        reply = "".join(
            json.loads(e[len("data: "):]).get("content") or ""
            for e in events if e.startswith("data: ")
        )
        self.assertIn("📚 **शिक्षण व करिअर:**", reply)
        self.assertIn("• शिक्षण: BE", reply)
        self.assertNotIn("मूलभूत माहिती", reply)


if __name__ == "__main__":
    unittest.main()
