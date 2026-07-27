import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.services.chat_service import user_facing_error
from app.ai.llm_client import call_llm
from app.core.prompts import BASE_SYSTEM_PROMPT
from app.services.db_query_service import DatabaseQueryError, _sync_safe_query, validate_select_sql


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
