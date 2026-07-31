"""مخزن پایه (Generic Repository Pattern).

تمام مخازن از این کلاس ارث‌بری می‌کنند تا عملیات CRUD مشترک
DRY و تایپ‌سیف باشند.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from anonchat.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """مخزن پایه با عملیات CRUD مشترک."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id_: int) -> ModelT | None:
        """دریافت موجودیت بر اساس شناسه."""
        return await self.session.get(self.model, id_)

    async def get_by(self, **filters: Any) -> ModelT | None:
        """دریافت اولین موجودیت منطبق با فیلترها."""
        stmt = select(self.model).filter_by(**filters).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_many(
        self,
        *,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
        order_by: Any = None,
    ) -> list[ModelT]:
        """دریافت لیست موجودیت‌ها با فیلتر و صفحه‌بندی."""
        stmt = select(self.model)
        if filters:
            stmt = stmt.filter_by(**filters)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, **filters: Any) -> int:
        """تعداد موجودیت‌های منطبق."""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model)
        if filters:
            stmt = stmt.filter_by(**filters)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def add(self, instance: ModelT) -> ModelT:
        """افزودن موجودیت جدید."""
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, instance: ModelT, **fields: Any) -> ModelT:
        """به‌روزرسانی فیلدهای موجودیت."""
        for key, value in fields.items():
            setattr(instance, key, value)
        await self.session.flush()
        return instance

    async def delete(self, instance: ModelT) -> None:
        """حذف موجودیت."""
        await self.session.delete(instance)
        await self.session.flush()

    async def commit(self) -> None:
        """کامیت نشست."""
        await self.session.commit()

    async def refresh(self, instance: ModelT) -> ModelT:
        """رفرش موجودیت از دیتابیس."""
        await self.session.refresh(instance)
        return instance
