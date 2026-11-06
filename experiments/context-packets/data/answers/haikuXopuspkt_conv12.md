Here's the paginated search endpoint for orders, using the spec we settled on: optional filters, offset pagination, `created_at DESC` with `id DESC` as the tiebreaker, and a `total` that counts only rows matching the filters.

Two pieces are new. There's no SQLAlchemy model for `orders` yet, so I included a minimal one. The router and handler go in their own module. Everything uses only FastAPI, Pydantic v2, SQLAlchemy 2.0 and the standard library.

```python
# app/models/order.py
import uuid
from datetime import datetime

from sqlalchemy import Text, Integer, String
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    status: Mapped[str] = mapped_column(Text, index=True)
    total_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    shipping_country: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
```

```python
# app/routers/orders.py
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session  # your existing session dependency
from app.models.order import Order

router = APIRouter(prefix="/orders", tags=["orders"])

OrderStatus = Literal["pending", "paid", "shipped", "cancelled"]


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    status: OrderStatus
    total_cents: int
    currency: str
    shipping_country: str
    created_at: datetime
    updated_at: datetime


class OrderPage(BaseModel):
    items: list[OrderOut]
    page: int
    page_size: int
    total: int


class OrderSearchParams(BaseModel):
    status: OrderStatus | None = None
    customer_id: UUID | None = None
    created_from: date | None = None  # inclusive, UTC day
    created_to: date | None = None    # inclusive, UTC day
    page: int = Field(1, ge=1)
    page_size: int = Field(25, ge=1, le=100)

    @model_validator(mode="after")
    def check_date_range(self):
        if self.created_from and self.created_to and self.created_from > self.created_to:
            raise ValueError("created_from must not be after created_to")
        return self


@router.get("", response_model=OrderPage)
async def search_orders(
    params: Annotated[OrderSearchParams, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrderPage:
    conditions = []
    if params.status is not None:
        conditions.append(Order.status == params.status)
    if params.customer_id is not None:
        conditions.append(Order.customer_id == params.customer_id)
    if params.created_from is not None:
        start = datetime.combine(params.created_from, time.min, tzinfo=UTC)
        conditions.append(Order.created_at >= start)
    if params.created_to is not None:
        end = datetime.combine(params.created_to + timedelta(days=1), time.min, tzinfo=UTC)
        conditions.append(Order.created_at < end)

    total = await session.scalar(
        select(func.count()).select_from(Order).where(*conditions)
    )

    result = await session.scalars(
        select(Order)
        .where(*conditions)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    )

    return OrderPage(
        items=[OrderOut.model_validate(row) for row in result],
        page=params.page,
        page_size=params.page_size,
        total=total or 0,
    )
```

Remember to register the router with `app.include_router(orders.router)`.

Notes:

- **Validation errors:** a bad `status` or `page_size=500` returns 422 with `code: "validation_error"` through the existing `RequestValidationError` handler in `app/errors.py`, so it uses the envelope. The reversed date range fails in the `model_validator` and goes through the same path. If the handler doesn't already map Pydantic's error list into `message`, that's the one place to adjust.
- **Date filters:** `created_to` is inclusive. The upper bound is converted to `< next day 00:00 UTC`, so it covers the whole day without a `<=` on a timestamp.
- **Sort order:** I used `id DESC` as the secondary key to match `created_at DESC`. If you wanted ascending for ids, change that one line.
- **Performance:** offset pagination gets slower on deep pages, and `COUNT(*)` over a large filtered set costs real time. If either becomes a problem, switch to keyset pagination on `(created_at, id)` or cache the total. If the status-filtered queries are common, a composite index on `(status, created_at)` would serve them better than the separate single-column indexes.

For tests, the usual approach fits: seed a few orders across two customers and statuses, then assert the sort order, that `total` ignores pagination, and that a reversed date range returns a 422.
