from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_authenticated_user, get_db
from app.models.commercial_model import AIUsageEvent, PaymentOrder, SubscriptionPlan
from app.models.user_model import User
from app.schemas.commercial_schema import OrderCreate
from app.services.commercial_service import (
    create_order,
    ensure_active_subscription,
    plan_dict,
    subscription_dict,
)

router = APIRouter(prefix="/api/commercial", tags=["commercial"])


@router.get("/plans")
async def list_plans(db: AsyncSession = Depends(get_db)):
    plans = (
        await db.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.is_current.is_(True), SubscriptionPlan.is_active.is_(True))
            .order_by(SubscriptionPlan.price_paise)
        )
    ).scalars().all()
    return [plan_dict(plan) for plan in plans]


@router.get("/me")
async def current_subscription(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_authenticated_user),
):
    subscription = await ensure_active_subscription(db, user.id)
    await db.commit()
    return subscription_dict(subscription)


@router.get("/usage")
async def usage_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_authenticated_user),
):
    subscription = await ensure_active_subscription(db, user.id)
    totals = (
        await db.execute(
            select(
                func.coalesce(func.sum(AIUsageEvent.prompt_tokens), 0),
                func.coalesce(func.sum(AIUsageEvent.completion_tokens), 0),
                func.coalesce(func.sum(AIUsageEvent.total_tokens), 0),
                func.coalesce(func.sum(AIUsageEvent.estimated_cost_micropaise), 0),
            ).where(AIUsageEvent.user_id == user.id)
        )
    ).one()
    await db.commit()
    return {
        "subscription": subscription_dict(subscription),
        "prompt_tokens": totals[0],
        "completion_tokens": totals[1],
        "total_tokens": totals[2],
        "estimated_cost_paise": round(totals[3] / 1_000_000, 2),
    }


@router.post("/orders")
async def new_order(
    body: OrderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_authenticated_user),
):
    plan = await db.get(SubscriptionPlan, body.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    try:
        order = await create_order(db, user.id, plan)
        await db.commit()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {
        "id": order.id,
        "order_reference": order.order_reference,
        "amount_paise": order.amount_paise,
        "currency": order.currency,
        "status": order.status,
        "checkout_available": False,
        "message": "Order created. An administrator must verify payment until a live payment gateway is configured.",
    }


@router.get("/orders")
async def my_orders(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_authenticated_user),
):
    orders = (
        await db.execute(
            select(PaymentOrder).where(PaymentOrder.user_id == user.id).order_by(PaymentOrder.id.desc())
        )
    ).scalars().all()
    return [
        {
            "id": item.id,
            "order_reference": item.order_reference,
            "amount_paise": item.amount_paise,
            "currency": item.currency,
            "status": item.status,
            "created_at": item.created_at.isoformat(),
            "paid_at": item.paid_at.isoformat() if item.paid_at else None,
        }
        for item in orders
    ]
