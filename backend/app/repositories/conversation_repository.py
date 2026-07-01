from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.models.conversation_model import Conversation


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, conversation_id: int) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: int, limit: int = 50, offset: int = 0) -> list[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.status != "deleted")
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_user(self, user_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Conversation)
            .where(Conversation.user_id == user_id, Conversation.status != "deleted")
        )
        return result.scalar() or 0

    async def create(self, user_id: int, title: str = "New Chat") -> Conversation:
        conv = Conversation(user_id=user_id, title=title)
        self.db.add(conv)
        await self.db.flush()
        await self.db.refresh(conv)
        return conv

    async def update(self, conv: Conversation, **kwargs) -> Conversation:
        for key, value in kwargs.items():
            if hasattr(conv, key):
                setattr(conv, key, value)
        await self.db.flush()
        await self.db.refresh(conv)
        return conv

    async def delete(self, conv: Conversation) -> None:
        conv.status = "deleted"
        await self.db.flush()
