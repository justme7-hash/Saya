"""مخزن علاقه‌مندی‌ها."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from anonchat.db.repositories.base import BaseRepository
from anonchat.models.favorite import Favorite


class FavoriteRepository(BaseRepository[Favorite]):
    """مخزن کاربران محبوب."""

    model = Favorite

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def add_favorite(
        self, *, user_id: int, favorite_user_id: int, note: str | None = None
    ) -> Favorite:
        """افزودن کاربر به لیست محبوب‌ها."""
        fav = Favorite(
            user_id=user_id,
            favorite_user_id=favorite_user_id,
            note=note,
        )
        return await self.add(fav)

    async def remove_favorite(self, user_id: int, favorite_user_id: int) -> bool:
        """حذف از لیست محبوب‌ها."""
        fav = await self.get_by(
            user_id=user_id, favorite_user_id=favorite_user_id
        )
        if fav is None:
            return False
        await self.delete(fav)
        return True

    async def get_favorites(self, user_id: int, limit: int = 50) -> list[Favorite]:
        """دریافت لیست محبوب‌های کاربر."""
        stmt = (
            select(Favorite)
            .where(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def is_favorite(self, user_id: int, favorite_user_id: int) -> bool:
        """بررسی اینکه آیا کاربر در لیست محبوب‌هاست."""
        fav = await self.get_by(
            user_id=user_id, favorite_user_id=favorite_user_id
        )
        return fav is not None
