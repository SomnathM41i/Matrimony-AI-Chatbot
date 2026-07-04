from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.chat_repository import ChatRepository
from app.services.llm_service import get_general_response
from app.services.db_query_service import answer_database_question, check_db_connection
from app.ai.intent_detector import is_database_question, detect_intent
from app.core.logger import logger
from datetime import datetime, timezone


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conv_repo = ConversationRepository(db)
        self.msg_repo = ChatRepository(db)

    async def process_message(
        self, user_id: int, message: str, conversation_id: int | None = None
    ) -> dict:
        if conversation_id:
            conv = await self.conv_repo.get_by_id(conversation_id)
            if not conv or conv.user_id != user_id:
                raise ValueError("Conversation not found")
        else:
            title = message[:60] + ("..." if len(message) > 60 else "")
            conv = await self.conv_repo.create(user_id=user_id, title=title)

        user_msg = await self.msg_repo.create(
            conversation_id=conv.id,
            user_id=user_id,
            role="user",
            content=message,
        )

        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        try:
            if is_database_question(message):
                result = await answer_database_question(message)
            else:
                result = await get_general_response(message)
            reply_text = result["content"]
            if result.get("usage"):
                u = result["usage"]
                usage = {
                    "prompt_tokens": usage["prompt_tokens"] + (u.get("prompt_tokens", 0) or 0),
                    "completion_tokens": usage["completion_tokens"] + (u.get("completion_tokens", 0) or 0),
                    "total_tokens": usage["total_tokens"] + (u.get("total_tokens", 0) or 0),
                }
        except Exception as e:
            logger.error(f"Chat processing error: {e}")
            reply_text = f"I encountered an error: {str(e)}"

        assistant_msg = await self.msg_repo.create(
            conversation_id=conv.id,
            user_id=user_id,
            role="assistant",
            content=reply_text,
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
        conversations = await self.conv_repo.list_by_user(user_id, limit=page_size, offset=offset)
        total = await self.conv_repo.count_by_user(user_id)
        result = []
        for conv in conversations:
            msg_count = await self.msg_repo.count_by_conversation(conv.id)
            result.append({
                "id": conv.id,
                "title": conv.title,
                "message_count": msg_count,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
            })
        return {
            "items": result,
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
