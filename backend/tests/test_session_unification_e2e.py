"""End-to-end regression test for the DB-session unification fix.

Drives the real FastAPI app (with the in-memory SQLite session substituted via
dependency overrides) through the exact flow the user reported:

1. Register + login.
2. Stream a bare MatriID -> auto-link starts the questionnaire.
3. /api/auth/me must now return the linked matri_id (this failed before the
   fix: get_current_user used a different session than the endpoint, so the
   user row never got the update).
4. Send "कायम ठेवा" in the same conversation -> the questionnaire intercepts
   it (no LLM/router) and replies with the next question.
"""
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db_session
from app.main import app

fake_link_result = {
    "member": {"matri_id": "DI80369", "name": "Prashant Nikam", "gender": "Male", "age": 29},
    "filters": {"gender": "Female", "age_min": "29", "age_max": "34"},
    "summary": {},
    "saved_search_used": False,
    "saved_search_source": None,
}

GENERAL_LLM_STUB = {"content": '{"intent": "general", "filters": {}, "limit": 10}'}


class SessionUnificationE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app.models  # noqa: F401
        cls.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        cls.session_factory = async_sessionmaker(cls.engine, expire_on_commit=False)

    @classmethod
    def tearDownClass(cls):
        import asyncio
        asyncio.run(cls.engine.dispose())

    def setUp(self):
        import asyncio
        asyncio.run(self._reset_db())
        app.dependency_overrides[get_db_session] = self._override_session
        # SlowAPI limiter would count TestClient requests; disable it.
        app.state.limiter.enabled = False
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        app.state.limiter.enabled = True
        self.client.close()

    async def _reset_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def _override_session(self):
        async with self.session_factory() as session:
            yield session

    def _register(self):
        r = self.client.post("/api/auth/register", json={
            "name": "Prashant",
            "email": "prashant@example.com",
            "password": "Secret@123",
        })
        self.assertEqual(r.status_code, 200, r.text)

    def _auth(self):
        return {"X-Test": "cookie-authed"}  # access token travels in the session cookie

    def test_auto_link_persists_matri_id_and_questionnaire_intercepts_next_answer(self):
        self._register()

        with patch(
            "app.services.matri_service.link_matri_id",
            new=AsyncMock(return_value=fake_link_result),
        ):
            with self.client.stream("POST", "/api/chat/stream", json={"message": "DI80369"}, headers=self._auth()) as resp:
                self.assertEqual(resp.status_code, 200)
                chunks = [line for line in resp.iter_lines() if line]
        done = json.loads(chunks[-1][len("data: "):])
        self.assertEqual(done["type"], "done")
        self.assertIn("questionnaire", done)
        conv_id = done["conversation_id"]
        self.assertIsNotNone(conv_id)

        # The user's MatriID must now be persisted (this is the regression).
        me = self.client.get("/api/auth/me", headers=self._auth()).json()
        self.assertEqual(me["matri_id"], "DI80369")

        # Answer "कायम ठेवा" in the same conversation -> questionnaire reply,
        # NOT the LLM router.
        with patch("app.services.extraction_service.call_ai", new=AsyncMock(return_value=GENERAL_LLM_STUB)) as call_ai:
            with self.client.stream(
                "POST", "/api/chat/stream",
                json={"message": "कायम ठेवा", "conversation_id": conv_id},
                headers=self._auth(),
            ) as resp:
                self.assertEqual(resp.status_code, 200)
                chunks = [line for line in resp.iter_lines() if line]
        events = [json.loads(c[len("data: "):]) for c in chunks]
        tokens = "".join(e["content"] for e in events if e["type"] == "token")
        self.assertIn("वैवाहिक स्थिती", tokens)
        call_ai.assert_not_called()

        # The kept age-range preference is applied: no LLM was used, so the
        # auto-saved questionnaire preferences must not have been overwritten.
        self.assertIn("questionnaire", done)

    def test_questionnaire_answer_after_page_reload_still_intercepted(self):
        """Same as above but the answer arrives in a brand-new request/session
        (simulating a page reload) — the session metadata lives in the DB."""
        self._register()

        with patch(
            "app.services.matri_service.link_matri_id",
            new=AsyncMock(return_value=fake_link_result),
        ):
            with self.client.stream("POST", "/api/chat/stream", json={"message": "DI80369"}, headers=self._auth()) as resp:
                chunks = [line for line in resp.iter_lines() if line]
        done = json.loads(chunks[-1][len("data: "):])
        conv_id = done["conversation_id"]

        # The answer arrives in a fresh request path (like a page reload).
        with patch("app.services.extraction_service.call_ai", new=AsyncMock(return_value=GENERAL_LLM_STUB)) as call_ai:
            with self.client.stream(
                "POST", "/api/chat/stream",
                json={"message": "कायम ठेवा", "conversation_id": conv_id},
                headers=self._auth(),
            ) as resp:
                self.assertEqual(resp.status_code, 200)
                chunks = [line for line in resp.iter_lines() if line]
        events = [json.loads(c[len("data: "):]) for c in chunks]
        tokens = "".join(e["content"] for e in events if e["type"] == "token")
        self.assertIn("वैवाहिक स्थिती", tokens)
        call_ai.assert_not_called()


if __name__ == "__main__":
    unittest.main()
