"""Tests for the profile comparison path (conversation-memory follow-ups)."""
import unittest
from unittest.mock import AsyncMock, patch
from unittest import IsolatedAsyncioTestCase

from app.services.db_query_service import (
    format_profile_comparison,
    resolve_comparison,
    handle_profile_comparison,
)


CANDIDATES = [
    {"MatriID": "M1", "Name": "Priya Patil", "City": "Pune", "Occupation": "Software Engineer"},
    {"MatriID": "M2", "Name": "Sneha Rane", "City": "Mumbai", "Occupation": "CA"},
    {"MatriID": "M3", "Name": "Aarti Joshi", "City": "Pune", "Occupation": "Doctor"},
]


class FormatProfileComparisonTests(unittest.TestCase):
    def test_side_by_side_fields(self):
        a = {"Name": "A", "Age": "28", "Gender": "Female", "Education": "BE", "City": "Pune"}
        b = {"Name": "B", "Age": "30", "Gender": "Female", "Education": "MBA", "City": "Mumbai"}
        text = format_profile_comparison(a, b)
        self.assertIn("प्रोफाइल तुलना", text)
        self.assertIn("1. A", text)
        self.assertIn("2. B", text)
        self.assertIn("वय: 28 | 30", text)
        self.assertIn("शहर: Pune | Mumbai", text)

    def test_missing_values_render_dash(self):
        a = {"Name": "A", "Age": "28"}
        b = {"Name": "B"}
        text = format_profile_comparison(a, b)
        self.assertIn("शिक्षण: — | —", text)
        self.assertIn("वय: 28 | —", text)


class ResolveComparisonTests(unittest.TestCase):
    def test_resolves_by_index_with_current_selected(self):
        pair, clarification = resolve_comparison(1, None, CANDIDATES, CANDIDATES[2])
        self.assertIsNone(clarification)
        self.assertEqual(pair[0], CANDIDATES[2])
        self.assertEqual(pair[1], CANDIDATES[0])

    def test_resolves_by_reference(self):
        pair, clarification = resolve_comparison(None, "doctor", CANDIDATES, CANDIDATES[0])
        self.assertIsNone(clarification)
        self.assertEqual(pair[0], CANDIDATES[0])
        self.assertEqual(pair[1], CANDIDATES[2])

    def test_no_candidates_returns_clarification(self):
        _, clarification = resolve_comparison(None, None, None, None)
        self.assertIsNotNone(clarification)

    def test_out_of_range_index_returns_clarification(self):
        _, clarification = resolve_comparison(99, None, CANDIDATES, CANDIDATES[0])
        self.assertIsNotNone(clarification)

    def test_multiple_matches_returns_clarification(self):
        _, clarification = resolve_comparison(None, "pune", CANDIDATES, CANDIDATES[0])
        self.assertIsNotNone(clarification)

    def test_same_profile_returns_clarification(self):
        pair, clarification = resolve_comparison(1, None, CANDIDATES, CANDIDATES[0])
        self.assertIsNotNone(clarification)
        self.assertIsNone(pair)

    def test_defaults_first_to_most_recent(self):
        pair, clarification = resolve_comparison(2, None, CANDIDATES, CANDIDATES[0])
        self.assertIsNone(clarification)
        self.assertEqual(pair[0], CANDIDATES[0])
        self.assertEqual(pair[1], CANDIDATES[1])


class HandleProfileComparisonTests(IsolatedAsyncioTestCase):
    async def test_returns_clarification_when_unresolvable(self):
        result = await handle_profile_comparison(
            "compare them", None, None, [], None, None, None
        )
        self.assertIn("content", result)
        self.assertTrue(result["content"])
        self.assertFalse(result["is_profile_search"])

    async def test_fetches_and_formats_both_profiles(self):
        rows_by_sql = {
            "M1": {"MatriID": "M1", "Name": "Priya Patil", "Age": "28", "City": "Pune"},
            "M2": {"MatriID": "M2", "Name": "Sneha Rane", "Age": "30", "City": "Mumbai"},
        }

        async def fake_execute(sql, params):
            matri_id = params[0] if params else None
            if matri_id in rows_by_sql:
                return {"sql": sql, "rows": [rows_by_sql[matri_id]], "row_count": 1}
            return {"sql": sql, "rows": [], "row_count": 0}

        with patch("app.services.db_query_service.execute_param_query", new=fake_execute):
            result = await handle_profile_comparison(
                "compare her with the first profile",
                1, None, [], None, CANDIDATES, CANDIDATES[1],
            )
        self.assertIn("प्रोफाइल तुलना", result["content"])
        self.assertIn("Priya Patil", result["content"])
        self.assertIn("Sneha Rane", result["content"])
        self.assertIn("वय: 30 | 28", result["content"])
        self.assertEqual(result["metadata"]["selected_profile"], CANDIDATES[0])


if __name__ == "__main__":
    unittest.main()
