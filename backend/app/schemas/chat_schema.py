from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime

from app.config import settings

MAX_CONVERSATION_TITLE_LENGTH = 200


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None

    @field_validator("message")
    @classmethod
    def check_message_length(cls, v: str) -> str:
        if len(v) > settings.MAX_MESSAGE_LENGTH:
            raise ValueError("Message too long")
        return v


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    reply: str
    conversation_id: int
    message_id: int
    usage: UsageInfo = UsageInfo()
    request_id: Optional[str] = None


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationListItem(BaseModel):
    id: int
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: int
    title: str
    status: str
    messages: List[MessageResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None

    @field_validator("title")
    @classmethod
    def check_title(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Title cannot be empty")
            if len(v) > MAX_CONVERSATION_TITLE_LENGTH:
                raise ValueError(f"Title must be at most {MAX_CONVERSATION_TITLE_LENGTH} characters")
        return v
