from typing import Annotated
from fastapi import Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_session
from backend.models.user import User


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    x_authentik_username: Annotated[str | None, Header()] = None,
) -> User:
    if not x_authentik_username:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = (await session.execute(
        select(User).where(User.authentik_username == x_authentik_username)
    )).scalar_one_or_none()

    if user is None:
        try:
            user_count = (await session.execute(
                select(func.count()).select_from(User)
            )).scalar() or 0
            user = User(
                authentik_username=x_authentik_username,
                is_admin=(user_count == 0),
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        except IntegrityError:
            await session.rollback()
            user = (await session.execute(
                select(User).where(User.authentik_username == x_authentik_username)
            )).scalar_one()

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
