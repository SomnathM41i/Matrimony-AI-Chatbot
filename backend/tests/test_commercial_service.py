import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
import app.models  # noqa: F401 - register all tables
from app.models.commercial_model import AIModel, AIProvider, Subscription, SubscriptionPlan
from app.models.user_model import User
from app.services.commercial_service import (
    CommercialLimitError,
    finalize_usage,
    reserve_usage,
)
from app.ai.gateway import _event
from app.services.chat_service import ChatService
from sqlalchemy import select
from app.models.commercial_model import AIUsageEvent


class CommercialQuotaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as db:
            user = User(email="quota@example.test", name="Quota User", password_hash="x")
            plan = SubscriptionPlan(
                code="TEST", version=1, name="Test", price_paise=100,
                duration_days=30, ai_credits=4, daily_message_limit=2,
                contact_limit=0, normal_credit_cost=1, database_credit_cost=2,
            )
            db.add_all([user, plan])
            await db.flush()
            db.add(Subscription(
                user_id=user.id, plan_id=plan.id, status="active",
                plan_code=plan.code, plan_name=plan.name, price_paid_paise=100,
                credits_allocated=4, credits_used=0, daily_message_limit=2,
                daily_messages_used=0, normal_credit_cost=1, database_credit_cost=2,
                contact_limit=0, started_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            ))
            await db.commit()
            self.user_id = user.id

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_normal_message_releases_unused_reserved_credit(self):
        async with self.sessions() as db:
            _, subscription = await reserve_usage(db, self.user_id, "normal-1")
            self.assertEqual(subscription.credits_used, 2)
            charged = await finalize_usage(db, "normal-1", "normal", True)
            self.assertEqual(charged, 1)
            self.assertEqual(subscription.credits_used, 1)
            self.assertEqual(subscription.daily_messages_used, 1)

    async def test_failed_message_releases_credit_and_daily_count(self):
        async with self.sessions() as db:
            _, subscription = await reserve_usage(db, self.user_id, "failed-1")
            charged = await finalize_usage(db, "failed-1", "database", False)
            self.assertEqual(charged, 0)
            self.assertEqual(subscription.credits_used, 0)
            self.assertEqual(subscription.daily_messages_used, 0)

    async def test_finalization_is_idempotent(self):
        async with self.sessions() as db:
            _, subscription = await reserve_usage(db, self.user_id, "same-request")
            first = await finalize_usage(db, "same-request", "normal", True)
            second = await finalize_usage(db, "same-request", "normal", True)
            await db.refresh(subscription)
            self.assertEqual((first, second), (1, 1))
            self.assertEqual(subscription.credits_used, 1)

    async def test_daily_limit_is_enforced(self):
        async with self.sessions() as db:
            await reserve_usage(db, self.user_id, "db-1")
            await finalize_usage(db, "db-1", "database", True)
            await reserve_usage(db, self.user_id, "db-2")
            await finalize_usage(db, "db-2", "database", True)
            with self.assertRaises(CommercialLimitError) as context:
                await reserve_usage(db, self.user_id, "db-3")
            self.assertEqual(context.exception.code, "daily_limit_reached")


class CostNormalizationTests(unittest.TestCase):
    def test_model_cost_is_recorded_in_micropaise(self):
        provider = AIProvider(code="test", name="Test", base_url="http://example.test")
        model = AIModel(
            external_id="model", display_name="Model", provider=provider,
            input_cost_paise_per_million=5700,
            output_cost_paise_per_million=7600,
        )
        event = _event(
            "general_chat", provider, model,
            {"id": "req", "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000, "total_tokens": 2_000_000}},
            10,
        )
        self.assertEqual(event["estimated_cost_micropaise"], 13_300_000_000)
        self.assertEqual(event["estimated_cost_micropaise"] / 1_000_000, 13_300)


class CommercialChatIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_charges_one_credit_and_records_every_ai_call(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            user = User(email="chat@example.test", name="Chat User", password_hash="x")
            plan = SubscriptionPlan(
                code="CHAT", version=1, name="Chat", price_paise=100,
                duration_days=30, ai_credits=10, daily_message_limit=10,
                contact_limit=0, normal_credit_cost=1, database_credit_cost=2,
            )
            db.add_all([user, plan])
            await db.flush()
            subscription = Subscription(
                user_id=user.id, plan_id=plan.id, status="active",
                plan_code=plan.code, plan_name=plan.name, price_paid_paise=100,
                credits_allocated=10, credits_used=0, daily_message_limit=10,
                daily_messages_used=0, normal_credit_cost=1, database_credit_cost=2,
                contact_limit=0, started_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            )
            db.add(subscription)
            await db.commit()
            intent = {
                "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
                "events": [{"task_key": "intent_detection", "provider_code": "p", "model_external_id": "intent", "total_tokens": 11}],
            }
            answer = {
                "content": "Hello",
                "usage": {"prompt_tokens": 20, "completion_tokens": 2, "total_tokens": 22},
                "events": [{"task_key": "general_chat", "provider_code": "p", "model_external_id": "chat", "total_tokens": 22}],
            }
            with patch("app.services.chat_service.detect_intent_with_llm", new=AsyncMock(return_value=(False, intent))), patch(
                "app.services.chat_service.get_general_response", new=AsyncMock(return_value=answer)
            ):
                result = await ChatService(db).process_message(user.id, "Hi")
            await db.commit()
            await db.refresh(subscription)
            events = (await db.execute(select(AIUsageEvent))).scalars().all()
            self.assertEqual(result["credits_charged"], 1)
            self.assertEqual(result["usage"]["total_tokens"], 33)
            self.assertEqual(subscription.credits_used, 1)
            self.assertEqual(len(events), 2)
        await engine.dispose()


if __name__ == "__main__":
    unittest.main()
