from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.limiter import limiter
from app.dependencies import get_db, get_authenticated_user
from app.models.user_model import User
from app.repositories.preference_repository import PreferenceRepository
from app.services.matri_service import (
    link_matri_id_to_user,
    start_questionnaire,
    advance_questionnaire,
    normalize_matri_id,
    MatriLinkError,
)
from app.core.questionnaire import QuestionnaireError
from app.schemas.profile_schema import (
    UpdateProfileRequest,
    LinkMatriRequest,
    QuestionnaireNextRequest,
    SavePreferenceRequest,
)
from app.schemas.auth_schema import UserResponse

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.patch("", response_model=UserResponse)
@limiter.limit("20/minute")
async def update_profile(
    request: Request,
    body: UpdateProfileRequest,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    if body.name is not None:
        user.name = body.name
    if body.profile_image is not None:
        user.profile_image = body.profile_image or None
    if body.matri_id is not None:
        try:
            user.matri_id = normalize_matri_id(body.matri_id)
        except MatriLinkError as e:
            raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/matri/link")
@limiter.limit("20/minute")
async def link_matri(
    request: Request,
    body: LinkMatriRequest,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await link_matri_id_to_user(db, user, body.matri_id)
    except MatriLinkError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=503, detail="Could not reach the matrimony database.")

    await db.commit()
    await db.refresh(user)
    return {
        "user": UserResponse.model_validate(user),
        "member": result["member"],
        "filters": result["filters"],
        "summary": result["summary"],
        "saved_search_used": result["saved_search_used"],
        "saved_search_source": result["saved_search_source"],
    }


@router.get("/preference")
@limiter.limit("60/minute")
async def get_preferences(
    request: Request,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await PreferenceRepository(db).list_by_user(user.id)
    return {
        "filters": PreferenceRepository.to_filter_dict(prefs),
        "rows": [
            {
                "filter_key": p.filter_key,
                "value": p.value,
                "source": p.source,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in prefs
        ],
        "matri_id": user.matri_id,
        "matri_name": user.matri_name,
        "matri_synced_at": user.matri_synced_at.isoformat() if user.matri_synced_at else None,
    }


@router.post("/preference/start")
@limiter.limit("30/minute")
async def start_preference_flow(
    request: Request,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await PreferenceRepository(db).list_by_user(user.id)
    base = PreferenceRepository.to_filter_dict(prefs)
    try:
        return start_questionnaire(base)
    except QuestionnaireError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/preference/next")
@limiter.limit("60/minute")
async def next_preference_question(
    request: Request,
    body: QuestionnaireNextRequest,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await PreferenceRepository(db).list_by_user(user.id)
    base = PreferenceRepository.to_filter_dict(prefs)
    answers = [a.model_dump() for a in body.answers]
    try:
        result = advance_questionnaire(base, answers)
    except QuestionnaireError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if result["done"]:
        await PreferenceRepository(db).replace_all(
            user.id, result["filters"], source="questionnaire", matri_id=user.matri_id
        )
        await db.commit()
    return result


@router.post("/preference/save")
@limiter.limit("20/minute")
async def save_preferences(
    request: Request,
    body: SavePreferenceRequest,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    await PreferenceRepository(db).replace_all(
        user.id, body.filters, source="questionnaire", matri_id=user.matri_id
    )
    await db.commit()
    return {"success": True, "filters": body.filters}


@router.delete("/preference")
@limiter.limit("20/minute")
async def clear_preferences(
    request: Request,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    await PreferenceRepository(db).clear(user.id)
    await db.commit()
    return {"success": True}
