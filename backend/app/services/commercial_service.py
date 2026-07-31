import json
from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.commercial_model import (
    AIModel,
    AIProvider,
    AITaskRoute,
    AITaskTarget,
    AIUsageEvent,
    AdminAuditEvent,
)


def utcnow():
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


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

    ollama_provider = (await db.execute(select(AIProvider).where(AIProvider.code == "ollama"))).scalar_one_or_none()
    if not ollama_provider:
        ollama_provider = AIProvider(
            code="ollama",
            name="Ollama (Local)",
            adapter_type="openai_compatible",
            base_url="http://localhost:11434/v1/chat/completions",
            api_key_env="",
            enabled=True,
            verify_ssl=False,
            timeout_seconds=120,
            retry_count=2,
        )
        db.add(ollama_provider)
        await db.flush()

    ollama_model = (await db.execute(
        select(AIModel).where(
            AIModel.provider_id == ollama_provider.id,
            AIModel.external_id == "qwen2.5:3b-instruct-q4_K_M",
        )
    )).scalar_one_or_none()
    if not ollama_model:
        ollama_model = AIModel(
            provider_id=ollama_provider.id,
            external_id="qwen2.5:3b-instruct-q4_K_M",
            display_name="Qwen 2.5 3B Instruct",
            context_window=32768,
            max_output_tokens=8192,
            supports_json=True,
            input_cost_paise_per_million=0,
            output_cost_paise_per_million=0,
            enabled=True,
        )
        db.add(ollama_model)
        await db.flush()

    cerebras_provider = (await db.execute(select(AIProvider).where(AIProvider.code == "cerebras"))).scalar_one_or_none()
    if not cerebras_provider:
        cerebras_provider = AIProvider(
            code="cerebras",
            name="Cerebras",
            adapter_type="openai_compatible",
            base_url=settings.CEREBRAS_API_URL,
            api_key_env="CEREBRAS_API_KEY",
            enabled=True,
            verify_ssl=True,
            timeout_seconds=60,
            retry_count=settings.LLM_MAX_RETRIES,
        )
        db.add(cerebras_provider)
        await db.flush()

    cerebras_model = (await db.execute(
        select(AIModel).where(
            AIModel.provider_id == cerebras_provider.id,
            AIModel.external_id == "llama-3.3-70b",
        )
    )).scalar_one_or_none()
    if not cerebras_model:
        cerebras_model = AIModel(
            provider_id=cerebras_provider.id,
            external_id="llama-3.3-70b",
            display_name="Llama 3.3 70B",
            context_window=131072,
            max_output_tokens=8192,
            supports_json=True,
            supports_sql=True,
            input_cost_paise_per_million=85,
            output_cost_paise_per_million=120,
            enabled=True,
        )
        db.add(cerebras_model)
        await db.flush()

    gemini_provider = (await db.execute(select(AIProvider).where(AIProvider.code == "gemini"))).scalar_one_or_none()
    if not gemini_provider:
        gemini_provider = AIProvider(
            code="gemini",
            name="Google Gemini",
            adapter_type="openai_compatible",
            base_url=settings.GEMINI_API_URL,
            api_key_env="GEMINI_API_KEY",
            enabled=True,
            verify_ssl=True,
            timeout_seconds=60,
            retry_count=settings.LLM_MAX_RETRIES,
        )
        db.add(gemini_provider)
        await db.flush()

    gemini_model = (await db.execute(
        select(AIModel).where(
            AIModel.provider_id == gemini_provider.id,
            AIModel.external_id == "gemini-2.5-flash",
        )
    )).scalar_one_or_none()
    if not gemini_model:
        gemini_model = AIModel(
            provider_id=gemini_provider.id,
            external_id="gemini-2.5-flash",
            display_name="Gemini 2.5 Flash",
            context_window=1000000,
            max_output_tokens=65536,
            supports_json=True,
            supports_sql=True,
            input_cost_paise_per_million=0,
            output_cost_paise_per_million=0,
            enabled=True,
        )
        db.add(gemini_model)
        await db.flush()

    groq_model = (await db.execute(
        select(AIModel).where(
            AIModel.provider_id == provider.id,
            AIModel.external_id == "llama-3.3-70b-versatile",
        )
    )).scalar_one_or_none()

    provider_model_map = {
        "ollama": ollama_model,
        "groq": groq_model,
        "cerebras": cerebras_model,
        "gemini": gemini_model,
    }
    active_model = provider_model_map.get(settings.LLM_PROVIDER) or groq_model

    TASK_KEYS = [
        "intent_detection", "general_chat", "sql_generation",
        "database_formatting", "database_notice",
    ]

    for task_key in TASK_KEYS:
        route = (await db.execute(select(AITaskRoute).where(AITaskRoute.task_key == task_key))).scalar_one_or_none()
        if not route:
            route = AITaskRoute(task_key=task_key, enabled=True)
            db.add(route)
            await db.flush()
        existing = (await db.execute(
            select(AITaskTarget).where(
                AITaskTarget.route_id == route.id,
                AITaskTarget.priority == 1,
            )
        )).scalar_one_or_none()
        if existing:
            existing.model_id = active_model.id
        else:
            db.add(AITaskTarget(route_id=route.id, model_id=active_model.id, priority=1, enabled=True))

    await db.commit()


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
