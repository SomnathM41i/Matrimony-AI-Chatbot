"""Unit tests for helpers in db_query_service.py that need no database."""
import unittest

from app.services.db_query_service import merge_filters


class MergeFiltersTests(unittest.TestCase):
    def test_merges_two_dicts(self):
        merged = merge_filters({"gender": "Female"}, {"city": "Pune"})
        self.assertEqual(merged, {"gender": "Female", "city": "Pune"})

    def test_new_values_override_accumulated(self):
        merged = merge_filters({"city": "Pune"}, {"city": "Mumbai"})
        self.assertEqual(merged, {"city": "Mumbai"})

    def test_none_values_do_not_override(self):
        merged = merge_filters({"city": "Pune"}, {"city": None, "gender": "Female"})
        self.assertEqual(merged, {"city": "Pune", "gender": "Female"})

    def test_accumulated_none_is_safe(self):
        merged = merge_filters(None, {"gender": "Female"})
        self.assertEqual(merged, {"gender": "Female"})

    def test_new_filters_none_is_safe(self):
        merged = merge_filters({"gender": "Female"}, None)
        self.assertEqual(merged, {"gender": "Female"})

    def test_both_none_is_safe(self):
        merged = merge_filters(None, None)
        self.assertEqual(merged, {})

    def test_empty_new_filters_preserves_accumulated(self):
        merged = merge_filters({"gender": "Female"}, {})
        self.assertEqual(merged, {"gender": "Female"})


if __name__ == "__main__":
    unittest.main()
