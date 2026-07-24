import asyncio
import os
import random
import time

import certifi
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.commercial_model import AIModel, AIProvider, AITaskRoute, AITaskTarget
from app.core.logger import logger


class AIConfigurationError(RuntimeError):
    pass


class AIProviderUnavailableError(RuntimeError):
    pass


def _secret_value(name: str) -> str:
    if not name:
        return ""
    configured = getattr(settings, name, "")
    return configured or os.getenv(name, "")


def _event(task_key: str, provider: AIProvider, model: AIModel, data: dict, latency_ms: int) -> dict:
    usage = data.get("usage", {}) or {}
    prompt = usage.get("prompt_tokens", 0) or 0
    completion = usage.get("completion_tokens", 0) or 0
    total = usage.get("total_tokens", prompt + completion) or prompt + completion
    return {
        "task_key": task_key,
        "provider_code": provider.code,
        "model_external_id": model.external_id,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        # tokens * paise-per-million equals micro-paise.
        "estimated_cost_micropaise": (
            prompt * model.input_cost_paise_per_million
            + completion * model.output_cost_paise_per_million
        ),
        "latency_ms": latency_ms,
        "provider_request_id": data.get("id"),
        "status": "success",
    }


async def _load_targets(db: AsyncSession, task_key: str) -> list[tuple[AITaskTarget, AIModel, AIProvider]]:
    route = (
        await db.execute(
            select(AITaskRoute)
            .options(
                selectinload(AITaskRoute.targets)
                .selectinload(AITaskTarget.model)
                .selectinload(AIModel.provider)
            )
            .where(AITaskRoute.task_key == task_key, AITaskRoute.enabled.is_(True))
        )
    ).scalar_one_or_none()
    if not route:
        raise AIConfigurationError(f"No published AI route for task: {task_key}")
    return [
        (target, target.model, target.model.provider)
        for target in route.targets
        if target.enabled and target.model.enabled and target.model.provider.enabled
    ]


async def _openai_compatible_request(
    provider: AIProvider,
    model: AIModel,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
) -> tuple[dict, int]:
    api_key = _secret_value(provider.api_key_env)
    if provider.api_key_env and not api_key:
        raise AIConfigurationError(f"Secret {provider.api_key_env} is not configured")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model.external_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": min(max_tokens, model.max_output_tokens),
    }
    verify = certifi.where() if provider.verify_ssl else False
    retryable = {429, 500, 502, 503, 504}
    started = time.perf_counter()
    for attempt in range(provider.retry_count + 1):
        try:
            async with httpx.AsyncClient(timeout=provider.timeout_seconds, verify=verify) as client:
                response = await client.post(provider.base_url, json=payload, headers=headers)
            if response.status_code in retryable and attempt < provider.retry_count:
                await asyncio.sleep((2 ** attempt) + random.random())
                continue
            response.raise_for_status()
            return response.json(), int((time.perf_counter() - started) * 1000)
        except httpx.TimeoutException:
            if attempt < provider.retry_count:
                await asyncio.sleep((2 ** attempt) + random.random())
                continue
            raise
    raise AIProviderUnavailableError(f"Provider {provider.code} did not return a response")


async def call_ai(
    db: AsyncSession,
    task_key: str,
    messages: list[dict],
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict:
    targets = await _load_targets(db, task_key)
    if not targets:
        raise AIConfigurationError(f"No enabled model target for task: {task_key}")
    last_error: Exception | None = None
    for _, model, provider in targets:
        try:
            approximate_input_tokens = sum(
                max(1, len(str(message.get("content", ""))) // 4)
                for message in messages
            )
            requested_output = min(
                max_tokens if max_tokens is not None else settings.DEFAULT_MAX_TOKENS,
                model.max_output_tokens,
            )
            if approximate_input_tokens + requested_output > model.context_window:
                last_error = AIConfigurationError(
                    f"Model {model.external_id} context window is too small for task {task_key}"
                )
                logger.warning(
                    "Skipping AI route target with insufficient context task=%s model=%s",
                    task_key, model.external_id,
                )
                continue
            if provider.adapter_type not in {"openai_compatible", "groq", "ollama"}:
                raise AIConfigurationError(f"Unsupported AI adapter: {provider.adapter_type}")
            data, latency_ms = await _openai_compatible_request(
                provider,
                model,
                messages,
                temperature if temperature is not None else settings.DEFAULT_TEMPERATURE,
                max_tokens if max_tokens is not None else settings.DEFAULT_MAX_TOKENS,
            )
            content = data["choices"][0]["message"]["content"]
            event = _event(task_key, provider, model, data, latency_ms)
            return {"content": content, "usage": data.get("usage", {}), "events": [event]}
        except AIConfigurationError:
            raise
        except httpx.HTTPStatusError as error:
            if error.response.status_code not in {429, 500, 502, 503, 504}:
                raise AIConfigurationError(
                    f"Provider {provider.code} rejected the configured request"
                ) from error
            last_error = error
            logger.warning(
                "AI route target failed task=%s provider=%s model=%s status=%s",
                task_key, provider.code, model.external_id, error.response.status_code,
            )
            continue
        except (httpx.TimeoutException, AIProviderUnavailableError, KeyError, ValueError) as error:
            last_error = error
            logger.warning(
                "AI route target failed task=%s provider=%s model=%s error=%s",
                task_key,
                provider.code,
                model.external_id,
                type(error).__name__,
            )
            continue
    if last_error:
        raise last_error
    raise AIProviderUnavailableError(f"All providers failed for task: {task_key}")


async def test_ai_model(provider: AIProvider, model: AIModel) -> dict:
    data, latency_ms = await _openai_compatible_request(
        provider,
        model,
        [{"role": "system", "content": "This is a health check."}, {"role": "user", "content": "Reply with OK."}],
        0,
        20,
    )
    return {
        "content": data["choices"][0]["message"]["content"],
        "event": _event("model_health_check", provider, model, data, latency_ms),
    }
