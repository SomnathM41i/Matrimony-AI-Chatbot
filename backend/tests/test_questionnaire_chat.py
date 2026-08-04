"""Unit tests for the chat-side questionnaire helpers (questionnaire_chat.py).

These helpers map free-text Marathi/Hinglish chat answers onto the rule-based
questionnaire options defined in app.core.questionnaire. The answers are then
replayed through build_nodes/current_node/apply_answers in chat_service.
"""
import unittest

from app.core.questionnaire import ANY, CUSTOM, build_nodes
from app.services.questionnaire_chat import first_name, format_question, parse_answer

NO_PREFS = {}

PE_GENDER_ONLY = {"gender": "Female"}


def _build(pe_filters=None):
    nodes, entry_seqs, total = build_nodes(pe_filters or {})
    return nodes, entry_seqs


class FirstNameTests(unittest.TestCase):
    def test_first_word_returned(self):
        self.assertEqual(first_name("Ravi Kumar"), "Ravi")

    def test_none_returns_empty(self):
        self.assertEqual(first_name(None), "")

    def test_blank_returns_empty(self):
        self.assertEqual(first_name("   "), "")


class ParseSingleTests(unittest.TestCase):
    def setUp(self):
        self.nodes, self.entry_seqs = _build(NO_PREFS)

    def _answer(self, category, message):
        node = self.nodes[self.entry_seqs[category]]
        return parse_answer(node, message)

    def test_gender_marathi_synonym(self):
        result = self._answer("gender", "मुलगी")
        self.assertEqual(result, {"node_id": "gender_fresh", "option_id": "female"})

    def test_gender_hinglish_synonym(self):
        result = self._answer("gender", "ladka")
        self.assertEqual(result, {"node_id": "gender_fresh", "option_id": "male"})

    def test_gender_by_index(self):
        result = self._answer("gender", "2")
        self.assertEqual(result, {"node_id": "gender_fresh", "option_id": "female"})

    def test_gender_devanagari_digit_index(self):
        result = self._answer("gender", "२")
        self.assertEqual(result, {"node_id": "gender_fresh", "option_id": "female"})

    def test_age_range_single_number(self):
        result = self._answer("age_range", "26")
        self.assertEqual(result, {"node_id": "age_range_fresh", "option_id": "26_30"})

    def test_age_range_explicit_range(self):
        result = self._answer("age_range", "31 - 35")
        self.assertEqual(result, {"node_id": "age_range_fresh", "option_id": "31_35"})

    def test_age_range_devnagari_digits(self):
        result = self._answer("age_range", "२६ - ३०")
        self.assertEqual(result, {"node_id": "age_range_fresh", "option_id": "26_30"})

    def test_age_range_any(self):
        result = self._answer("age_range", "कोणताही")
        self.assertEqual(result, {"node_id": "age_range_fresh", "option_id": ANY})

    def test_marital_marathi(self):
        result = self._answer("marital_status", "घटस्फोटित")
        self.assertEqual(result, {"node_id": "marital_status_fresh", "option_id": "divorced"})

    def test_marital_english(self):
        result = self._answer("marital_status", "never married")
        self.assertEqual(result, {"node_id": "marital_status_fresh", "option_id": "unmarried"})

    def test_religion_marathi(self):
        result = self._answer("religion", "हिंदू")
        self.assertEqual(result, {"node_id": "religion_fresh", "option_id": "hindu"})

    def test_religion_by_index(self):
        result = self._answer("religion", "3")
        self.assertEqual(result, {"node_id": "religion_fresh", "option_id": "christian"})

    def test_religion_any(self):
        result = self._answer("religion", "पसंती नाही")
        self.assertEqual(result, {"node_id": "religion_fresh", "option_id": ANY})

    def test_manglik_yes(self):
        result = self._answer("manglik", "मांगलिक")
        self.assertEqual(result, {"node_id": "manglik_fresh", "option_id": "yes"})

    def test_manglik_no(self):
        result = self._answer("manglik", "नाही")
        self.assertEqual(result, {"node_id": "manglik_fresh", "option_id": "no"})

    def test_complexion_fair(self):
        result = self._answer("complexion", "गोरी")
        self.assertEqual(result, {"node_id": "complexion_fresh", "option_id": "fair"})

    def test_complexion_dark(self):
        result = self._answer("complexion", "सावळा")
        self.assertEqual(result, {"node_id": "complexion_fresh", "option_id": "dark"})

    def test_unrecognized_answer_returns_none(self):
        self.assertIsNone(self._answer("gender", "ब्लाह"))

    def test_empty_answer_returns_none(self):
        self.assertIsNone(self._answer("gender", "   "))


class ParseConfirmTests(unittest.TestCase):
    def setUp(self):
        self.nodes, self.entry_seqs = _build(
            {"gender": "Female", "age_min": "18", "age_max": "25"}
        )

    def _answer(self, message):
        node = self.nodes[self.entry_seqs["age_range"]]
        return parse_answer(node, message)

    def test_keep_by_index(self):
        result = self._answer("1")
        self.assertEqual(result, {"node_id": "age_range_confirm", "option_id": "keep"})

    def test_keep_marathi(self):
        result = self._answer("कायम ठेवा")
        self.assertEqual(result, {"node_id": "age_range_confirm", "option_id": "keep"})

    def test_change_marathi(self):
        result = self._answer("बदला")
        self.assertEqual(result, {"node_id": "age_range_confirm", "option_id": "change"})

    def test_skip_marathi(self):
        result = self._answer("वगळा")
        self.assertEqual(result, {"node_id": "age_range_confirm", "option_id": "skip"})

    def test_unrecognized_returns_none(self):
        self.assertIsNone(self._answer("काय करू?"))
        self.assertIsNone(self._answer("5"))


class ParseTextTests(unittest.TestCase):
    def setUp(self):
        self.nodes, self.entry_seqs = _build(NO_PREFS)

    def _answer(self, category, message):
        node = self.nodes[self.entry_seqs[category]]
        return parse_answer(node, message)

    def test_custom_value_returned(self):
        result = self._answer("caste", "मराठा")
        self.assertEqual(
            result,
            {"node_id": "caste_fresh", "option_id": CUSTOM, "value": "मराठा"},
        )

    def test_custom_value_strips_outer_whitespace(self):
        result = self._answer("occupation", "  Software Engineer  ")
        self.assertEqual(
            result,
            {"node_id": "occupation_fresh", "option_id": CUSTOM, "value": "Software Engineer"},
        )

    def test_any_option(self):
        result = self._answer("caste", "कोणतीही")
        self.assertEqual(result, {"node_id": "caste_fresh", "option_id": ANY})

    def test_skip_option(self):
        result = self._answer("city", "skip")
        self.assertEqual(result, {"node_id": "city_fresh", "option_id": ANY})

    def test_education_preset_label_match(self):
        result = self._answer("education", "पदवीधर")
        self.assertEqual(result, {"node_id": "education_fresh", "option_id": "graduate"})

    def test_education_custom_value(self):
        result = self._answer("education", "B.E.")
        self.assertEqual(result, {"node_id": "education_fresh", "option_id": CUSTOM, "value": "B.E."})


class GenderSkipTests(unittest.TestCase):
    def test_gender_auto_applied_first_question_is_age(self):
        nodes, entry_seqs = _build(PE_GENDER_ONLY)
        self.assertNotIn("gender", entry_seqs)
        self.assertNotIn("gender_fresh", entry_seqs)
        self.assertEqual(nodes[0]["id"], "age_range_fresh")

    def test_gender_filters_node_id(self):
        nodes, entry_seqs = _build(PE_GENDER_ONLY)
        node = nodes[0]
        self.assertEqual(node["id"], "age_range_fresh")
        self.assertEqual(node["category"], "age_range")


class FormatQuestionTests(unittest.TestCase):
    def test_formats_question_with_numbered_options(self):
        nodes, entry_seqs = _build(NO_PREFS)
        node = nodes[entry_seqs["age_range"]]
        text = format_question(node)
        self.assertIn("वयोगट", text)
        self.assertIn("1. 18 - 25 वर्षे", text)
        self.assertIn("6. कोणताही वयोगट", text)

    def test_format_with_progress(self):
        nodes, entry_seqs = _build(NO_PREFS)
        node = nodes[entry_seqs["age_range"]]
        text = format_question(node, index=2, total=11)
        self.assertIn("प्रश्न 2/11", text)


if __name__ == "__main__":
    unittest.main()
