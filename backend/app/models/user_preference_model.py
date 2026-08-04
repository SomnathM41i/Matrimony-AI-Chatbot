from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from datetime import datetime, timezone
from app.database import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "filter_key", name="uq_user_preference_key"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    matri_id = Column(String(15), nullable=True)
    filter_key = Column(String(64), nullable=False)
    value = Column(String(255), nullable=True)
    source = Column(String(32), nullable=False, default="questionnaire")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
