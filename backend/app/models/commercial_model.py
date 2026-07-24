from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
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


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_plan_code_version"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), index=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="", nullable=False)
    price_paise = Column(Integer, default=0, nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    duration_days = Column(Integer, default=30, nullable=False)
    ai_credits = Column(Integer, default=0, nullable=False)
    daily_message_limit = Column(Integer, default=0, nullable=False)
    contact_limit = Column(Integer, default=0, nullable=False)
    normal_credit_cost = Column(Integer, default=1, nullable=False)
    database_credit_cost = Column(Integer, default=2, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_current = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), index=True, nullable=False)
    status = Column(String(32), default="active", index=True, nullable=False)
    plan_code = Column(String(64), nullable=False)
    plan_name = Column(String(128), nullable=False)
    price_paid_paise = Column(Integer, default=0, nullable=False)
    credits_allocated = Column(Integer, default=0, nullable=False)
    credits_used = Column(Integer, default=0, nullable=False)
    daily_message_limit = Column(Integer, default=0, nullable=False)
    daily_messages_used = Column(Integer, default=0, nullable=False)
    daily_reset_date = Column(Date, default=date.today, nullable=False)
    normal_credit_cost = Column(Integer, default=1, nullable=False)
    database_credit_cost = Column(Integer, default=2, nullable=False)
    contact_limit = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    plan = relationship("SubscriptionPlan")


class UsageReservation(Base):
    __tablename__ = "usage_reservations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), index=True, nullable=False)
    reserved_credits = Column(Integer, nullable=False)
    charged_credits = Column(Integer, default=0, nullable=False)
    status = Column(String(32), default="reserved", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    finalized_at = Column(DateTime, nullable=True)


class AIUsageEvent(Base):
    __tablename__ = "ai_usage_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), index=True, nullable=True)
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


class PaymentGateway(Base):
    __tablename__ = "payment_gateways"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False)
    adapter_type = Column(String(64), default="manual", nullable=False)
    key_id_env = Column(String(128), default="", nullable=False)
    secret_env = Column(String(128), default="", nullable=False)
    webhook_secret_env = Column(String(128), default="", nullable=False)
    enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_reference = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)
    gateway_id = Column(Integer, ForeignKey("payment_gateways.id"), nullable=True)
    amount_paise = Column(Integer, nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    status = Column(String(32), default="pending", index=True, nullable=False)
    provider_order_id = Column(String(256), unique=True, nullable=True)
    provider_payment_id = Column(String(256), unique=True, nullable=True)
    plan_snapshot_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    paid_at = Column(DateTime, nullable=True)

    plan = relationship("SubscriptionPlan")
    gateway = relationship("PaymentGateway")


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
