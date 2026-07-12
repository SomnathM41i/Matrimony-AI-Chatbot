import asyncio
import random
import httpx
import certifi
from app.config import settings
from app.core.logger import logger


class GroqPayloadTooLargeError(Exception):
    pass


async def call_groq(
    messages: list[dict],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict:
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured")

    _temperature = temperature if temperature is not None else settings.DEFAULT_TEMPERATURE
    _max_tokens = max_tokens if max_tokens is not None else settings.DEFAULT_MAX_TOKENS
    _max_retries = settings.LLM_MAX_RETRIES
    _base_delay = settings.LLM_BASE_DELAY
    _retryable = settings.retryable_statuses_set
    verify = certifi.where() if settings.GROQ_VERIFY_SSL else False

    for attempt in range(_max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT, verify=verify) as client:
                resp = await client.post(
                    settings.GROQ_API_URL,
                    json={
                        "model": model or settings.GROQ_MODEL,
                        "messages": messages,
                        "temperature": _temperature,
                        "max_tokens": _max_tokens,
                    },
                    headers={
                        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                )

                if resp.status_code == 413:
                    raise GroqPayloadTooLargeError(
                        "Payload too large for Groq API. Try narrowing your search criteria."
                    )

                if resp.status_code == 429 and attempt < _max_retries:
                    delay = _base_delay * (2 ** attempt) + random.random()
                    logger.warning(
                        f"Groq 429 rate limited (attempt {attempt + 1}), "
                        f"retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                    continue

                resp.raise_for_status()
                data = resp.json()
                return {
                    "content": data["choices"][0]["message"]["content"],
                    "usage": data.get("usage", {}),
                }

        except httpx.TimeoutException:
            if attempt < _max_retries:
                delay = _base_delay * (2 ** attempt) + random.random()
                logger.warning(
                    f"Groq timeout (attempt {attempt + 1}), "
                    f"retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                continue
            raise

        except httpx.HTTPStatusError as e:
            if e.response.status_code in _retryable and attempt < _max_retries:
                delay = _base_delay * (2 ** attempt) + random.random()
                logger.warning(
                    f"Groq {e.response.status_code} (attempt {attempt + 1}), "
                    f"retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                continue
            raise

    raise RuntimeError("Groq request failed after retries")


async def call_llm(
    system_prompt: str,
    user_message: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    history: list[dict] | None = None,
) -> dict:
    messages = [
        {"role": "system", "content": system_prompt[:settings.LLM_PROMPT_TRUNCATION]},
    ]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message[:settings.LLM_MESSAGE_TRUNCATION]})
    try:
        return await call_groq(messages, temperature=temperature, max_tokens=max_tokens)
    except httpx.TimeoutException:
        return {"content": "Request timed out. Please try again with a simpler question.", "usage": {}}
    except Exception as e:
        logger.error(f"LLM call error: {e}")
        return {"content": f"Error communicating with AI: {str(e)}", "usage": {}}
