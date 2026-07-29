from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AIProvider(Base):
    __tablename__ = "ai_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=False)
    adapter_type = Column(String(64), default="openai_compatible", nullable=False)
    base_url = Column(String(1024), nullable=False)
    api_key_env = Column(String(128), default="", nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    verify_ssl = Column(Boolean, default=True, nullable=False)
    timeout_seconds = Column(Integer, default=30, nullable=False)
    retry_count = Column(Integer, default=2, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    models = relationship("AIModel", back_populates="provider", cascade="all, delete-orphan")


class AIModel(Base):
    __tablename__ = "ai_models"
    __table_args__ = (UniqueConstraint("provider_id", "external_id", name="uq_ai_provider_model"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(Integer, ForeignKey("ai_providers.id"), index=True, nullable=False)
    external_id = Column(String(256), nullable=False)
    display_name = Column(String(256), nullable=False)
    context_window = Column(Integer, default=8192, nullable=False)
    max_output_tokens = Column(Integer, default=1200, nullable=False)
    supports_json = Column(Boolean, default=True, nullable=False)
    supports_sql = Column(Boolean, default=True, nullable=False)
    input_cost_paise_per_million = Column(Integer, default=0, nullable=False)
    output_cost_paise_per_million = Column(Integer, default=0, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    provider = relationship("AIProvider", back_populates="models")


class AITaskRoute(Base):
    __tablename__ = "ai_task_routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_key = Column(String(64), unique=True, index=True, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    targets = relationship(
        "AITaskTarget",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="AITaskTarget.priority",
    )


class AITaskTarget(Base):
    __tablename__ = "ai_task_targets"
    __table_args__ = (UniqueConstraint("route_id", "priority", name="uq_ai_route_priority"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("ai_task_routes.id"), index=True, nullable=False)
    model_id = Column(Integer, ForeignKey("ai_models.id"), index=True, nullable=False)
    priority = Column(Integer, default=1, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    route = relationship("AITaskRoute", back_populates="targets")
    model = relationship("AIModel")


class AIUsageEvent(Base):
    __tablename__ = "ai_usage_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True, nullable=True)
    task_key = Column(String(64), index=True, nullable=False)
    request_type = Column(String(32), default="normal", nullable=False)
    provider_code = Column(String(64), nullable=False)
    model_external_id = Column(String(256), nullable=False)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    estimated_cost_micropaise = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Integer, default=0, nullable=False)
    provider_request_id = Column(String(256), nullable=True)
    status = Column(String(32), default="success", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class AdminAuditEvent(Base):
    __tablename__ = "admin_audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    action = Column(String(128), index=True, nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=False)
    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
