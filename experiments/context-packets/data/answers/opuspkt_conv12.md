Here it is. It's in three pieces: the `Order` model you'd put off writing, the schemas, and the route. It only uses FastAPI, Pydantic, SQLAlchemy and the standard library, so no new dependencies.

### `app/models/order.py`

```python
import uuid
from datetime import datetime

from sqlalchemy import String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base  # adjust to wherever your declarative Base lives


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    # The FK to customers is enforced in the DB. Add ForeignKey("customers.id")
    # once a Customer model exists, or metadata resolution will fail.
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(Text)
    total_cents: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))
    shipping_country: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
```

### `app/schemas/order.py`

```python
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OrderStatus = Literal["pending", "paid", "shipped", "cancelled"]


class OrderOut(BaseModel):
    """Single-order representation. If you already have one, use it here instead."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    status: OrderStatus
    total_cents: int
    currency: str
    shipping_country: str
    created_at: datetime
    updated_at: datetime | None


class OrderPage(BaseModel):
    items: list[OrderOut]
    page: int
    page_size: int
    total: int


class OrderSearchParams(BaseModel):
    status: OrderStatus | None = None
    customer_id: UUID | None = None
    created_from: datetime | None = None  # inclusive
    created_to: datetime | None = None    # exclusive
    page: int = Field(1, ge=1)
    page_size: int = Field(25, ge=1, le=100)

    @field_validator("created_from", "created_to")
    @classmethod
    def _assume_utc(cls, v: datetime | None) -> datetime | None:
        # Treat naive timestamps as UTC instead of rejecting them.
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @model_validator(mode="after")
    def _check_range(self) -> "OrderSearchParams":
        if self.created_from and self.created_to and self.created_from > self.created_to:
            raise ValueError("created_from must not be after created_to")
        return self
```

### `app/routers/orders.py`

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.order import Order
from app.schemas.order import OrderOut, OrderPage, OrderSearchParams

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=OrderPage)
async def search_orders(
    params: Annotated[OrderSearchParams, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrderPage:
    filters = []
    if params.status is not None:
        filters.append(Order.status == params.status)
    if params.customer_id is not None:
        filters.append(Order.customer_id == params.customer_id)
    if params.created_from is not None:
        filters.append(Order.created_at >= params.created_from)
    if params.created_to is not None:
        filters.append(Order.created_at < params.created_to)

    total = (
        await session.execute(select(func.count()).select_from(Order).where(*filters))
    ).scalar_one()

    offset = (params.page - 1) * params.page_size
    rows: list[Order] = []
    if offset < total:  # skip the page query entirely past the last page
        stmt = (
            select(Order)
            .where(*filters)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .offset(offset)
            .limit(params.page_size)
        )
        rows = list((await session.scalars(stmt)).all())

    return OrderPage(
        items=[OrderOut.model_validate(r) for r in rows],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )
```

Then register it with `app.include_router(orders.router)` (or add the route to your existing orders router if you have one).

A few choices I made that you might want to change:

- **Param names and range semantics:** We never settled the names, so I went with `created_from` / `created_to` as a half-open range `[from, to)`. That way `created_to=2024-02-01` doesn't double-count midnight. If someone sends a naive timestamp, it's treated as UTC.
- **Validation errors:** A bad `status`, a `page_size` over 100, `page=0` or an inverted range all raise `RequestValidationError`. Your override in `app/errors.py` already turns that into a 422 `validation_error` envelope. One catch: Pydantic v2 prefixes `model_validator` messages with `"Value error, "`, so strip that in your handler if you want a clean "created_from must not be after created_to".
- **Past the last page:** You get `items: []` with the real `total`, not an error. Skipping the query when `offset >= total` also means a huge `page` can't send Postgres an OFFSET bigger than bigint.
- **Timestamps:** asyncpg returns timestamptz as aware UTC datetimes, and Pydantic serializes those as ISO 8601 (with a `Z`), so that matches your convention as is.
- **Performance:** The single-column indexes work, but if filtering by customer or status plus sorting gets hot, composite indexes will let Postgres stop early: `(customer_id, created_at DESC, id DESC)` and `(status, created_at DESC, id DESC)`. The earlier caveats still apply. Deep offsets and `COUNT(*)` on a huge unfiltered table are where this will start to hurt. If that happens, the usual fixes are keyset pagination or an approximate total.

Want me to write the pytest-asyncio tests next? They'd cover the filters, the ordering tiebreak, the page math and the 422 cases. Note the fixtures will need to insert a customer row first because of the FK.
