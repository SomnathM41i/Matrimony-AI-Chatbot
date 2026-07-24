import json
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.commercial_model import (
    AIModel,
    AIProvider,
    AITaskRoute,
    AITaskTarget,
    AIUsageEvent,
    AdminAuditEvent,
    PaymentGateway,
    PaymentOrder,
    Subscription,
    SubscriptionPlan,
    UsageReservation,
)


def utcnow():
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class CommercialLimitError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 402):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def plan_dict(plan: SubscriptionPlan) -> dict:
    return {
        "id": plan.id,
        "code": plan.code,
        "version": plan.version,
        "name": plan.name,
        "description": plan.description,
        "price_paise": plan.price_paise,
        "currency": plan.currency,
        "duration_days": plan.duration_days,
        "ai_credits": plan.ai_credits,
        "daily_message_limit": plan.daily_message_limit,
        "contact_limit": plan.contact_limit,
        "normal_credit_cost": plan.normal_credit_cost,
        "database_credit_cost": plan.database_credit_cost,
        "is_active": plan.is_active,
        "is_current": plan.is_current,
    }


def subscription_dict(subscription: Subscription) -> dict:
    remaining = max(0, subscription.credits_allocated - subscription.credits_used)
    daily_remaining = max(0, subscription.daily_message_limit - subscription.daily_messages_used)
    return {
        "id": subscription.id,
        "plan_id": subscription.plan_id,
        "plan_code": subscription.plan_code,
        "plan_name": subscription.plan_name,
        "status": subscription.status,
        "credits_allocated": subscription.credits_allocated,
        "credits_used": subscription.credits_used,
        "credits_remaining": remaining,
        "daily_message_limit": subscription.daily_message_limit,
        "daily_messages_used": subscription.daily_messages_used,
        "daily_messages_remaining": daily_remaining,
        "contact_limit": subscription.contact_limit,
        "started_at": subscription.started_at.isoformat(),
        "expires_at": subscription.expires_at.isoformat(),
    }


async def seed_commercial_defaults(db: AsyncSession) -> None:
    provider = (await db.execute(select(AIProvider).where(AIProvider.code == "groq"))).scalar_one_or_none()
    if not provider:
        provider = AIProvider(
            code="groq",
            name="Groq",
            adapter_type="openai_compatible",
            base_url=settings.GROQ_API_URL,
            api_key_env="GROQ_API_KEY",
            enabled=True,
            verify_ssl=settings.GROQ_VERIFY_SSL,
            timeout_seconds=settings.LLM_TIMEOUT,
            retry_count=settings.LLM_MAX_RETRIES,
        )
        db.add(provider)
        await db.flush()

    model_specs = [
        ("llama-3.3-70b-versatile", "Llama 3.3 70B Versatile", 131072, 32768, 5700, 7600),
        ("llama-3.1-8b-instant", "Llama 3.1 8B Instant", 131072, 8192, 500, 800),
    ]
    models = {}
    for external_id, name, context, output, input_cost, output_cost in model_specs:
        model = (
            await db.execute(
                select(AIModel).where(
                    AIModel.provider_id == provider.id,
                    AIModel.external_id == external_id,
                )
            )
        ).scalar_one_or_none()
        if not model:
            model = AIModel(
                provider_id=provider.id,
                external_id=external_id,
                display_name=name,
                context_window=context,
                max_output_tokens=output,
                supports_json=True,
                supports_sql=True,
                input_cost_paise_per_million=input_cost,
                output_cost_paise_per_million=output_cost,
                enabled=True,
            )
            db.add(model)
            await db.flush()
        models[external_id] = model

    route_models = {
        "intent_detection": [models["llama-3.1-8b-instant"]],
        "general_chat": [models["llama-3.3-70b-versatile"], models["llama-3.1-8b-instant"]],
        "sql_generation": [models["llama-3.3-70b-versatile"]],
        "database_formatting": [models["llama-3.3-70b-versatile"], models["llama-3.1-8b-instant"]],
        "database_notice": [models["llama-3.1-8b-instant"], models["llama-3.3-70b-versatile"]],
    }
    for task_key, target_models in route_models.items():
        route = (await db.execute(select(AITaskRoute).where(AITaskRoute.task_key == task_key))).scalar_one_or_none()
        if not route:
            route = AITaskRoute(task_key=task_key, enabled=True)
            db.add(route)
            await db.flush()
            for priority, model in enumerate(target_models, 1):
                db.add(AITaskTarget(route_id=route.id, model_id=model.id, priority=priority, enabled=True))

    plans = [
        dict(code="FREE", name="Free", description="Explore the AI matchmaker", price_paise=0, duration_days=30, ai_credits=50, daily_message_limit=10, contact_limit=0),
        dict(code="BASIC", name="Basic", description="AI matchmaking with 30 contacts", price_paise=249900, duration_days=30, ai_credits=500, daily_message_limit=200, contact_limit=30),
        dict(code="SILVER", name="Silver", description="Extended AI matchmaking with 60 contacts", price_paise=499900, duration_days=60, ai_credits=1500, daily_message_limit=200, contact_limit=60),
    ]
    for spec in plans:
        exists = (
            await db.execute(
                select(SubscriptionPlan).where(
                    SubscriptionPlan.code == spec["code"],
                    SubscriptionPlan.is_current.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not exists:
            db.add(SubscriptionPlan(**spec, version=1, currency="INR", normal_credit_cost=1, database_credit_cost=2))

    gateway = (await db.execute(select(PaymentGateway).where(PaymentGateway.code == "manual"))).scalar_one_or_none()
    if not gateway:
        db.add(PaymentGateway(code="manual", name="Manual admin verification", adapter_type="manual", enabled=True))
    await db.commit()


async def ensure_active_subscription(db: AsyncSession, user_id: int) -> Subscription:
    current = (
        await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id, Subscription.status == "active")
            .order_by(Subscription.expires_at.desc())
        )
    ).scalars().first()
    now = utcnow()
    if current and _aware(current.expires_at) > now:
        if current.daily_reset_date != date.today():
            current.daily_reset_date = date.today()
            current.daily_messages_used = 0
            await db.flush()
        return current
    if current:
        current.status = "expired"

    free_plan = (
        await db.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.code == "FREE",
                SubscriptionPlan.is_current.is_(True),
                SubscriptionPlan.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not free_plan:
        raise CommercialLimitError("subscription_unavailable", "No active subscription plan is available.", 503)
    subscription = create_subscription(user_id, free_plan, now)
    db.add(subscription)
    await db.flush()
    return subscription


def create_subscription(user_id: int, plan: SubscriptionPlan, start: datetime | None = None) -> Subscription:
    start = start or utcnow()
    return Subscription(
        user_id=user_id,
        plan_id=plan.id,
        status="active",
        plan_code=plan.code,
        plan_name=plan.name,
        price_paid_paise=plan.price_paise,
        credits_allocated=plan.ai_credits,
        credits_used=0,
        daily_message_limit=plan.daily_message_limit,
        daily_messages_used=0,
        daily_reset_date=date.today(),
        normal_credit_cost=plan.normal_credit_cost,
        database_credit_cost=plan.database_credit_cost,
        contact_limit=plan.contact_limit,
        started_at=start,
        expires_at=start + timedelta(days=plan.duration_days),
    )


async def reserve_usage(db: AsyncSession, user_id: int, request_id: str) -> tuple[UsageReservation, Subscription]:
    subscription = await ensure_active_subscription(db, user_id)
    reserve = max(subscription.normal_credit_cost, subscription.database_credit_cost)
    conditions = [
        Subscription.id == subscription.id,
        Subscription.status == "active",
        Subscription.credits_used + reserve <= Subscription.credits_allocated,
    ]
    if subscription.daily_message_limit:
        conditions.append(Subscription.daily_messages_used < Subscription.daily_message_limit)
    updated = await db.execute(
        update(Subscription)
        .where(*conditions)
        .values(
            credits_used=Subscription.credits_used + reserve,
            daily_messages_used=Subscription.daily_messages_used + 1,
        )
        .execution_options(synchronize_session=False)
    )
    if updated.rowcount != 1:
        await db.refresh(subscription)
        if subscription.daily_message_limit and subscription.daily_messages_used >= subscription.daily_message_limit:
            raise CommercialLimitError("daily_limit_reached", "Your daily AI message limit has been reached.", 429)
        raise CommercialLimitError("credits_exhausted", "Your AI credits are exhausted. Please upgrade or renew your plan.")
    await db.refresh(subscription)
    reservation = UsageReservation(
        request_id=request_id,
        user_id=user_id,
        subscription_id=subscription.id,
        reserved_credits=reserve,
    )
    db.add(reservation)
    await db.flush()
    return reservation, subscription


async def finalize_usage(db: AsyncSession, request_id: str, request_type: str, success: bool) -> int:
    reservation = (
        await db.execute(select(UsageReservation).where(UsageReservation.request_id == request_id))
    ).scalar_one_or_none()
    if not reservation or reservation.status != "reserved":
        return reservation.charged_credits if reservation else 0
    claimed = await db.execute(
        update(UsageReservation)
        .where(UsageReservation.id == reservation.id, UsageReservation.status == "reserved")
        .values(status="finalizing")
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        await db.refresh(reservation)
        return reservation.charged_credits
    await db.refresh(reservation)
    subscription = await db.get(Subscription, reservation.subscription_id)
    if success:
        charge = subscription.database_credit_cost if request_type == "database" else subscription.normal_credit_cost
        charge = min(charge, reservation.reserved_credits)
        subscription.credits_used -= reservation.reserved_credits - charge
        reservation.status = "charged"
        reservation.charged_credits = charge
    else:
        subscription.credits_used = max(0, subscription.credits_used - reservation.reserved_credits)
        subscription.daily_messages_used = max(0, subscription.daily_messages_used - 1)
        reservation.status = "released"
        reservation.charged_credits = 0
    reservation.finalized_at = utcnow()
    await db.flush()
    return reservation.charged_credits


async def record_usage_events(
    db: AsyncSession,
    request_id: str,
    user_id: int,
    subscription_id: int,
    conversation_id: int,
    request_type: str,
    events: list[dict],
) -> None:
    for event in events:
        db.add(AIUsageEvent(
            request_id=request_id,
            user_id=user_id,
            subscription_id=subscription_id,
            conversation_id=conversation_id,
            task_key=event.get("task_key", "unknown"),
            request_type=request_type,
            provider_code=event.get("provider_code", "unknown"),
            model_external_id=event.get("model_external_id", "unknown"),
            prompt_tokens=event.get("prompt_tokens", 0) or 0,
            completion_tokens=event.get("completion_tokens", 0) or 0,
            total_tokens=event.get("total_tokens", 0) or 0,
            estimated_cost_micropaise=event.get("estimated_cost_micropaise", 0) or 0,
            latency_ms=event.get("latency_ms", 0) or 0,
            provider_request_id=event.get("provider_request_id"),
            status=event.get("status", "success"),
        ))
    await db.flush()


async def create_order(db: AsyncSession, user_id: int, plan: SubscriptionPlan) -> PaymentOrder:
    if not plan.is_active or not plan.is_current or plan.code == "FREE":
        raise ValueError("This plan cannot be purchased")
    gateway = (
        await db.execute(select(PaymentGateway).where(PaymentGateway.enabled.is_(True)).order_by(PaymentGateway.id))
    ).scalars().first()
    snapshot = plan_dict(plan)
    order = PaymentOrder(
        order_reference=f"MVV-{uuid.uuid4().hex[:16].upper()}",
        user_id=user_id,
        plan_id=plan.id,
        gateway_id=gateway.id if gateway else None,
        amount_paise=plan.price_paise,
        currency=plan.currency,
        status="pending",
        plan_snapshot_json=json.dumps(snapshot),
    )
    db.add(order)
    await db.flush()
    return order


async def activate_order(db: AsyncSession, order: PaymentOrder, payment_reference: str) -> Subscription:
    if order.status == "paid":
        existing = (
            await db.execute(
                select(Subscription).where(
                    Subscription.user_id == order.user_id,
                    Subscription.plan_id == order.plan_id,
                    Subscription.started_at >= order.paid_at,
                )
            )
        ).scalars().first()
        if existing:
            return existing
    plan = await db.get(SubscriptionPlan, order.plan_id)
    active = (
        await db.execute(
            select(Subscription).where(Subscription.user_id == order.user_id, Subscription.status == "active")
        )
    ).scalars().all()
    now = utcnow()
    for item in active:
        if _aware(item.expires_at) > now and item.plan_code != "FREE":
            item.status = "replaced"
        elif item.plan_code == "FREE":
            item.status = "upgraded"
    subscription = create_subscription(order.user_id, plan, now)
    db.add(subscription)
    order.status = "paid"
    order.provider_payment_id = payment_reference
    order.paid_at = now
    await db.flush()
    return subscription


async def add_audit(
    db: AsyncSession,
    admin_user_id: int,
    action: str,
    entity_type: str,
    entity_id: int | str,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    db.add(AdminAuditEvent(
        admin_user_id=admin_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        before_json=json.dumps(before, default=str) if before is not None else None,
        after_json=json.dumps(after, default=str) if after is not None else None,
    ))
    await db.flush()


async def commercial_summary(db: AsyncSession) -> dict:
    active_subscriptions = (
        await db.execute(select(func.count(Subscription.id)).where(Subscription.status == "active"))
    ).scalar() or 0
    paid_revenue = (
        await db.execute(select(func.coalesce(func.sum(PaymentOrder.amount_paise), 0)).where(PaymentOrder.status == "paid"))
    ).scalar() or 0
    total_tokens = (await db.execute(select(func.coalesce(func.sum(AIUsageEvent.total_tokens), 0)))).scalar() or 0
    cost_micropaise = (
        await db.execute(select(func.coalesce(func.sum(AIUsageEvent.estimated_cost_micropaise), 0)))
    ).scalar() or 0
    return {
        "active_subscriptions": active_subscriptions,
        "revenue_paise": paid_revenue,
        "total_tokens": total_tokens,
        "estimated_cost_paise": round(cost_micropaise / 1_000_000, 2),
    }
