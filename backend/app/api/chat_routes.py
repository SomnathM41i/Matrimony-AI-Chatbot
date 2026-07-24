from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.dependencies import get_db, get_authenticated_user
from app.schemas.chat_schema import ChatRequest, ChatResponse, UsageInfo
from app.services.chat_service import ChatService
from app.models.user_model import User
from app.main import limiter
from app.core.logger import logger
from app.services.commercial_service import CommercialLimitError

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
@limiter.limit("30/minute")
async def send_message(
    request: Request,
    body: ChatRequest,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(body.message) > settings.MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=400, detail="Message too long")
    service = ChatService(db)
    try:
        result = await service.process_message(
            user_id=user.id,
            message=body.message.strip(),
            conversation_id=body.conversation_id,
        )
        await db.commit()
        return ChatResponse(
            reply=result["reply"],
            conversation_id=result["conversation_id"],
            message_id=result["message_id"],
            usage=UsageInfo(**result.get("usage", {})),
            request_id=result.get("request_id"),
            credits_charged=result.get("credits_charged", 0),
            subscription=result.get("subscription"),
        )
    except CommercialLimitError as e:
        await db.rollback()
        raise HTTPException(
            status_code=e.status_code,
            detail={"code": e.code, "message": str(e)},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Unhandled chat API error")
        raise HTTPException(
            status_code=500,
            detail="Sorry, the request could not be processed right now.",
        )
