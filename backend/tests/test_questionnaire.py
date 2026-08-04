"""Unit tests for the rule-based partner-preference questionnaire.

The questionnaire is deliberately zero-LLM: every question, option and
branch lives in app.core.questionnaire. These tests pin down traversal,
confirm (keep/change/skip) nodes, custom text answers and the final
filter output that gets saved to the user_preferences table.
"""
import unittest

from app.core.questionnaire import (
    BUILD_ORDER,
    DONE,
    QuestionnaireError,
    apply_answers,
    build_nodes,
    current_node,
    is_viable_search,
    serialize_node,
    validate_answer,
)
from app.services.matri_service import advance_questionnaire, start_questionnaire

NO_PREFS = {}

ALL_PREFS = {
    "gender": "Female",
    "age_min": "18",
    "age_max": "25",
    "marital_status": "Unmarried",
    "religion": "Hindu",
    "caste": "Maratha",
    "education": "Graduate",
    "occupation": "Engineer",
    "city": "Pune",
    "manglik": "Yes",
    "complexion": "Fair",
}


def _first_options(node, *ids):
    opts = {o["id"]: o for o in node["options"]}
    return [opts[i] for i in ids]


class BuildNodesTests(unittest.TestCase):
    def test_build_nodes_without_preferences_has_one_node_per_category(self):
        nodes, entry_seqs, total = build_nodes(NO_PREFS)
        self.assertEqual(total, len(BUILD_ORDER))
        for category in BUILD_ORDER:
            self.assertIn(category, entry_seqs)
            self.assertNotIn(f"{category}_confirm", entry_seqs)
        self.assertEqual(len(nodes), len(BUILD_ORDER))

    def test_build_nodes_with_preferences_skips_gender_and_has_confirm_per_known_value(self):
        nodes, entry_seqs, total = build_nodes(ALL_PREFS)
        # Partner gender is auto-applied from the member, so gender is skipped.
        self.assertNotIn("gender", entry_seqs)
        self.assertNotIn("gender_confirm", {n["id"] for n in nodes})
        # subcaste has no known value; age_min/age_max collapse into one
        # age_range confirm node -> 9 confirm nodes among the remaining 10
        # categories (gender skipped).
        known_categories = 9
        self.assertEqual(total, len(BUILD_ORDER) - 1 + known_categories)
        self.assertEqual(len(nodes), total)
        for category in ("age_range", "caste", "city"):
            self.assertEqual(nodes[entry_seqs[category]]["id"], f"{category}_confirm")
            self.assertEqual(nodes[entry_seqs[f"{category}_fresh"]]["id"], f"{category}_fresh")
        self.assertNotIn("subcaste_confirm", {n["id"] for n in nodes})

    def test_confirm_node_precedes_fresh_node(self):
        nodes, entry_seqs, _ = build_nodes(ALL_PREFS)
        self.assertLess(entry_seqs["age_range"], entry_seqs["age_range_fresh"])
        self.assertEqual(nodes[entry_seqs["age_range"]]["id"], "age_range_confirm")
        self.assertEqual(nodes[entry_seqs["age_range_fresh"]]["id"], "age_range_fresh")


class MissingOnlyBuildTests(unittest.TestCase):
    """CF-3: chat onboarding auto-applies known preferences and asks only the
    missing categories (no "कायम ठेवा?" confirm nodes)."""

    def test_missing_only_drops_confirm_nodes_and_asks_missing(self):
        nodes, entry_seqs, total = build_nodes(ALL_PREFS, missing_only=True)
        self.assertEqual([n["id"] for n in nodes], ["subcaste_fresh"])
        self.assertEqual(total, 1)
        self.assertEqual(entry_seqs, {"subcaste": 0})

    def test_missing_only_gender_only_asks_every_other_category(self):
        nodes, entry_seqs, total = build_nodes({"gender": "Female"}, missing_only=True)
        self.assertNotIn("gender", entry_seqs)
        self.assertEqual(total, len(BUILD_ORDER) - 1)
        for n in nodes:
            self.assertNotIn("_confirm", n["id"])

    def test_default_mode_still_has_confirm_nodes(self):
        nodes, entry_seqs, _ = build_nodes({"gender": "Female", "age_min": "18", "age_max": "25"})
        self.assertEqual(nodes[entry_seqs["age_range"]]["id"], "age_range_confirm")


class ViableSearchTests(unittest.TestCase):
    """CF-3 search-early strategies."""

    def test_gender_plus_core_requires_gender_and_a_core_filter(self):
        self.assertTrue(is_viable_search({"gender": "Female", "age_min": "18"}))
        self.assertTrue(is_viable_search({"gender": "Female", "city": "Pune"}))
        self.assertTrue(is_viable_search({"gender": "Female", "education": "Graduate"}))
        self.assertFalse(is_viable_search({"gender": "Female"}))
        self.assertFalse(is_viable_search({"age_min": "18"}))

    def test_gender_only_strategy(self):
        self.assertTrue(is_viable_search({"gender": "Female"}, "gender_only"))
        self.assertFalse(is_viable_search({"age_min": "18"}, "gender_only"))

    def test_full_only_never_searches_early(self):
        self.assertFalse(is_viable_search({"gender": "Female", "city": "Pune"}, "full_only"))


class TraversalTests(unittest.TestCase):
    def test_returns_first_node_with_no_answers(self):
        nodes, entry_seqs, _ = build_nodes(NO_PREFS)
        node = current_node(nodes, entry_seqs, [])
        self.assertEqual(node["id"], "gender_fresh")

    def test_advances_through_single_option_nodes(self):
        nodes, entry_seqs, _ = build_nodes(NO_PREFS)
        answers = [
            {"node_id": "gender_fresh", "option_id": "female"},
            {"node_id": "age_range_fresh", "option_id": "26_30"},
        ]
        node = current_node(nodes, entry_seqs, answers)
        self.assertEqual(node["id"], "marital_status_fresh")

    def test_custom_text_answer_advances_to_next_node(self):
        """Regression: a custom text answer must advance the cursor, otherwise
        the questionnaire loops forever on the same question."""
        nodes, entry_seqs, _ = build_nodes(NO_PREFS)
        answers = [
            {"node_id": "gender_fresh", "option_id": "female"},
            {"node_id": "age_range_fresh", "option_id": "26_30"},
            {"node_id": "marital_status_fresh", "option_id": "unmarried"},
            {"node_id": "religion_fresh", "option_id": "any"},
            {"node_id": "education_fresh", "option_id": "custom", "value": "B.E."},
        ]
        node = current_node(nodes, entry_seqs, answers)
        self.assertIsNotNone(node)
        self.assertEqual(node["id"], "occupation_fresh")

    def test_any_religion_skips_caste_and_subcaste(self):
        nodes, entry_seqs, _ = build_nodes(NO_PREFS)
        answers = [
            {"node_id": "gender_fresh", "option_id": "female"},
            {"node_id": "age_range_fresh", "option_id": "26_30"},
            {"node_id": "marital_status_fresh", "option_id": "unmarried"},
            {"node_id": "religion_fresh", "option_id": "any"},
        ]
        node = current_node(nodes, entry_seqs, answers)
        self.assertEqual(node["id"], "education_fresh")

    def test_last_answer_marks_flow_done(self):
        nodes, entry_seqs, _ = build_nodes(NO_PREFS)
        answers = [
            {"node_id": "gender_fresh", "option_id": "female"},
            {"node_id": "age_range_fresh", "option_id": "26_30"},
            {"node_id": "marital_status_fresh", "option_id": "unmarried"},
            {"node_id": "religion_fresh", "option_id": "any"},
            {"node_id": "education_fresh", "option_id": "custom", "value": "B.E."},
            {"node_id": "occupation_fresh", "option_id": "custom", "value": "Engineer"},
            {"node_id": "city_fresh", "option_id": "custom", "value": "Pune"},
            {"node_id": "manglik_fresh", "option_id": "no"},
            {"node_id": "complexion_fresh", "option_id": "any"},
        ]
        self.assertIsNone(current_node(nodes, entry_seqs, answers))


class ConfirmNodeTests(unittest.TestCase):
    def setUp(self):
        self.nodes, self.entry_seqs, _ = build_nodes(ALL_PREFS)

    def test_keep_preserves_value_and_advances(self):
        answers = [{"node_id": "age_range_confirm", "option_id": "keep"}]
        filters = apply_answers(self.nodes, answers, ALL_PREFS)
        self.assertEqual(filters["age_min"], "18")
        node = current_node(self.nodes, self.entry_seqs, answers)
        self.assertEqual(node["id"], "marital_status_confirm")

    def test_skip_clears_value(self):
        answers = [{"node_id": "age_range_confirm", "option_id": "skip"}]
        filters = apply_answers(self.nodes, answers, ALL_PREFS)
        self.assertNotIn("age_min", filters)
        node = current_node(self.nodes, self.entry_seqs, answers)
        self.assertEqual(node["id"], "marital_status_confirm")

    def test_change_jumps_to_fresh_node(self):
        answers = [{"node_id": "age_range_confirm", "option_id": "change"}]
        node = current_node(self.nodes, self.entry_seqs, answers)
        self.assertEqual(node["id"], "age_range_fresh")

    def test_changing_fresh_value_overrides_known_value(self):
        answers = [
            {"node_id": "age_range_confirm", "option_id": "change"},
            {"node_id": "age_range_fresh", "option_id": "31_35"},
        ]
        filters = apply_answers(self.nodes, answers, ALL_PREFS)
        self.assertEqual(filters["age_min"], "31")
        self.assertEqual(filters["age_max"], "35")
        node = current_node(self.nodes, self.entry_seqs, answers)
        self.assertEqual(node["id"], "marital_status_confirm")

    def test_skipping_fresh_node_clears_preference(self):
        answers = [
            {"node_id": "city_confirm", "option_id": "change"},
            {"node_id": "city_fresh", "option_id": "any"},
        ]
        filters = apply_answers(self.nodes, answers, ALL_PREFS)
        self.assertNotIn("city", filters)
        self.assertNotIn("state", filters)


class ValidationTests(unittest.TestCase):
    def test_unknown_answer_node_rejected(self):
        nodes, entry_seqs, _ = build_nodes(NO_PREFS)
        with self.assertRaises(QuestionnaireError):
            advance_questionnaire(NO_PREFS, [{"node_id": "bogus_fresh", "option_id": "x"}])

    def test_invalid_option_rejected(self):
        nodes, entry_seqs, _ = build_nodes(NO_PREFS)
        node = nodes[0]
        self.assertIsNotNone(validate_answer(node, {"node_id": node["id"], "option_id": "nope"}))
        self.assertIsNone(validate_answer(node, {"node_id": node["id"], "option_id": "female"}))

    def test_custom_text_answer_requires_value(self):
        nodes, entry_seqs, _ = build_nodes(NO_PREFS)
        node = nodes[entry_seqs["caste"]]
        error = validate_answer(node, {"node_id": node["id"], "option_id": "custom", "value": "  "})
        self.assertEqual(error, "कृपया या उत्तरासाठी मूल्य लिहा.")


class SerializeTests(unittest.TestCase):
    def test_serialize_node_exposes_ui_fields(self):
        nodes, entry_seqs, total = build_nodes(NO_PREFS)
        node = nodes[0]
        serialized = serialize_node(node, 0, total, {})
        self.assertEqual(serialized["node_id"], "gender_fresh")
        self.assertEqual(serialized["category"], "gender")
        self.assertEqual(serialized["type"], "single")
        self.assertIn("progress", serialized)
        self.assertEqual(serialized["progress"]["total"], total)
        self.assertIn("filters_so_far", serialized)
        for option in serialized["options"]:
            self.assertIn("id", option)
            self.assertIn("label", option)


class FlowWrapperTests(unittest.TestCase):
    def test_start_without_preferences_returns_first_node(self):
        result = start_questionnaire(NO_PREFS)
        self.assertFalse(result["done"])
        self.assertEqual(result["node"]["node_id"], "gender_fresh")
        self.assertEqual(result["node"]["progress"]["current"], 1)

    def test_start_with_preferences_returns_confirm_node(self):
        result = start_questionnaire(ALL_PREFS)
        self.assertFalse(result["done"])
        self.assertEqual(result["node"]["node_id"], "age_range_confirm")
        self.assertEqual(result["node"]["type"], "confirm")
        self.assertEqual(result["node"]["known_value"], "18 - 25 वर्षे वयोगट")

    def test_start_with_gender_only_returns_first_fresh_question(self):
        result = start_questionnaire({"gender": "Female"})
        self.assertFalse(result["done"])
        self.assertEqual(result["node"]["node_id"], "age_range_fresh")
        self.assertEqual(result["node"]["type"], "single")

    def test_advance_returns_done_with_final_filters(self):
        result = advance_questionnaire(NO_PREFS, [
            {"node_id": "gender_fresh", "option_id": "female"},
            {"node_id": "age_range_fresh", "option_id": "26_30"},
            {"node_id": "marital_status_fresh", "option_id": "unmarried"},
            {"node_id": "religion_fresh", "option_id": "any"},
            {"node_id": "education_fresh", "option_id": "custom", "value": "B.E."},
            {"node_id": "occupation_fresh", "option_id": "custom", "value": "Engineer"},
            {"node_id": "city_fresh", "option_id": "custom", "value": "Pune"},
            {"node_id": "manglik_fresh", "option_id": "no"},
            {"node_id": "complexion_fresh", "option_id": "any"},
        ])
        self.assertTrue(result["done"])
        self.assertIsNone(result["node"])
        self.assertEqual(
            result["filters"],
            {
                "gender": "Female",
                "age_min": "26",
                "age_max": "30",
                "marital_status": "Unmarried",
                "education": "B.E.",
                "occupation": "Engineer",
                "city": "Pune",
                "manglik": "No",
            },
        )

    def test_advance_keeps_pe_values_when_kept(self):
        result = advance_questionnaire(ALL_PREFS, [
            {"node_id": "age_range_confirm", "option_id": "keep"},
            {"node_id": "marital_status_confirm", "option_id": "keep"},
            {"node_id": "religion_confirm", "option_id": "keep"},
            {"node_id": "caste_confirm", "option_id": "keep"},
            {"node_id": "subcaste_fresh", "option_id": "any"},
            {"node_id": "education_confirm", "option_id": "keep"},
            {"node_id": "occupation_confirm", "option_id": "keep"},
            {"node_id": "city_confirm", "option_id": "keep"},
            {"node_id": "manglik_confirm", "option_id": "keep"},
            {"node_id": "complexion_confirm", "option_id": "keep"},
        ])
        self.assertTrue(result["done"])
        for key, value in ALL_PREFS.items():
            self.assertEqual(result["filters"][key], value)


if __name__ == "__main__":
    unittest.main()
