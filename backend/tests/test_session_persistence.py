"""Regression tests for the DB-session unification fix.

The chat/profile auto-link only worked for a single request: get_current_user
loaded the authenticated ``user`` through ``get_db_session`` while endpoints
used ``get_db``, and because those were two different dependency callables
FastAPI created two separate SQLAlchemy sessions per request. Mutations like
``user.matri_id = ...`` were made on the auth session's object but the
endpoint committed the *other* session, so the MatriID (and everything else
set on the auth user) was silently lost — the chat kept asking for the ID and
questionnaire answers fell through to the LLM router.
"""
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base


class SessionPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_db_is_the_same_callable_as_get_db_session(self):
        from app.database import get_db_session
        from app.dependencies import get_db

        self.assertIs(get_db, get_db_session)

    async def test_matri_id_and_prefs_persist_on_shared_session(self):
        import app.models  # noqa: F401  (registers every model on Base.metadata)
        from app.models.user_model import User
        from app.services.matri_service import link_matri_id_to_user

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        fake_link_result = {
            "member": {"matri_id": "DI80369", "name": "Prashant Nikam", "gender": "Male", "age": 29},
            "filters": {"gender": "Female", "age_min": "29", "age_max": "34"},
            "summary": {},
            "saved_search_used": False,
            "saved_search_source": None,
        }

        async with session_factory() as session:
            user = User(email="prashant@example.com", name="Prashant", is_active=True)
            session.add(user)
            await session.flush()
            with patch(
                "app.services.matri_service.link_matri_id",
                new=AsyncMock(return_value=fake_link_result),
            ):
                await link_matri_id_to_user(session, user, "di80369")
            await session.commit()
            self.assertEqual(user.matri_id, "DI80369")
            self.assertEqual(user.matri_name, "Prashant Nikam")

        # A fresh session must see the committed MatriID (the real bug: it was None).
        async with session_factory() as session:
            reloaded = await session.get(User, user.id)
            self.assertEqual(reloaded.matri_id, "DI80369")

        await engine.dispose()

    async def test_questionnaire_session_survives_second_request(self):
        """End-to-end of the reported flow: link in one request, then answer
        'कायम ठेवा' in a later request with the user reloaded from the DB."""
        import app.models  # noqa: F401
        from app.models.user_model import User
        from app.services.chat_service import ChatService
        from app.services.matri_service import link_matri_id_to_user

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        fake_link_result = {
            "member": {"matri_id": "DI80369", "name": "Prashant Nikam", "gender": "Male", "age": 29},
            "filters": {"gender": "Female", "age_min": "29", "age_max": "34"},
            "summary": {},
            "saved_search_used": False,
            "saved_search_source": None,
        }

        async with session_factory() as session:
            user = User(email="prashant@example.com", name="Prashant", is_active=True)
            session.add(user)
            await session.flush()
            with patch(
                "app.services.matri_service.link_matri_id",
                new=AsyncMock(return_value=fake_link_result),
            ):
                await link_matri_id_to_user(session, user, "di80369")
            await session.commit()

        # Second request: user is re-fetched from the DB (as get_current_user does).
        async with session_factory() as session:
            reloaded = await session.get(User, user.id)
            self.assertEqual(reloaded.matri_id, "DI80369")
            service = ChatService(db=session)
            result = await service._process_questionnaire(
                reloaded, user.id, "कायम ठेवा",
                {"questionnaire_answers": [], "questionnaire_pe_filters": fake_link_result["filters"], "questionnaire_done": False},
                7, [],
            )
            self.assertIsNotNone(result)
            self.assertIn("वैवाहिक स्थिती", result["reply"])

        await engine.dispose()


if __name__ == "__main__":
    unittest.main()
