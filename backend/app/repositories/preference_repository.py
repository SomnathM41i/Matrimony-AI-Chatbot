from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.user_preference_model import UserPreference


class PreferenceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_user(self, user_id: int) -> list[UserPreference]:
        result = await self.db.execute(
            select(UserPreference)
            .where(UserPreference.user_id == user_id)
            .order_by(UserPreference.filter_key)
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        user_id: int,
        filter_key: str,
        value: str | None,
        source: str,
        matri_id: str | None = None,
    ) -> UserPreference:
        from datetime import datetime, timezone
        existing = await self.db.execute(
            select(UserPreference).where(
                UserPreference.user_id == user_id,
                UserPreference.filter_key == filter_key,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = UserPreference(
                user_id=user_id,
                matri_id=matri_id,
                filter_key=filter_key,
                value=value,
                source=source,
            )
            self.db.add(row)
        else:
            row.value = value
            row.source = source
            if matri_id is not None:
                row.matri_id = matri_id
            row.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def replace_all(
        self,
        user_id: int,
        filters: dict,
        source: str,
        matri_id: str | None = None,
    ) -> None:
        await self.db.execute(
            delete(UserPreference).where(UserPreference.user_id == user_id)
        )
        for key, value in (filters or {}).items():
            if value is None or value == "":
                continue
            self.db.add(
                UserPreference(
                    user_id=user_id,
                    matri_id=matri_id,
                    filter_key=key,
                    value=str(value),
                    source=source,
                )
            )
        await self.db.flush()

    async def clear(self, user_id: int) -> None:
        await self.db.execute(
            delete(UserPreference).where(UserPreference.user_id == user_id)
        )
        await self.db.flush()

    @staticmethod
    def to_filter_dict(preferences: list[UserPreference]) -> dict:
        result = {}
        for pref in preferences:
            if pref.value is None or pref.value == "":
                continue
            result[pref.filter_key] = pref.value
        return result
