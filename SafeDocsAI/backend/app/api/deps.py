from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession
from app.shared.settings import settings
from app.core.database import get_session, session_context
from app.shared.models import User
from sqlmodel import select

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login/access-token"
)


async def _get_current_user_from_session(session: AsyncSession, token: str) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Could not validate credentials",
            )
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    result = await session.exec(select(User).where(User.username == username))
    user = result.first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def get_current_user(
    session: AsyncSession = Depends(get_session), token: str = Depends(oauth2_scheme)
) -> User:
    return await _get_current_user_from_session(session, token)


async def get_current_user_short_lived(
    token: str = Depends(oauth2_scheme),
) -> User:
    async with session_context() as session:
        return await _get_current_user_from_session(session, token)


async def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=400, detail="The user doesn't have enough privileges"
        )
    return current_user


async def get_current_content_manager_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role not in ("admin", "content_manager"):
        raise HTTPException(
            status_code=403, detail="The user does not have enough privileges"
        )
    return current_user
