from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_authenticated_user
from app.schemas.chat_schema import UpdateConversationRequest
from app.schemas.common_schema import SuccessResponse
from app.services.chat_service import ChatService
from app.models.user_model import User

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=dict)
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = ChatService(db)
    return await service.list_conversations(user.id, page=page, page_size=page_size)


@router.get("/{conversation_id}", response_model=dict)
async def get_conversation(
    conversation_id: int,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = ChatService(db)
    try:
        return await service.get_conversation(user.id, conversation_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{conversation_id}", response_model=dict)
async def update_conversation(
    conversation_id: int,
    body: UpdateConversationRequest,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = ChatService(db)
    try:
        result = await service.update_conversation(
            user.id, conversation_id, title=body.title
        )
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{conversation_id}", response_model=SuccessResponse)
async def delete_conversation(
    conversation_id: int,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = ChatService(db)
    try:
        await service.delete_conversation(user.id, conversation_id)
        await db.commit()
        return SuccessResponse(message="Conversation deleted")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
