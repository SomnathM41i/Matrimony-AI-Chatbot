from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PlanInput(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=128)
    description: str = Field(default="", max_length=2000)
    price_paise: int = Field(ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    duration_days: int = Field(ge=1, le=3650)
    ai_credits: int = Field(ge=0)
    daily_message_limit: int = Field(ge=0)
    contact_limit: int = Field(ge=0)
    normal_credit_cost: int = Field(default=1, ge=1, le=100)
    database_credit_cost: int = Field(default=2, ge=1, le=100)
    is_active: bool = True


class ProviderInput(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=128)
    adapter_type: str = Field(default="openai_compatible", max_length=64)
    base_url: str = Field(min_length=8, max_length=1024)
    api_key_env: str = Field(default="", max_length=128)
    enabled: bool = True
    verify_ssl: bool = True
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    retry_count: int = Field(default=2, ge=0, le=10)


class ModelInput(BaseModel):
    provider_id: int
    external_id: str = Field(min_length=1, max_length=256)
    display_name: str = Field(min_length=1, max_length=256)
    context_window: int = Field(default=8192, ge=512)
    max_output_tokens: int = Field(default=1200, ge=1)
    supports_json: bool = True
    supports_sql: bool = True
    input_cost_paise_per_million: int = Field(default=0, ge=0)
    output_cost_paise_per_million: int = Field(default=0, ge=0)
    enabled: bool = True


class RouteInput(BaseModel):
    task_key: str = Field(min_length=2, max_length=64)
    model_ids: list[int] = Field(min_length=1, max_length=10)
    enabled: bool = True


class SubscriptionAssignment(BaseModel):
    plan_id: int
    starts_at: Optional[datetime] = None


class SubscriptionAdminUpdate(BaseModel):
    status: Optional[str] = None
    credits_delta: int = Field(default=0, ge=-1_000_000, le=1_000_000)
    extend_days: int = Field(default=0, ge=0, le=3650)
    daily_message_limit: Optional[int] = Field(default=None, ge=0, le=100_000)


class OrderCreate(BaseModel):
    plan_id: int


class ManualPaymentConfirm(BaseModel):
    provider_payment_id: str = Field(min_length=3, max_length=256)


class GatewayInput(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=128)
    adapter_type: str = Field(default="manual", max_length=64)
    key_id_env: str = Field(default="", max_length=128)
    secret_env: str = Field(default="", max_length=128)
    webhook_secret_env: str = Field(default="", max_length=128)
    enabled: bool = False
