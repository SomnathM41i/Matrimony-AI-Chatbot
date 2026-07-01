from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.chat_model import ChatMessage


class ChatRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, message_id: int) -> ChatMessage | None:
        result = await self.db.execute(
            select(ChatMessage).where(ChatMessage.id == message_id)
        )
        return result.scalar_one_or_none()

    async def list_by_conversation(self, conversation_id: int) -> list[ChatMessage]:
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at)
        )
        return list(result.scalars().all())

    async def count_by_conversation(self, conversation_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
        )
        return result.scalar() or 0

    async def create(
        self, conversation_id: int, user_id: int, role: str, content: str,
        metadata_json: str | None = None
    ) -> ChatMessage:
        msg = ChatMessage(
            conversation_id=conversation_id,
            user_id=user_id,
            role=role,
            content=content,
            metadata_json=metadata_json,
        )
        self.db.add(msg)
        await self.db.flush()
        await self.db.refresh(msg)
        return msg

    async def delete_by_conversation(self, conversation_id: int) -> None:
        await self.db.execute(
            ChatMessage.__table__.delete().where(
                ChatMessage.conversation_id == conversation_id
            )
        )
        await self.db.flush()
