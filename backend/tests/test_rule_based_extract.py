"""Unit tests for the deterministic rule-based profile-search fast path.

These guard against clear Marathi/English profile queries (like
"पुण्यातील 5 मुलींची प्रोफाइल दाखवा") being routed to the slow LLM path,
and ensure vague/detail/greeting messages still fall through to the LLM.
"""
import unittest
from unittest.mock import patch

from app.services.extraction_service import rule_based_extract


@patch("app.services.schema_discovery.get_all_cities", return_value=["Pune", "Mumbai", "Kolhapur", "Satara", "Nashik"])
@patch("app.services.schema_discovery.get_all_castes", return_value=["Maratha", "Brahmin", "Kunbi", "Mali"])
class RuleBasedExtractTests(unittest.TestCase):
    def test_pune_five_girls_profiles(self, *_mocks):
        result = rule_based_extract("पुण्यातील 5 मुलींची प्रोफाइल दाखवा")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "profile_search")
        self.assertTrue(result["deterministic"])
        self.assertEqual(result["filters"]["gender"], "Female")
        self.assertEqual(result["filters"]["city"], "Pune")
        self.assertEqual(result["limit"], 5)

    def test_pune_girls_no_count(self, *_mocks):
        result = rule_based_extract("पुण्यातील मुली दाखवा")
        self.assertIsNotNone(result)
        self.assertEqual(result["filters"]["city"], "Pune")
        self.assertEqual(result["limit"], 10)

    def test_age_range_female(self, *_mocks):
        result = rule_based_extract("मला 26 ते 30 वर्षांची मुलगी हवी आहे")
        self.assertIsNotNone(result)
        self.assertEqual(result["filters"]["gender"], "Female")
        self.assertEqual(result["filters"]["age_min"], 26)
        self.assertEqual(result["filters"]["age_max"], 30)

    def test_male_city_search(self, *_mocks):
        result = rule_based_extract("पुणे मधील मुले शोधा")
        self.assertIsNotNone(result)
        self.assertEqual(result["filters"]["gender"], "Male")
        self.assertEqual(result["filters"]["city"], "Pune")

    def test_english_query(self, *_mocks):
        result = rule_based_extract("in Pune show 3 girls")
        self.assertIsNotNone(result)
        self.assertEqual(result["filters"]["gender"], "Female")
        self.assertEqual(result["filters"]["city"], "Pune")
        self.assertEqual(result["limit"], 3)

    def test_city_caste_religion(self, *_mocks):
        result = rule_based_extract("कोल्हापूरातील ब्राह्मण मुलगी दाखवा")
        self.assertIsNotNone(result)
        self.assertEqual(result["filters"]["city"], "Kolhapur")
        self.assertEqual(result["filters"]["caste"], "Brahmin")
        self.assertEqual(result["filters"]["gender"], "Female")

    def test_greeting_falls_through(self, *_mocks):
        self.assertIsNone(rule_based_extract("नमस्कार"))
        self.assertIsNone(rule_based_extract("hi"))

    def test_detail_query_falls_through(self, *_mocks):
        self.assertIsNone(rule_based_extract("तिचे शिक्षण काय आहे"))
        self.assertIsNone(rule_based_extract("what is her education"))

    def test_generic_english_profiles_request_falls_through(self, *_mocks):
        # No concrete filter and not Devanagari -> leave it to the LLM.
        self.assertIsNone(rule_based_extract("show me profiles"))

    def test_marathi_profiles_request_intercepts(self, *_mocks):
        result = rule_based_extract("प्रोफाइल दाखवा")
        self.assertIsNotNone(result)
        self.assertEqual(result["filters"], {})
        self.assertTrue(result["deterministic"])

    def test_bare_search_verb_falls_through(self, *_mocks):
        self.assertIsNone(rule_based_extract("दाखवा"))
        self.assertIsNone(rule_based_extract("search something"))

    def test_widow_profiles(self, *_mocks):
        result = rule_based_extract("show widow profiles in Pune")
        self.assertIsNotNone(result)
        self.assertEqual(result["filters"]["gender"], "Female")
        self.assertEqual(result["filters"]["marital_status"], "Widow")
        self.assertEqual(result["filters"]["city"], "Pune")

    def test_widow_marathi(self, *_mocks):
        result = rule_based_extract("विधवा महिला दाखवा")
        self.assertIsNotNone(result)
        self.assertEqual(result["filters"]["gender"], "Female")
        self.assertEqual(result["filters"]["marital_status"], "Widow")

    def test_divorced_girls(self, *_mocks):
        result = rule_based_extract("show me divorced girls in Mumbai")
        self.assertIsNotNone(result)
        self.assertEqual(result["filters"]["gender"], "Female")
        self.assertEqual(result["filters"]["marital_status"], "Divorced")
        self.assertEqual(result["filters"]["city"], "Mumbai")

    def test_nri_boys(self, *_mocks):
        result = rule_based_extract("NRI boys")
        self.assertIsNotNone(result)
        self.assertEqual(result["filters"]["gender"], "Male")
        self.assertTrue(result["filters"]["nri"])

    def test_unmarried_marathi(self, *_mocks):
        result = rule_based_extract("अविवाहित मुली दाखवा")
        self.assertIsNotNone(result)
        self.assertEqual(result["filters"]["gender"], "Female")
        self.assertEqual(result["filters"]["marital_status"], "Unmarried")


if __name__ == "__main__":
    unittest.main()
