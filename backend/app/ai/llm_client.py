import asyncio
import random
import httpx
import certifi
from app.config import settings
from app.core.logger import logger


RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRIES = 4
BASE_DELAY = 1.0


async def call_groq(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.5,
    max_tokens: int = 1200,
) -> dict:
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured")

    verify = certifi.where() if settings.GROQ_VERIFY_SSL else False
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=30, verify=verify) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={
                        "model": model or settings.GROQ_MODEL,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    headers={
                        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                )

                if resp.status_code == 429 and attempt < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** attempt) + random.random()
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
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2 ** attempt) + random.random()
                logger.warning(
                    f"Groq timeout (attempt {attempt + 1}), "
                    f"retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                continue
            raise

        except httpx.HTTPStatusError as e:
            if e.response.status_code in RETRYABLE_STATUSES and attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2 ** attempt) + random.random()
                logger.warning(
                    f"Groq {e.response.status_code} (attempt {attempt + 1}), "
                    f"retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                continue
            raise

    raise last_error or RuntimeError("Groq request failed after retries")


async def call_llm(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.5,
    max_tokens: int = 1200,
) -> dict:
    messages = [
        {"role": "system", "content": system_prompt[:3000]},
        {"role": "user", "content": user_message[:5000]},
    ]
    try:
        return await call_groq(messages, temperature=temperature, max_tokens=max_tokens)
    except httpx.TimeoutException:
        return {"content": "Request timed out. Please try again with a simpler question.", "usage": {}}
    except Exception as e:
        logger.error(f"LLM call error: {e}")
        return {"content": f"Error communicating with AI: {str(e)}", "usage": {}}
