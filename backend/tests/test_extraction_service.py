import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.extraction_service import (
    clean_json,
    validate_filters,
    validate_fields,
    is_likely_profile_message,
    _is_detail_query,
    _keyword_fallback,
    _normalize_intent,
    extract_search_params,
    DEFAULT_FILTERS,
    VALID_INTENTS,
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
        mock_response = {
            "content": '{"intent": "general", "filters": {}, "limit": 10}'
        }
        with patch("app.services.extraction_service.call_groq", new=AsyncMock(return_value=mock_response)):
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
        # "show maratha girls" is now answered by the deterministic fast path,
        # so use a vague message that still needs the LLM.
        with patch("app.services.extraction_service.call_groq", new=AsyncMock(return_value=mock_response)):
            result = await extract_search_params("show me profiles please")
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


class IntentClassificationTests(unittest.IsolatedAsyncioTestCase):
    """Intent classification across the explicit intent vocabulary.

    The LLM response and the TF-IDF router are mocked (and the deterministic
    rule-based fast path is bypassed) so the parse-and-normalize pipeline is
    exercised deterministically regardless of language or script."""

    def _llm(self, payload: str):
        return patch(
            "app.services.extraction_service.call_groq",
            new=AsyncMock(return_value={"content": payload}),
        )

    def _router(self):
        return patch(
            "app.services.extraction_service.router.route",
            new=MagicMock(return_value=("database", 0.0)),
        )

    def _no_rules(self):
        return patch(
            "app.services.extraction_service.rule_based_extract",
            new=MagicMock(return_value=None),
        )

    async def _classify(self, message: str, payload: str) -> dict:
        with self._router(), self._no_rules(), self._llm(payload):
            return await extract_search_params(message)

    async def test_intent_vocabulary_covered(self):
        self.assertEqual(
            VALID_INTENTS,
            {
                "profile_search", "profile_detail", "comparison", "biodata",
                "membership", "greeting", "follow_up", "general", "admin",
            },
        )

    async def test_biodata_routes_to_profile_detail(self):
        result = await self._classify(
            "show me her biodata",
            '{"intent": "biodata", "fields": ["all"]}',
        )
        self.assertEqual(result["intent"], "profile_detail")
        self.assertEqual(result["intent_label"], "biodata")
        self.assertEqual(result["fields"], ["all"])

    async def test_comparison_kept_as_label_routes_general(self):
        result = await self._classify(
            "compare her with the first profile",
            '{"intent": "comparison", "selected_index": 1}',
        )
        self.assertEqual(result["intent"], "general")
        self.assertEqual(result["intent_label"], "comparison")
        self.assertEqual(result["selected_index"], 1)

    async def test_follow_up_with_index_routes_to_detail(self):
        result = await self._classify(
            "what about the second one",
            '{"intent": "follow_up", "selected_index": 2}',
        )
        self.assertEqual(result["intent"], "profile_detail")
        self.assertEqual(result["intent_label"], "follow_up")
        self.assertEqual(result["selected_index"], 2)

    async def test_follow_up_without_reference_routes_general(self):
        result = await self._classify(
            "and the next one",
            '{"intent": "follow_up"}',
        )
        self.assertEqual(result["intent"], "general")
        self.assertEqual(result["intent_label"], "follow_up")

    async def test_membership_label(self):
        result = await self._classify(
            "what are your membership plans",
            '{"intent": "membership"}',
        )
        self.assertEqual(result["intent"], "general")
        self.assertEqual(result["intent_label"], "membership")

    async def test_admin_label(self):
        result = await self._classify(
            "how can I contact the site admin",
            '{"intent": "admin"}',
        )
        self.assertEqual(result["intent"], "general")
        self.assertEqual(result["intent_label"], "admin")

    async def test_greeting_label(self):
        result = await self._classify(
            "hello there",
            '{"intent": "greeting"}',
        )
        self.assertEqual(result["intent"], "general")
        self.assertEqual(result["intent_label"], "greeting")

    async def test_unknown_intent_defaults_general(self):
        result = await self._classify(
            "whatever this is",
            '{"intent": "stats"}',
        )
        self.assertEqual(result["intent"], "general")
        self.assertEqual(result["intent_label"], "general")

    async def test_normalize_intent_mapping(self):
        self.assertEqual(_normalize_intent("profile_search", {}), "profile_search")
        self.assertEqual(_normalize_intent("profile_detail", {}), "profile_detail")
        self.assertEqual(_normalize_intent("biodata", {}), "profile_detail")
        self.assertEqual(_normalize_intent("follow_up", {"selected_index": 3}), "profile_detail")
        self.assertEqual(_normalize_intent("follow_up", {}), "general")
        self.assertEqual(_normalize_intent("comparison", {}), "general")
        self.assertEqual(_normalize_intent("membership", {}), "general")
        self.assertEqual(_normalize_intent("greeting", {}), "general")
        self.assertEqual(_normalize_intent("admin", {}), "general")
        self.assertEqual(_normalize_intent("general", {}), "general")

    # --- Multilingual / multi-script LLM classification -------------------

    async def test_marathi_profile_search(self):
        result = await self._classify(
            "मला पुण्यातील 5 माळी मुली दाखवा",
            '{"intent": "profile_search", "filters": {"gender": "Female", "city": "Pune", "caste": "Mali"}, "limit": 5}',
        )
        self.assertEqual(result["intent"], "profile_search")
        self.assertEqual(result["filters"]["gender"], "Female")
        self.assertEqual(result["filters"]["caste"], "Mali")
        self.assertEqual(result["filters"]["city"], "Pune")
        self.assertEqual(result["limit"], 5)

    async def test_hindi_profile_search(self):
        result = await self._classify(
            "मुझे मुंबई में लड़की चाहिए",
            '{"intent": "profile_search", "filters": {"gender": "Female", "city": "Mumbai"}, "limit": 10}',
        )
        self.assertEqual(result["intent"], "profile_search")
        self.assertEqual(result["filters"]["gender"], "Female")
        self.assertEqual(result["filters"]["city"], "Mumbai")

    async def test_hinglish_profile_detail(self):
        result = await self._classify(
            "uska education kya hai",
            '{"intent": "profile_detail", "fields": ["education"], "limit": 1}',
        )
        self.assertEqual(result["intent"], "profile_detail")
        self.assertEqual(result["fields"], ["education"])
        self.assertEqual(result["limit"], 1)

    async def test_mixed_language_follow_up(self):
        result = await self._classify(
            "तिसरी वाली कोण आहे",
            '{"intent": "follow_up", "selected_index": 3}',
        )
        self.assertEqual(result["intent"], "profile_detail")
        self.assertEqual(result["selected_index"], 3)

    async def test_marathi_greeting_fast_path(self):
        # Exact-match fast path: no LLM call, intent stays general.
        with patch("app.services.extraction_service.call_groq", new=AsyncMock()) as mock:
            result = await extract_search_params("नमस्कार")
            mock.assert_not_awaited()
        self.assertEqual(result["intent"], "general")

    async def test_nri_filter_kept_by_validation(self):
        result = await self._classify(
            "show me NRI boys",
            '{"intent": "profile_search", "filters": {"gender": "Male", "nri": true}, "limit": 10}',
        )
        self.assertEqual(result["intent"], "profile_search")
        self.assertEqual(result["filters"]["gender"], "Male")
        self.assertTrue(result["filters"]["nri"])

    async def test_divorced_filter_kept_by_validation(self):
        result = await self._classify(
            "show divorced girls",
            '{"intent": "profile_search", "filters": {"gender": "Female", "marital_status": "Divorced"}, "limit": 10}',
        )
        self.assertEqual(result["intent"], "profile_search")
        self.assertEqual(result["filters"]["marital_status"], "Divorced")

    async def test_country_filter_kept_by_validation(self):
        result = await self._classify(
            "find girls settled in usa",
            '{"intent": "profile_search", "filters": {"gender": "Female", "country": "USA"}, "limit": 10}',
        )
        self.assertEqual(result["filters"]["country"], "USA")


if __name__ == "__main__":
    unittest.main()
