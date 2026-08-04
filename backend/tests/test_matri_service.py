"""Unit tests for MatriID linking and partner-expectation extraction.

execute_param_query is mocked so the suite never touches the live
matrimony MySQL database.
"""
import unittest
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.services.matri_service import (
    MatriLinkError,
    _clean,
    _extract_pe_filters,
    _extract_pe_summary,
    _extract_pe_summary_mr,
    _extract_profile_summary,
    _merge_saved_search,
    _partner_gender,
    fetch_partner_expectations,
    format_user_profile_summary,
    link_matri_id,
    normalize_matri_id,
)

REGISTER_ROW = {
    "MatriID": "WP88076",
    "Name": "Ravi Kumar",
    "Gender": "Male",
    "Age": "32",
    "Photo1": "/uploads/photo1.jpg",
    "PE_FromAge": "21",
    "PE_ToAge": "28",
    "PE_Complexion": "Fair",
    "PE_MotherTongue": "Hindi",
    "PE_Religion": "Hindu",
    "PE_Caste": "Brahmin",
    "PE_subcaste": "",
    "PE_Education": "Graduate",
    "PE_Occupation": "Engineer",
    "PE_Countrylivingin": "India",
    "PE_Residentstatus": "Citizen",
    "PE_State": "Maharashtra",
    "PE_City": "Pune",
    "PE_income_from": "500000",
    "PE_income_to": "1000000",
    "PE_HaveChildren": "",
    "PE_from_Height": None,
    "PE_to_Height": None,
    "PE_Height2": None,
    "PartnerExpectations": "Looking for a fair, educated girl.",
}

NO_REGISTER = {"rows": []}


class NormalizeTests(unittest.TestCase):
    def test_uppercases_and_strips(self):
        self.assertEqual(normalize_matri_id("  wp12345  "), "WP12345")

    def test_requires_value(self):
        with self.assertRaises(MatriLinkError):
            normalize_matri_id("")

    def test_rejects_too_long(self):
        with self.assertRaises(MatriLinkError):
            normalize_matri_id("A" * 16)

    def test_rejects_special_characters(self):
        with self.assertRaises(MatriLinkError):
            normalize_matri_id("WP-12345")


class ExtractionTests(unittest.TestCase):
    def test_partner_gender_is_inverted(self):
        self.assertEqual(_partner_gender("Male"), "Female")
        self.assertEqual(_partner_gender("female"), "Male")
        self.assertIsNone(_partner_gender(None))
        self.assertIsNone(_partner_gender("Other"))

    def test_clean_blank_values_to_none(self):
        self.assertIsNone(_clean(""))
        self.assertIsNone(_clean("  ANY  "))
        self.assertIsNone(_clean("Not Applicable"))
        self.assertEqual(_clean("  Fair  "), "Fair")
        self.assertIsNone(_clean(None))

    def test_extract_pe_filters_maps_columns_and_derives_gender(self):
        filters = _extract_pe_filters(REGISTER_ROW)
        self.assertEqual(filters["gender"], "Female")
        self.assertEqual(filters["age_min"], "21")
        self.assertEqual(filters["age_max"], "28")
        self.assertEqual(filters["complexion"], "Fair")
        self.assertEqual(filters["religion"], "Hindu")
        self.assertEqual(filters["caste"], "Brahmin")
        self.assertEqual(filters["city"], "Pune")
        self.assertNotIn("subcaste", filters)

    def test_extract_pe_summary_skips_empty_values(self):
        summary = _extract_pe_summary(REGISTER_ROW)
        self.assertEqual(summary["Religion"], "Hindu")
        self.assertNotIn("Accepted Children", summary)

    def test_extract_pe_summary_mr_uses_marathi_labels(self):
        pe_mr = _extract_pe_summary_mr(REGISTER_ROW)
        self.assertEqual(pe_mr["जोडीदाराचा धर्म"], "Hindu")
        self.assertEqual(pe_mr["जोडीदाराची जात"], "Brahmin")
        self.assertEqual(pe_mr["जोडीदाराचे किमान वय"], "21")
        self.assertNotIn("मुले स्वीकार्य", pe_mr)

    def test_extract_profile_summary_keeps_only_populated_fields(self):
        profile = _extract_profile_summary(REGISTER_ROW)
        self.assertEqual(profile["Name"], "Ravi Kumar")
        self.assertEqual(profile["Age"], "32")
        self.assertNotIn("City", profile)

    def test_format_user_profile_summary_sections(self):
        text = format_user_profile_summary(
            {"Name": "Ravi Kumar", "Age": "32", "City": "Pune"},
            {"जोडीदाराचा धर्म": "Hindu", "जोडीदाराचे शहर": "Pune"},
        )
        self.assertIn("📋 **तुमचे प्रोफाइल:**", text)
        self.assertIn("• नाव: Ravi Kumar", text)
        self.assertIn("• वय: 32", text)
        self.assertIn("🎯 **तुमच्या जोडीदाराच्या पसंती:**", text)
        self.assertIn("• जोडीदाराचा धर्म: Hindu", text)

    def test_format_user_profile_summary_empty_returns_empty(self):
        self.assertEqual(format_user_profile_summary({}), "")
        self.assertEqual(
            format_user_profile_summary({"Name": ""}, {"जोडीदाराचा धर्म": "any"}),
            "",
        )

    def test_merge_saved_search_fills_gaps_but_does_not_override(self):
        filters = {"religion": "Hindu", "city": "Pune"}
        saved = {
            "source": "advance_saveandsearch",
            "maritialstatus": "Unmarried",
            "religion": "Muslim",
            "fromage": "21",
            "toage": "28",
        }
        merged = _merge_saved_search(filters, saved)
        self.assertEqual(merged["religion"], "Hindu")
        self.assertEqual(merged["marital_status"], "Unmarried")
        self.assertEqual(merged["age_min"], "21")

    def test_merge_saved_search_handles_basic_table_column_name(self):
        saved = {"source": "basic_saveandsearch", "Maritial_status": "Divorced"}
        merged = _merge_saved_search({}, saved)
        self.assertEqual(merged["marital_status"], "Divorced")


class FetchPartnerExpectationsTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_member_raises_link_error(self):
        with patch(
            "app.services.matri_service.execute_param_query",
            new=AsyncMock(return_value=NO_REGISTER),
        ):
            with self.assertRaises(MatriLinkError):
                await fetch_partner_expectations("WP00000")

    async def test_register_only_fetch(self):
        async def fake_query(sql, params):
            if "FROM register" in sql:
                return {"rows": [REGISTER_ROW]}
            return {"rows": []}

        with patch(
            "app.services.matri_service.execute_param_query",
            new=AsyncMock(side_effect=fake_query),
        ):
            result = await fetch_partner_expectations("WP88076")

        self.assertEqual(result["member"]["name"], "Ravi Kumar")
        self.assertEqual(
            result["member"]["photo_url"],
            settings.PHOTO_BASE_URL.rstrip("/") + "/uploads/photo1.jpg",
        )
        self.assertEqual(result["filters"]["gender"], "Female")
        self.assertFalse(result["saved_search_used"])
        self.assertIsNone(result["saved_search_source"])
        self.assertEqual(result["summary"]["Religion"], "Hindu")
        self.assertEqual(result["profile"]["Name"], "Ravi Kumar")
        self.assertEqual(result["pe_summary_mr"]["जोडीदाराचा धर्म"], "Hindu")

    async def test_saved_search_fills_gaps_and_reports_source(self):
        async def fake_query(sql, params):
            if "FROM register" in sql:
                row = dict(REGISTER_ROW)
                row["PE_Religion"] = None
                return {"rows": [row]}
            if "advance_saveandsearch" in sql:
                return {"rows": [{"source": "advance_saveandsearch", "maritialstatus": "Unmarried"}]}
            return {"rows": []}

        with patch(
            "app.services.matri_service.execute_param_query",
            new=AsyncMock(side_effect=fake_query),
        ):
            result = await fetch_partner_expectations("WP88076")

        self.assertTrue(result["saved_search_used"])
        self.assertEqual(result["saved_search_source"], "advance_saveandsearch")
        self.assertEqual(result["filters"]["marital_status"], "Unmarried")
        self.assertNotIn("religion", result["filters"])

    async def test_advance_table_checked_before_basic(self):
        queries = []

        async def fake_query(sql, params):
            queries.append(sql)
            if "FROM register" in sql:
                row = dict(REGISTER_ROW)
                row["PE_Religion"] = None
                return {"rows": [row]}
            if "advance_saveandsearch" in sql:
                return {"rows": [{"source": "advance_saveandsearch"}]}
            return {"rows": []}

        with patch(
            "app.services.matri_service.execute_param_query",
            new=AsyncMock(side_effect=fake_query),
        ):
            result = await fetch_partner_expectations("WP88076")

        self.assertTrue(result["saved_search_used"])
        self.assertEqual(result["saved_search_source"], "advance_saveandsearch")
        self.assertEqual(sum("advance_saveandsearch" in q for q in queries), 1)
        self.assertEqual(sum("basic_saveandsearch" in q for q in queries), 0)

    async def test_link_matri_id_normalizes_and_fetches(self):
        async def fake_query(sql, params):
            return {"rows": [REGISTER_ROW]}

        with patch(
            "app.services.matri_service.execute_param_query",
            new=AsyncMock(side_effect=fake_query),
        ):
            result = await link_matri_id("  wp88076  ")
        self.assertEqual(result["member"]["matri_id"], "WP88076")


if __name__ == "__main__":
    unittest.main()
