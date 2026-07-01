from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_authenticated_user
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.models.user_model import User

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def send_message(
    body: ChatRequest,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(body.message) > 5000:
        raise HTTPException(status_code=400, detail="Message too long")
    service = ChatService(db)
    try:
        result = await service.process_message(
            user_id=user.id,
            message=body.message.strip(),
            conversation_id=body.conversation_id,
        )
        return ChatResponse(
            reply=result["reply"],
            conversation_id=result["conversation_id"],
            message_id=result["message_id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")
