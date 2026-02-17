from datetime import datetime, timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, ConfigDict
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.core import security
from app.core.config import settings
from app.core.rate_limit import auth_limiter, check_rate_limit
from app.api import deps
from app.models.models import User

router = APIRouter()


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class RegisterResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime


@router.post("/login/access-token", response_model=dict)
async def login_access_token(
    session: AsyncSession = Depends(deps.get_session),
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    Rate limited to 10 attempts per minute per IP.
    """
    # Check rate limit
    if request:
        await check_rate_limit(request, auth_limiter)
    
    result = await session.exec(select(User).where(User.username == form_data.username))
    user = result.first()
    
    if not user or not security.verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/login", response_model=dict)
async def login_alias(
    session: AsyncSession = Depends(deps.get_session),
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
) -> Any:
    """
    Alias for /login/access-token to match clients expecting /auth/login.
    """
    return await login_access_token(session=session, form_data=form_data, request=request)


@router.post("/register", response_model=RegisterResponse)
async def register_user(
    session: AsyncSession = Depends(deps.get_session),
    payload: RegisterRequest = None,
    request: Request = None
) -> Any:
    """
    Register a new user.
    Rate limited to 10 attempts per minute per IP.
    """
    if request:
        # Check rate limit
        await check_rate_limit(request, auth_limiter)
    
    result = await session.exec(select(User).where(User.username == payload.username))
    user = result.first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system",
        )
    user_in = User(
        username=payload.username,
        password_hash=security.get_password_hash(payload.password),
        role="user",
    )
    session.add(user_in)
    await session.commit()
    await session.refresh(user_in)
    return RegisterResponse(
        id=user_in.id,
        username=user_in.username,
        role=user_in.role,
        created_at=user_in.created_at,
    )
