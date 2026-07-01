import httpx
import certifi
from app.config import settings
from app.core.logger import logger


async def call_groq(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.5,
    max_tokens: int = 1200,
) -> str:
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured")

    verify = certifi.where() if settings.GROQ_VERIFY_SSL else False

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
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def call_llm(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.5,
    max_tokens: int = 1200,
) -> str:
    messages = [
        {"role": "system", "content": system_prompt[:3000]},
        {"role": "user", "content": user_message[:5000]},
    ]
    try:
        return await call_groq(messages, temperature=temperature, max_tokens=max_tokens)
    except httpx.TimeoutException:
        return "Request timed out. Please try again with a simpler question."
    except Exception as e:
        logger.error(f"LLM call error: {e}")
        return f"Error communicating with AI: {str(e)}"
