import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import delete, select
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
)
from app.models.user_model import User
from app.services.commercial_service import add_audit

router = APIRouter(prefix="/api/admin/commercial", tags=["admin-commercial"])


class ProviderInput(BaseModel):
    code: str
    name: str
    adapter_type: str = "openai_compatible"
    base_url: str
    api_key_env: str = ""
    enabled: bool = True
    verify_ssl: bool = True
    timeout_seconds: int = 30
    retry_count: int = 2


class ModelInput(BaseModel):
    provider_id: int
    external_id: str
    display_name: str
    context_window: int = 8192
    max_output_tokens: int = 1200
    supports_json: bool = True
    supports_sql: bool = True
    input_cost_paise_per_million: int = 0
    output_cost_paise_per_million: int = 0
    enabled: bool = True


class RouteInput(BaseModel):
    task_key: str
    model_ids: List[int]
    enabled: bool = True


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


@router.get("/usage")
async def usage(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    items = (await db.execute(select(AIUsageEvent).order_by(AIUsageEvent.id.desc()).limit(200))).scalars().all()
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
