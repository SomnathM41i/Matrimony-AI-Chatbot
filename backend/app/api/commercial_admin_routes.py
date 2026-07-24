import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.gateway import call_ai, test_ai_model
from app.dependencies import get_db, require_admin
from app.models.commercial_model import (
    AIModel,
    AIProvider,
    AITaskRoute,
    AITaskTarget,
    AIUsageEvent,
    AdminAuditEvent,
    PaymentOrder,
    PaymentGateway,
    Subscription,
    SubscriptionPlan,
)
from app.models.user_model import User
from app.schemas.commercial_schema import (
    ManualPaymentConfirm,
    GatewayInput,
    ModelInput,
    PlanInput,
    ProviderInput,
    RouteInput,
    SubscriptionAssignment,
    SubscriptionAdminUpdate,
)
from app.services.commercial_service import (
    activate_order,
    add_audit,
    commercial_summary,
    create_subscription,
    plan_dict,
    subscription_dict,
)

router = APIRouter(prefix="/api/admin/commercial", tags=["admin-commercial"])


def provider_dict(item: AIProvider) -> dict:
    return {
        "id": item.id, "code": item.code, "name": item.name,
        "adapter_type": item.adapter_type, "base_url": item.base_url,
        "api_key_env": item.api_key_env, "enabled": item.enabled,
        "verify_ssl": item.verify_ssl, "timeout_seconds": item.timeout_seconds,
        "retry_count": item.retry_count,
    }


def model_dict(item: AIModel) -> dict:
    return {
        "id": item.id, "provider_id": item.provider_id,
        "provider_code": item.provider.code if item.provider else None,
        "external_id": item.external_id, "display_name": item.display_name,
        "context_window": item.context_window, "max_output_tokens": item.max_output_tokens,
        "supports_json": item.supports_json, "supports_sql": item.supports_sql,
        "input_cost_paise_per_million": item.input_cost_paise_per_million,
        "output_cost_paise_per_million": item.output_cost_paise_per_million,
        "enabled": item.enabled,
    }


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    return await commercial_summary(db)


@router.get("/plans")
async def plans(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    items = (await db.execute(select(SubscriptionPlan).order_by(SubscriptionPlan.code, SubscriptionPlan.version.desc()))).scalars().all()
    return [plan_dict(item) for item in items]


@router.post("/plans")
async def create_plan(body: PlanInput, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    code = body.code.strip().upper()
    latest = (
        await db.execute(select(func.max(SubscriptionPlan.version)).where(SubscriptionPlan.code == code))
    ).scalar() or 0
    current = (
        await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.code == code, SubscriptionPlan.is_current.is_(True)))
    ).scalars().all()
    for item in current:
        item.is_current = False
    plan = SubscriptionPlan(**body.model_dump(exclude={"code"}), code=code, version=latest + 1, is_current=True)
    db.add(plan)
    await db.flush()
    await add_audit(db, admin.id, "plan.version_created", "subscription_plan", plan.id, after=plan_dict(plan))
    await db.commit()
    return plan_dict(plan)


@router.get("/providers")
async def providers(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    items = (await db.execute(select(AIProvider).order_by(AIProvider.id))).scalars().all()
    return [provider_dict(item) for item in items]


@router.post("/providers")
async def create_provider(body: ProviderInput, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    values = body.model_dump()
    values["code"] = body.code.strip().lower()
    item = AIProvider(**values)
    db.add(item)
    await db.flush()
    await add_audit(db, admin.id, "provider.created", "ai_provider", item.id, after=provider_dict(item))
    await db.commit()
    return provider_dict(item)


@router.patch("/providers/{provider_id}")
async def update_provider(provider_id: int, body: ProviderInput, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    item = await db.get(AIProvider, provider_id)
    if not item:
        raise HTTPException(status_code=404, detail="Provider not found")
    before = provider_dict(item)
    for key, value in body.model_dump().items():
        setattr(item, key, value.strip().lower() if key == "code" else value)
    await db.flush()
    await add_audit(db, admin.id, "provider.updated", "ai_provider", item.id, before, provider_dict(item))
    await db.commit()
    return provider_dict(item)


@router.get("/models")
async def models(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    items = (await db.execute(select(AIModel).options(selectinload(AIModel.provider)).order_by(AIModel.id))).scalars().all()
    return [model_dict(item) for item in items]


@router.post("/models")
async def create_model(body: ModelInput, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    provider = await db.get(AIProvider, body.provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    item = AIModel(**body.model_dump())
    item.provider = provider
    db.add(item)
    await db.flush()
    await add_audit(db, admin.id, "model.created", "ai_model", item.id, after=model_dict(item))
    await db.commit()
    return model_dict(item)


@router.patch("/models/{model_id}")
async def update_model(model_id: int, body: ModelInput, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    item = await db.get(AIModel, model_id)
    if not item:
        raise HTTPException(status_code=404, detail="Model not found")
    provider = await db.get(AIProvider, item.provider_id)
    item.provider = provider
    before = model_dict(item)
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    item.provider = await db.get(AIProvider, body.provider_id)
    await db.flush()
    await add_audit(db, admin.id, "model.updated", "ai_model", item.id, before, model_dict(item))
    await db.commit()
    return model_dict(item)


@router.post("/models/{model_id}/test")
async def test_model(model_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    item = (
        await db.execute(select(AIModel).options(selectinload(AIModel.provider)).where(AIModel.id == model_id))
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Model not found")
    return await test_ai_model(item.provider, item)


@router.get("/routes")
async def routes(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    items = (
        await db.execute(select(AITaskRoute).options(selectinload(AITaskRoute.targets).selectinload(AITaskTarget.model)).order_by(AITaskRoute.task_key))
    ).scalars().all()
    return [
        {
            "id": item.id,
            "task_key": item.task_key,
            "enabled": item.enabled,
            "targets": [
                {"model_id": target.model_id, "model_name": target.model.display_name, "priority": target.priority}
                for target in item.targets if target.enabled
            ],
        }
        for item in items
    ]


@router.put("/routes/{task_key}")
async def publish_route(task_key: str, body: RouteInput, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    if task_key != body.task_key:
        raise HTTPException(status_code=400, detail="Task key mismatch")
    selected = (await db.execute(select(AIModel).where(AIModel.id.in_(body.model_ids)))).scalars().all()
    models_by_id = {item.id: item for item in selected}
    if len(models_by_id) != len(set(body.model_ids)):
        raise HTTPException(status_code=400, detail="One or more models do not exist")
    if any(not models_by_id[item].enabled for item in body.model_ids):
        raise HTTPException(status_code=400, detail="Disabled models cannot be published in an active route")
    provider_ids = {item.provider_id for item in selected}
    enabled_provider_ids = set(
        (await db.execute(select(AIProvider.id).where(AIProvider.id.in_(provider_ids), AIProvider.enabled.is_(True)))).scalars().all()
    )
    if enabled_provider_ids != provider_ids:
        raise HTTPException(status_code=400, detail="All route models must belong to enabled providers")
    if task_key in {"intent_detection", "sql_generation"} and any(not models_by_id[item].supports_json for item in body.model_ids):
        raise HTTPException(status_code=400, detail="All models for this task must support JSON output")
    if task_key == "sql_generation" and any(not models_by_id[item].supports_sql for item in body.model_ids):
        raise HTTPException(status_code=400, detail="All SQL-generation models must support SQL")
    route = (await db.execute(select(AITaskRoute).where(AITaskRoute.task_key == task_key))).scalar_one_or_none()
    if not route:
        route = AITaskRoute(task_key=task_key)
        db.add(route)
        await db.flush()
    before_targets = (await db.execute(select(AITaskTarget).where(AITaskTarget.route_id == route.id))).scalars().all()
    before = {"task_key": task_key, "model_ids": [item.model_id for item in before_targets]}
    await db.execute(delete(AITaskTarget).where(AITaskTarget.route_id == route.id))
    route.enabled = body.enabled
    for priority, model_id in enumerate(body.model_ids, 1):
        db.add(AITaskTarget(route_id=route.id, model_id=model_id, priority=priority, enabled=True))
    await add_audit(db, admin.id, "route.published", "ai_task_route", route.id, before, body.model_dump())
    await db.commit()
    return {"success": True, "task_key": task_key, "model_ids": body.model_ids}


@router.post("/routes/{task_key}/test")
async def test_route(task_key: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    result = await call_ai(
        db, task_key,
        [{"role": "system", "content": "Return a concise test response."}, {"role": "user", "content": "Reply with OK."}],
        temperature=0, max_tokens=20,
    )
    return {"content": result["content"], "events": result.get("events", [])}


@router.get("/subscriptions")
async def subscriptions(
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin),
):
    rows = (
        await db.execute(
            select(Subscription, User).join(User, Subscription.user_id == User.id)
            .order_by(Subscription.id.desc()).offset((page - 1) * per_page).limit(per_page)
        )
    ).all()
    return [{**subscription_dict(sub), "user_id": user.id, "user_name": user.name, "user_email": user.email} for sub, user in rows]


@router.post("/users/{user_id}/subscription")
async def assign_subscription(user_id: int, body: SubscriptionAssignment, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    if not await db.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    plan = await db.get(SubscriptionPlan, body.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(status_code=404, detail="Active plan not found")
    active = (await db.execute(select(Subscription).where(Subscription.user_id == user_id, Subscription.status == "active"))).scalars().all()
    for item in active:
        item.status = "replaced_by_admin"
    start = body.starts_at or datetime.now(timezone.utc)
    item = create_subscription(user_id, plan, start)
    db.add(item)
    await db.flush()
    await add_audit(db, admin.id, "subscription.assigned", "subscription", item.id, after=subscription_dict(item))
    await db.commit()
    return subscription_dict(item)


@router.patch("/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: int,
    body: SubscriptionAdminUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = await db.get(Subscription, subscription_id)
    if not item:
        raise HTTPException(status_code=404, detail="Subscription not found")
    before = subscription_dict(item)
    if body.status is not None:
        allowed = {"active", "cancelled", "expired", "suspended"}
        if body.status not in allowed:
            raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(sorted(allowed))}")
        item.status = body.status
    if body.credits_delta:
        item.credits_allocated = max(item.credits_used, item.credits_allocated + body.credits_delta)
    if body.extend_days:
        item.expires_at = item.expires_at + timedelta(days=body.extend_days)
    if body.daily_message_limit is not None:
        item.daily_message_limit = body.daily_message_limit
    await db.flush()
    await add_audit(db, admin.id, "subscription.updated", "subscription", item.id, before, subscription_dict(item))
    await db.commit()
    return subscription_dict(item)


@router.get("/orders")
async def orders(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    rows = (
        await db.execute(select(PaymentOrder, User).join(User, PaymentOrder.user_id == User.id).order_by(PaymentOrder.id.desc()).limit(200))
    ).all()
    return [
        {"id": order.id, "order_reference": order.order_reference, "user_id": user.id,
         "user_name": user.name, "plan_id": order.plan_id, "amount_paise": order.amount_paise,
         "currency": order.currency, "status": order.status, "created_at": order.created_at.isoformat()}
        for order, user in rows
    ]


def gateway_dict(item: PaymentGateway) -> dict:
    return {
        "id": item.id, "code": item.code, "name": item.name,
        "adapter_type": item.adapter_type, "key_id_env": item.key_id_env,
        "secret_env": item.secret_env, "webhook_secret_env": item.webhook_secret_env,
        "enabled": item.enabled,
    }


@router.get("/gateways")
async def gateways(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    items = (await db.execute(select(PaymentGateway).order_by(PaymentGateway.id))).scalars().all()
    return [gateway_dict(item) for item in items]


@router.post("/gateways")
async def create_gateway(body: GatewayInput, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    values = body.model_dump()
    values["code"] = body.code.strip().lower()
    item = PaymentGateway(**values)
    db.add(item)
    await db.flush()
    await add_audit(db, admin.id, "payment_gateway.created", "payment_gateway", item.id, after=gateway_dict(item))
    await db.commit()
    return gateway_dict(item)


@router.patch("/gateways/{gateway_id}")
async def update_gateway(gateway_id: int, body: GatewayInput, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    item = await db.get(PaymentGateway, gateway_id)
    if not item:
        raise HTTPException(status_code=404, detail="Gateway not found")
    before = gateway_dict(item)
    for key, value in body.model_dump().items():
        setattr(item, key, value.strip().lower() if key == "code" else value)
    await add_audit(db, admin.id, "payment_gateway.updated", "payment_gateway", item.id, before, gateway_dict(item))
    await db.commit()
    return gateway_dict(item)


@router.post("/orders/{order_id}/confirm")
async def confirm_order(order_id: int, body: ManualPaymentConfirm, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    order = await db.get(PaymentOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in {"pending", "paid"}:
        raise HTTPException(status_code=400, detail="Order cannot be confirmed")
    subscription = await activate_order(db, order, body.provider_payment_id)
    await add_audit(db, admin.id, "payment.manually_confirmed", "payment_order", order.id, after={"payment_reference": body.provider_payment_id})
    await db.commit()
    return {"order_id": order.id, "status": order.status, "subscription": subscription_dict(subscription)}


@router.get("/usage")
async def usage(
    page: int = Query(1, ge=1), per_page: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin),
):
    items = (
        await db.execute(select(AIUsageEvent).order_by(AIUsageEvent.id.desc()).offset((page - 1) * per_page).limit(per_page))
    ).scalars().all()
    return [
        {"id": item.id, "request_id": item.request_id, "user_id": item.user_id,
         "task_key": item.task_key, "request_type": item.request_type,
         "provider_code": item.provider_code, "model_external_id": item.model_external_id,
         "prompt_tokens": item.prompt_tokens, "completion_tokens": item.completion_tokens,
         "total_tokens": item.total_tokens,
         "estimated_cost_paise": round(item.estimated_cost_micropaise / 1_000_000, 4),
         "latency_ms": item.latency_ms, "created_at": item.created_at.isoformat()}
        for item in items
    ]


@router.get("/audit")
async def audit(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    items = (await db.execute(select(AdminAuditEvent).order_by(AdminAuditEvent.id.desc()).limit(200))).scalars().all()
    return [
        {"id": item.id, "admin_user_id": item.admin_user_id, "action": item.action,
         "entity_type": item.entity_type, "entity_id": item.entity_id,
         "before": json.loads(item.before_json) if item.before_json else None,
         "after": json.loads(item.after_json) if item.after_json else None,
         "created_at": item.created_at.isoformat()}
        for item in items
    ]
