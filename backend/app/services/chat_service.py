from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.chat_repository import ChatRepository
from app.services.llm_service import get_general_response
from app.services.db_query_service import answer_database_question
from app.ai.intent_llm import detect_intent_with_llm
from app.core.logger import logger
from datetime import datetime, timezone
import httpx

HISTORY_LIMIT = 10


def user_facing_error(error: Exception) -> str:
    """Map internal/provider failures to safe, actionable chat messages."""
    if isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 429:
        return (
            "Sorry, the assistant is receiving many requests right now. "
            "Please wait a moment and try again."
        )
    if isinstance(error, httpx.TimeoutException):
        return "Sorry, the request took too long to process. Please try again."
    if isinstance(error, ValueError) and str(error) == "Could not convert request into a database query.":
        return (
            "Sorry, I couldn't understand that request in the current context. "
            "Please rephrase it—for example, ‘Translate the previous answer into Marathi’ "
            "or ‘Show 5 female profiles from Pune.’"
        )
    return "Sorry, I couldn't process your request right now. Please try again or rephrase it."


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conv_repo = ConversationRepository(db)
        self.msg_repo = ChatRepository(db)

    async def _load_history(self, conversation_id: int) -> list[dict]:
        msgs = await self.msg_repo.list_by_conversation(conversation_id)
        history = []
        for m in msgs[-HISTORY_LIMIT:]:
            history.append({"role": m.role, "content": m.content})
        return history

    async def process_message(
        self, user_id: int, message: str, conversation_id: int | None = None
    ) -> dict:
        if conversation_id:
            conv = await self.conv_repo.get_by_id(conversation_id)
            if not conv or conv.user_id != user_id:
                raise ValueError("Conversation not found")
        else:
            n = settings.CHAT_TITLE_TRUNCATION
            title = message[:n] + ("..." if len(message) > n else "")
            conv = await self.conv_repo.create(user_id=user_id, title=title)

        history = await self._load_history(conv.id)

        user_msg = await self.msg_repo.create(
            conversation_id=conv.id,
            user_id=user_id,
            role="user",
            content=message,
        )

        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        try:
            if await detect_intent_with_llm(message, history=history):
                result = await answer_database_question(message, history=history)
            else:
                result = await get_general_response(message, history=history)
            reply_text = result["content"]
            if result.get("usage"):
                u = result["usage"]
                usage = {
                    "prompt_tokens": usage["prompt_tokens"] + (u.get("prompt_tokens", 0) or 0),
                    "completion_tokens": usage["completion_tokens"] + (u.get("completion_tokens", 0) or 0),
                    "total_tokens": usage["total_tokens"] + (u.get("total_tokens", 0) or 0),
                }
        except Exception as e:
            logger.exception("Chat processing error")
            reply_text = user_facing_error(e)

        assistant_msg = await self.msg_repo.create(
            conversation_id=conv.id,
            user_id=user_id,
            role="assistant",
            content=reply_text,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
        )

        await self.conv_repo.update(conv, updated_at=datetime.now(timezone.utc))

        return {
            "reply": reply_text,
            "conversation_id": conv.id,
            "message_id": assistant_msg.id,
            "usage": usage,
        }

    async def get_conversation(self, user_id: int, conversation_id: int) -> dict:
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv or conv.user_id != user_id:
            raise ValueError("Conversation not found")
        messages = await self.msg_repo.list_by_conversation(conversation_id)
        return {
            "id": conv.id,
            "title": conv.title,
            "status": conv.status,
            "messages": [
                {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
                for m in messages
            ],
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
        }

    async def list_conversations(self, user_id: int, page: int = 1, page_size: int = 20) -> dict:
        offset = (page - 1) * page_size
        items = await self.conv_repo.list_by_user_with_counts(user_id, limit=page_size, offset=offset)
        total = await self.conv_repo.count_by_user(user_id)
        for item in items:
            item["created_at"] = item["created_at"].isoformat() if item["created_at"] else None
            item["updated_at"] = item["updated_at"].isoformat() if item["updated_at"] else None
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    async def delete_conversation(self, user_id: int, conversation_id: int) -> None:
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv or conv.user_id != user_id:
            raise ValueError("Conversation not found")
        await self.conv_repo.delete(conv)

    async def update_conversation(
        self, user_id: int, conversation_id: int, title: str | None = None
    ) -> dict:
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv or conv.user_id != user_id:
            raise ValueError("Conversation not found")
        updates = {}
        if title is not None:
            updates["title"] = title
        updates["updated_at"] = datetime.now(timezone.utc)
        conv = await self.conv_repo.update(conv, **updates)
        return {
            "id": conv.id,
            "title": conv.title,
            "status": conv.status,
            "updated_at": conv.updated_at.isoformat(),
        }
