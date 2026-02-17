from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import deps
from app.core.database import get_session
from app.models.models import User
from app.services.runtime_settings_service import RuntimeSettingsService

router = APIRouter()


class RuntimeSettingsResponse(BaseModel):
    model: str
    top_k: int = Field(ge=1, le=20)
    available_models: list[str]


class RuntimeSettingsUpdate(BaseModel):
    model: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


class UserRoleItem(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime


class UserRoleUpdate(BaseModel):
    role: Literal["admin", "content_manager", "user"]


@router.get("/", response_model=RuntimeSettingsResponse)
async def get_runtime_settings(
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    runtime_settings = RuntimeSettingsService.get_settings()
    return RuntimeSettingsResponse(
        model=runtime_settings["model"],
        top_k=runtime_settings["top_k"],
        available_models=RuntimeSettingsService.available_models(),
    )


@router.put("/", response_model=RuntimeSettingsResponse)
async def update_runtime_settings(
    payload: RuntimeSettingsUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    try:
        updated = RuntimeSettingsService.update_settings(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RuntimeSettingsResponse(
        model=updated["model"],
        top_k=updated["top_k"],
        available_models=RuntimeSettingsService.available_models(),
    )


@router.get("/users", response_model=list[UserRoleItem])
async def list_users_for_role_management(
    current_user: User = Depends(deps.get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
) -> Any:
    result = await session.exec(select(User).order_by(User.created_at.desc()))
    users = result.all()
    return [
        UserRoleItem(
            id=user.id,
            username=user.username,
            role=user.role,
            created_at=user.created_at,
        )
        for user in users
        if user.id is not None
    ]


@router.put("/users/{user_id}/role", response_model=UserRoleItem)
async def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: AsyncSession = Depends(get_session),
) -> Any:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Avoid removing the last admin privileges from yourself by mistake.
    if user.id == current_user.id and payload.role != "admin":
        admins_result = await session.exec(select(User).where(User.role == "admin"))
        admins = admins_result.all()
        if len(admins) <= 1:
            raise HTTPException(status_code=400, detail="At least one admin must remain in the system")

    user.role = payload.role
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return UserRoleItem(
        id=user.id,
        username=user.username,
        role=user.role,
        created_at=user.created_at,
    )
