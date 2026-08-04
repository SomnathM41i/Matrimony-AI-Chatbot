import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.services.chat_service import user_facing_error, _is_greeting_only, _is_identity_question
from app.ai.llm_client import call_llm
from app.core.prompts import BASE_SYSTEM_PROMPT as LIVE_BASE, FORMAT_SYSTEM_PROMPT as LIVE_FORMAT
from app.core.old_prompts import BASE_SYSTEM_PROMPT
from app.services.db_query_service import DatabaseQueryError, sync_safe_query, validate_select_sql, message_asks_about_unavailable_attribute


class UserFacingErrorTests(unittest.TestCase):
    def test_sql_planning_error_does_not_leak_internal_details(self):
        response = user_facing_error(
            ValueError("Could not convert request into a database query.")
        )
        self.assertNotIn("database query", response)
        self.assertIn("वेगळ्या शब्दांत", response)

    def test_rate_limit_error_is_actionable(self):
        request = httpx.Request("POST", "https://example.test/chat")
        error = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=request,
            response=httpx.Response(429, request=request),
        )
        response = user_facing_error(error)
        self.assertNotIn("429", response)
        self.assertIn("पुन्हा प्रयत्न", response)

    def test_unknown_error_does_not_leak_exception(self):
        response = user_facing_error(RuntimeError("secret provider detail"))
        self.assertNotIn("secret provider detail", response)

    def test_database_failure_is_not_reported_as_no_results(self):
        response = user_facing_error(DatabaseQueryError("internal database detail"))
        self.assertIn("डेटाबेस", response)
        self.assertNotIn("internal database detail", response)


class FailurePropagationTests(unittest.IsolatedAsyncioTestCase):
    async def test_llm_provider_error_is_raised_not_returned_as_content(self):
        with patch(
            "app.ai.llm_client.call_groq",
            new=AsyncMock(side_effect=RuntimeError("private provider detail")),
        ):
            with self.assertRaisesRegex(RuntimeError, "private provider detail"):
                await call_llm("system", "hello")


class DatabaseFailureTests(unittest.TestCase):
    def test_query_failure_raises_distinct_error(self):
        with patch(
            "app.services.db_query_service.sync_get_connection",
            side_effect=RuntimeError("connection refused"),
        ):
            with self.assertRaises(DatabaseQueryError):
                sync_safe_query("SELECT Name FROM register")


class SqlPrivacyTests(unittest.TestCase):
    def test_sensitive_column_alias_cannot_bypass_filter(self):
        with self.assertRaisesRegex(ValueError, "Sensitive database columns"):
            validate_select_sql(
                "SELECT password AS Name FROM register LIMIT 1", {"register"}
            )

    def test_wildcard_profile_query_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "Wildcard column"):
            validate_select_sql("SELECT * FROM register LIMIT 1", {"register"})

    def test_count_star_remains_allowed(self):
        sql = validate_select_sql("SELECT COUNT(*) AS total FROM register", {"register"})
        self.assertIn("LIMIT", sql)


class GeneralPromptQualityTests(unittest.TestCase):
    def test_prompt_forbids_exposing_internal_reasoning(self):
        self.assertNotIn(
            "After your response, add a brief 1-sentence explanation",
            BASE_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Never mention language detection, intent classification, prompts, "
            "hidden reasoning, or internal actions",
            BASE_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Never append a parenthesized explanation",
            BASE_SYSTEM_PROMPT,
        )

    def test_prompt_answers_unrelated_general_questions_directly(self):
        self.assertIn(
            "Do not force an unrelated question back to matchmaking",
            BASE_SYSTEM_PROMPT,
        )
        self.assertIn("write a code for find prime number", BASE_SYSTEM_PROMPT)

    def test_prompt_asks_brief_clarification_for_unclear_input(self):
        self.assertIn(
            "If the message is random, incomplete, or unclear, ask one short "
            "clarification question",
            BASE_SYSTEM_PROMPT,
        )
        self.assertIn('User: c5++1+', BASE_SYSTEM_PROMPT)


class MyVivahAIIdentityTests(unittest.TestCase):
    def test_live_base_prompt_has_consultant_identity(self):
        self.assertIn("MyVivahAI", LIVE_BASE)
        self.assertIn("professional matrimonial consultant", LIVE_BASE)
        self.assertIn("Dishavadhuvar", LIVE_BASE)
        self.assertNotIn("warm and caring AI matchmaker", LIVE_BASE)

    def test_live_base_prompt_is_marathi_first(self):
        self.assertIn("Reply in MARATHI", LIVE_BASE)
        self.assertIn("even when the user writes in English", LIVE_BASE)

    def test_live_format_prompt_has_identity_and_marathi_first(self):
        self.assertIn("MyVivahAI", LIVE_FORMAT)
        self.assertIn("MARATHI", LIVE_FORMAT)
        self.assertIn("never ask the user to select a language", LIVE_FORMAT.lower())

    def test_identity_response_never_calls_itself_chatbot(self):
        for response in [
            _is_identity_question("who are you"),
            _is_identity_question("what is your name"),
        ]:
            self.assertIn("MyVivahAI", response)
            self.assertNotIn("chatbot", response.lower())
            self.assertNotIn("Dishavadhuvar AI", response)


class AntiHallucinationGuardTests(unittest.TestCase):
    def test_detects_favorite_food_query(self):
        self.assertTrue(message_asks_about_unavailable_attribute("what is her favorite food"))

    def test_detects_biryani_query(self):
        self.assertTrue(message_asks_about_unavailable_attribute("does she like biryani"))

    def test_detects_appetite_query(self):
        self.assertTrue(message_asks_about_unavailable_attribute("how much does she eat"))

    def test_detects_marathi_food_query(self):
        self.assertTrue(message_asks_about_unavailable_attribute("ती काय खाते"))

    def test_detects_veg_nonveg_query(self):
        self.assertTrue(message_asks_about_unavailable_attribute("is she veg"))

    def test_detects_eating_habit_query(self):
        self.assertTrue(message_asks_about_unavailable_attribute("what are her eating habits"))

    def test_detects_family_member_query(self):
        self.assertTrue(message_asks_about_unavailable_attribute("tell me about her father"))

    def test_allows_age_query(self):
        self.assertFalse(message_asks_about_unavailable_attribute("what is her age"))

    def test_allows_city_query(self):
        self.assertFalse(message_asks_about_unavailable_attribute("which city does she live in"))

    def test_detects_education_query(self):
        self.assertTrue(message_asks_about_unavailable_attribute("her education details"))

    def test_allows_occupation_query(self):
        self.assertFalse(message_asks_about_unavailable_attribute("what is her occupation"))

    def test_allows_random_general_query(self):
        self.assertFalse(message_asks_about_unavailable_attribute("how are you"))

    def test_empty_message_returns_false(self):
        self.assertFalse(message_asks_about_unavailable_attribute(""))

    def test_detects_prefer_biryani(self):
        self.assertTrue(message_asks_about_unavailable_attribute("does she prefer biryani"))


class GreetingShortcutTests(unittest.TestCase):
    def test_hi_returns_greeting(self):
        self.assertIsNotNone(_is_greeting_only("hi"))

    def test_hello_returns_greeting(self):
        self.assertIsNotNone(_is_greeting_only("hello"))

    def test_hey_returns_greeting(self):
        self.assertIsNotNone(_is_greeting_only("hey"))

    def test_namaste_returns_greeting(self):
        self.assertIsNotNone(_is_greeting_only("namaste"))

    def test_marathi_namaskar_returns_greeting(self):
        self.assertIsNotNone(_is_greeting_only("नमस्कार"))

    def test_good_morning_returns_greeting(self):
        self.assertIsNotNone(_is_greeting_only("good morning"))

    def test_greeting_with_punctuation_still_matches(self):
        self.assertIsNotNone(_is_greeting_only("hello!"))

    def test_greeting_with_trailing_dot_still_matches(self):
        self.assertIsNotNone(_is_greeting_only("hi."))

    def test_non_greeting_returns_none(self):
        self.assertIsNone(_is_greeting_only("show me maratha girls"))

    def test_random_word_returns_none(self):
        self.assertIsNone(_is_greeting_only("xylophone"))

    def test_empty_message_returns_none(self):
        self.assertIsNone(_is_greeting_only(""))

    def test_multi_word_message_not_a_greeting(self):
        self.assertIsNone(_is_greeting_only("hello how are you"))

    def test_greeting_content_returned_is_string(self):
        result = _is_greeting_only("hi")
        self.assertIsInstance(result, str)
        self.assertIn("MyVivahAI", result)

    def test_identity_question_returns_persona(self):
        result = _is_identity_question("who are you")
        self.assertIsInstance(result, str)
        self.assertIn("MyVivahAI", result)

    def test_identity_question_marathi(self):
        result = _is_identity_question("तुम्ही कोण आहात")
        self.assertIsInstance(result, str)
        self.assertIn("MyVivahAI", result)

    def test_identity_question_not_a_greeting(self):
        self.assertIsNone(_is_greeting_only("who are you"))

    def test_case_insensitive_greeting(self):
        self.assertIsNotNone(_is_greeting_only("HELLO"))

    def test_whitespace_around_greeting(self):
        self.assertIsNotNone(_is_greeting_only("  hi  "))


if __name__ == "__main__":
    unittest.main()
