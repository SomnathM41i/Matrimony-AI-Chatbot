import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.extraction_service import (
    clean_json,
    validate_filters,
    validate_fields,
    is_likely_profile_message,
    _is_detail_query,
    _keyword_fallback,
    extract_search_params,
    DEFAULT_FILTERS,
)


class CleanJsonTests(unittest.TestCase):
    def test_strips_markdown_code_fence(self):
        result = clean_json("```json\n{\"key\": \"value\"}\n```")
        self.assertEqual(result, "{\"key\": \"value\"}")

    def test_strips_code_fence_without_json(self):
        result = clean_json("```\n{\"key\": \"value\"}\n```")
        self.assertEqual(result, "{\"key\": \"value\"}")

    def test_extracts_first_json_object(self):
        result = clean_json("text before {\"a\": 1} text after")
        self.assertEqual(result, "{\"a\": 1}")

    def test_returns_raw_text_if_no_braces(self):
        result = clean_json("plain text")
        self.assertEqual(result, "plain text")

    def test_handles_nested_braces(self):
        result = clean_json('{"outer": {"inner": "value"}}')
        self.assertEqual(result, '{"outer": {"inner": "value"}}')

    def test_handles_empty_input(self):
        self.assertEqual(clean_json(""), "")
        self.assertEqual(clean_json(None), "")


class ValidateFiltersTests(unittest.TestCase):
    def test_keeps_valid_string_filters(self):
        result = validate_filters({"gender": "Female", "caste": "Maratha"})
        self.assertEqual(result["gender"], "Female")
        self.assertEqual(result["caste"], "Maratha")

    def test_keeps_numeric_filters(self):
        result = validate_filters({"age_min": 21, "age_max": 35})
        self.assertEqual(result["age_min"], 21)
        self.assertEqual(result["age_max"], 35)

    def test_strips_whitespace(self):
        result = validate_filters({"gender": "  Male  "})
        self.assertEqual(result["gender"], "Male")

    def test_converts_empty_string_to_none(self):
        result = validate_filters({"gender": ""})
        self.assertIsNone(result["gender"])

    def test_drops_unknown_keys(self):
        result = validate_filters({"unknown_key": "value"})
        self.assertNotIn("unknown_key", result)

    def test_all_default_keys_present(self):
        result = validate_filters({})
        for key in DEFAULT_FILTERS:
            self.assertIn(key, result)

    def test_non_string_non_numeric_sets_none(self):
        result = validate_filters({"gender": ["list"]})
        self.assertIsNone(result["gender"])


class ValidateFieldsTests(unittest.TestCase):
    def test_valid_field_names(self):
        result = validate_fields(["education", "family", "income"])
        self.assertEqual(result, ["education", "family", "income"])

    def test_case_insensitive(self):
        result = validate_fields(["EDUCATION", "Family"])
        self.assertEqual(result, ["education", "family"])

    def test_mixed_valid_and_invalid(self):
        result = validate_fields(["education", "nonexistent"])
        self.assertEqual(result, ["education"])

    def test_all_invalid_returns_none(self):
        result = validate_fields(["foo", "bar"])
        self.assertIsNone(result)

    def test_empty_list_returns_none(self):
        result = validate_fields([])
        self.assertIsNone(result)

    def test_none_returns_none(self):
        result = validate_fields(None)
        self.assertIsNone(result)


class IsLikelyProfileMessageTests(unittest.TestCase):
    def test_profile_keyword(self):
        self.assertTrue(is_likely_profile_message("show profiles"))

    def test_community_keyword(self):
        self.assertTrue(is_likely_profile_message("maratha brides"))

    def test_search_verb(self):
        self.assertTrue(is_likely_profile_message("looking for a match"))

    def test_detail_keyword(self):
        self.assertTrue(is_likely_profile_message("tell me about her"))

    def test_general_message_false(self):
        self.assertFalse(is_likely_profile_message("how are you"))

    def test_empty_message_false(self):
        self.assertFalse(is_likely_profile_message(""))

    def test_marathi_profile_keyword(self):
        self.assertTrue(is_likely_profile_message("प्रोफाइल दाखवा"))

    def test_hinglish_search(self):
        self.assertTrue(is_likely_profile_message("mujhe ladki dikhao"))


class IsDetailQueryTests(unittest.TestCase):
    def test_single_pronoun(self):
        self.assertTrue(_is_detail_query("her"))

    def test_pronoun_sentence(self):
        self.assertTrue(_is_detail_query("tell me about her"))

    def test_positional_reference(self):
        self.assertTrue(_is_detail_query("show first profile"))

    def test_detail_keyword_education(self):
        self.assertTrue(_is_detail_query("what is her education"))

    def test_detail_keyword_family(self):
        self.assertTrue(_is_detail_query("tell me about family"))

    def test_general_query_false(self):
        self.assertFalse(_is_detail_query("show me maratha girls"))

    def test_detail_keyword_income(self):
        self.assertTrue(_is_detail_query("her income"))

    def test_detail_keyword_manglik(self):
        self.assertTrue(_is_detail_query("is she manglik"))

    def test_marathi_detail(self):
        self.assertTrue(_is_detail_query("तिचे शिक्षण काय आहे"))

    def test_hinglish_detail(self):
        self.assertTrue(_is_detail_query("uski kundali dikhao"))


class KeywordFallbackTests(unittest.TestCase):
    def test_female_detected(self):
        result = _keyword_fallback("I want a girl")
        self.assertEqual(result.get("gender"), "Female")

    def test_male_detected(self):
        result = _keyword_fallback("looking for a boy")
        self.assertEqual(result.get("gender"), "Male")

    def test_marathi_female(self):
        result = _keyword_fallback("मुलगी हवी")
        self.assertEqual(result.get("gender"), "Female")

    def test_caste_detected(self):
        result = _keyword_fallback("maratha bride")
        self.assertEqual(result.get("caste"), "Maratha")

    def test_city_detected(self):
        result = _keyword_fallback("profiles in Pune")
        self.assertEqual(result.get("city"), "Pune")

    def test_marathi_city_captures_before_madhy(self):
        result = _keyword_fallback("पुणे मध्ये मुलगी")
        self.assertEqual(result.get("city"), "पुणे")
        self.assertEqual(result.get("gender"), "Female")

    def test_no_filters_for_irrelevant(self):
        result = _keyword_fallback("hello world")
        self.assertEqual(result, {})


class ExtractSearchParamsTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_profile_message_returns_general(self):
        result = await extract_search_params("what is 2+2")
        self.assertEqual(result["intent"], "general")
        self.assertEqual(result["filters"], {})

    async def test_llm_failure_falls_back_to_keyword(self):
        with patch("app.services.extraction_service.call_groq", new=AsyncMock(side_effect=RuntimeError("API down"))):
            result = await extract_search_params("show maratha girls")
            self.assertEqual(result["intent"], "profile_search")
            self.assertIn("filters", result)

    async def test_llm_failure_detail_falls_back_correctly(self):
        with patch("app.services.extraction_service.call_groq", new=AsyncMock(side_effect=RuntimeError("API down"))):
            result = await extract_search_params("tell me about her")
            self.assertEqual(result["intent"], "profile_detail")

    async def test_successful_extraction_profile_search(self):
        mock_response = {
            "content": '{"intent": "profile_search", "filters": {"gender": "Female", "caste": "Maratha"}, "limit": 10}'
        }
        with patch("app.services.extraction_service.call_groq", new=AsyncMock(return_value=mock_response)):
            result = await extract_search_params("show maratha girls")
            self.assertEqual(result["intent"], "profile_search")
            self.assertEqual(result["filters"]["gender"], "Female")
            self.assertEqual(result["filters"]["caste"], "Maratha")

    async def test_successful_extraction_profile_detail(self):
        mock_response = {
            "content": '{"intent": "profile_detail", "filters": {}, "fields": ["education"], "limit": 1}'
        }
        with patch("app.services.extraction_service.call_groq", new=AsyncMock(return_value=mock_response)):
            result = await extract_search_params("her education")
            self.assertEqual(result["intent"], "profile_detail")
            self.assertEqual(result["fields"], ["education"])

    async def test_limit_capped_at_50(self):
        mock_response = {
            "content": '{"intent": "profile_search", "filters": {}, "limit": 999}'
        }
        with patch("app.services.extraction_service.call_groq", new=AsyncMock(return_value=mock_response)):
            result = await extract_search_params("show profiles")
            self.assertEqual(result["limit"], 50)

    async def test_limit_minimum_1(self):
        mock_response = {
            "content": '{"intent": "profile_search", "filters": {}, "limit": 0}'
        }
        with patch("app.services.extraction_service.call_groq", new=AsyncMock(return_value=mock_response)):
            result = await extract_search_params("show profiles")
            self.assertEqual(result["limit"], 10)

    async def test_detail_query_during_llm_failure(self):
        with patch("app.services.extraction_service.call_groq", new=AsyncMock(side_effect=RuntimeError("fail"))):
            result = await extract_search_params("her")
            self.assertEqual(result["intent"], "profile_detail")


if __name__ == "__main__":
    unittest.main()
