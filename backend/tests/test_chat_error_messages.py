import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.ai.intent_llm import (
    detect_intent_with_llm,
    is_contextual_database_follow_up,
    is_response_transformation_request,
)
from app.services.chat_service import user_facing_error
from app.ai.sql_generator import validate_select_sql
from app.ai.llm_client import call_llm
from app.core.prompts import BASE_SYSTEM_PROMPT
from app.services.db_query_service import DatabaseQueryError, _sync_safe_query


class UserFacingErrorTests(unittest.TestCase):
    def test_sql_planning_error_does_not_leak_internal_details(self):
        response = user_facing_error(
            ValueError("Could not convert request into a database query.")
        )
        self.assertNotIn("database query", response)
        self.assertIn("rephrase", response.lower())

    def test_rate_limit_error_is_actionable(self):
        request = httpx.Request("POST", "https://example.test/chat")
        error = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=request,
            response=httpx.Response(429, request=request),
        )
        response = user_facing_error(error)
        self.assertNotIn("429", response)
        self.assertIn("try again", response.lower())

    def test_unknown_error_does_not_leak_exception(self):
        response = user_facing_error(RuntimeError("secret provider detail"))
        self.assertNotIn("secret provider detail", response)

    def test_database_failure_is_not_reported_as_no_results(self):
        response = user_facing_error(DatabaseQueryError("internal database detail"))
        self.assertIn("database", response.lower())
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
            "app.services.db_query_service._sync_get_connection",
            side_effect=RuntimeError("connection refused"),
        ):
            with self.assertRaises(DatabaseQueryError):
                _sync_safe_query("SELECT Name FROM register")


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


class ResponseTransformationTests(unittest.TestCase):
    def test_marathi_translation_follow_up(self):
        self.assertTrue(
            is_response_transformation_request("Can u let me know this in Marathi?")
        )

    def test_profile_search_is_not_transformation(self):
        self.assertFalse(
            is_response_transformation_request("Show me 5 female profiles in Pune")
        )

    def test_hindi_translation_follow_up(self):
        self.assertTrue(
            is_response_transformation_request("Please explain this in Hindi")
        )

    def test_location_is_not_mistaken_for_language(self):
        self.assertFalse(
            is_response_transformation_request("Show profiles in Mumbai")
        )


class ContextualDatabaseFollowUpTests(unittest.TestCase):
    history = [
        {"role": "user", "content": "Madhuri Arun Jhalte, give me more details"},
        {
            "role": "assistant",
            "content": "![Madhuri Arun Jhalte](https://example.test/photo.jpg) 34, Female, Dahyane, Hindu, Divorced",
        },
    ]

    def test_age_pronoun_uses_database(self):
        self.assertTrue(is_contextual_database_follow_up("How old is she?", self.history))

    def test_photo_pronoun_uses_database(self):
        self.assertTrue(is_contextual_database_follow_up("Show her photo", self.history))

    def test_unrelated_general_question_stays_general(self):
        self.assertFalse(is_contextual_database_follow_up("How are you?", self.history))

    def test_word_containing_he_is_not_a_pronoun(self):
        self.assertFalse(is_contextual_database_follow_up("Show the pricing", self.history))

    def test_no_profile_history_stays_general(self):
        history = [{"role": "assistant", "content": "Hello! How can I help?"}]
        self.assertFalse(is_contextual_database_follow_up("How old is she?", history))


class SemanticIntentRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_llm_semantic_decision_is_primary(self):
        history = [
            {"role": "assistant", "content": "![A](https://example.test/a.jpg) Female"}
        ]
        with patch(
            "app.ai.intent_llm.call_groq",
            new=AsyncMock(return_value={"content": "general"}),
        ) as mocked_call:
            result = await detect_intent_with_llm("Show her photo", history)

        self.assertFalse(result)
        mocked_call.assert_awaited_once()

    async def test_semantically_worded_profile_follow_up_can_route_to_database(self):
        history = [
            {"role": "assistant", "content": "Previously displayed member data"}
        ]
        with patch(
            "app.ai.intent_llm.call_groq",
            new=AsyncMock(return_value={"content": "database"}),
        ):
            result = await detect_intent_with_llm(
                "Would our families need to account for a relocation?", history
            )

        self.assertTrue(result)


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


if __name__ == "__main__":
    unittest.main()
