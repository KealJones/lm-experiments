Here it is. It's split into four pieces: the model (you hadn't written it yet), the schemas, the query, and the route. It only uses FastAPI, Pydantic, SQLAlchemy and the stdlib.

### 1. Model: `app/models/order.py`

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base  # wherever your DeclarativeBase lives


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), index=True
    )
    status: Mapped[str] = mapped_column(Text, index=True)
    total_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    shipping_country: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

### 2. Schemas: `app/schemas/orders.py`

If you already have `OrderOut` from the single-order endpoint, keep yours and delete mine. The list items have to use the same schema.

```python
import uuid
from datetime import datetime, timezone
from typing import Literal, get_args

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field,
    field_serializer, field_validator, model_validator,
)
from pydantic_core import PydanticCustomError

OrderStatus = Literal["pending", "paid", "shipped", "cancelled"]
STATUSES: tuple[str, ...] = get_args(OrderStatus)


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    status: OrderStatus
    total_cents: int
    currency: str
    shipping_country: str
    created_at: datetime
    updated_at: datetime | None

    @field_serializer("created_at", "updated_at")
    def _as_utc(self, v: datetime | None) -> datetime | None:
        # Always emit ISO 8601 UTC ("...Z"), whatever tz the driver handed back
        return v.astimezone(timezone.utc) if v is not None else None


class OrderSearchParams(BaseModel):
    # Unknown query params (e.g. ?statuss=paid) become a 422 instead of being silently ignored
    model_config = ConfigDict(extra="forbid")

    status: OrderStatus | None = None
    customer_id: uuid.UUID | None = None
    created_from: AwareDatetime | None = None  # inclusive
    created_to: AwareDatetime | None = None    # exclusive
    page: int = Field(1, ge=1)
    page_size: int = Field(25, ge=1, le=100)

    @field_validator("status", mode="before")
    @classmethod
    def _check_status(cls, v: object) -> object:
        if v is not None and v not in STATUSES:
            raise PydanticCustomError(
                "validation_error", f"status must be one of {', '.join(STATUSES)}"
            )
        return v

    @model_validator(mode="after")
    def _check_range(self) -> "OrderSearchParams":
        if self.created_from and self.created_to and self.created_from >= self.created_to:
            raise PydanticCustomError(
                "validation_error", "created_from must be before created_to"
            )
        return self


class OrderPage(BaseModel):
    items: list[OrderOut]
    page: int
    page_size: int
    total: int
```

I used `PydanticCustomError` rather than `ValueError` because Pydantic adds a `"Value error, "` prefix to `ValueError` messages, and that would end up inside your envelope. With this, the `RequestValidationError` handler in `app/errors.py` gets exactly `"status must be one of pending, paid, shipped, cancelled"` in `msg`. That assumes your handler copies the error's `msg` into `message`; if it builds its own string, adjust to match.

`AwareDatetime` rejects naive timestamps with a 422. A filter like `?created_from=2026-11-01T00:00:00` with no offset is ambiguous, and quietly reading it as server-local time is how off-by-a-few-hours bugs happen.

### 3. Query: `app/services/orders.py`

```python
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.schemas.orders import OrderSearchParams


async def search_orders(
    session: AsyncSession, params: OrderSearchParams
) -> tuple[list[Order], int]:
    conds = []
    if params.status is not None:
        conds.append(Order.status == params.status)
    if params.customer_id is not None:
        conds.append(Order.customer_id == params.customer_id)
    if params.created_from is not None:
        conds.append(Order.created_at >= params.created_from)
    if params.created_to is not None:
        conds.append(Order.created_at < params.created_to)

    total = await session.scalar(
        select(func.count()).select_from(Order).where(*conds)
    ) or 0

    offset = (params.page - 1) * params.page_size
    if offset >= total:
        return [], total  # past the last page: skip the second query

    rows = await session.scalars(
        select(Order)
        .where(*conds)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(params.page_size)
        .offset(offset)
    )
    return list(rows), total
```

### 4. Route: `app/routers/orders.py`

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.orders import OrderOut, OrderPage, OrderSearchParams
from app.services.orders import search_orders

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=OrderPage)
async def list_orders(
    params: Annotated[OrderSearchParams, Query()],
    session: AsyncSession = Depends(get_session),
) -> OrderPage:
    orders, total = await search_orders(session, params)
    return OrderPage(
        items=[OrderOut.model_validate(o) for o in orders],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )
```

Example: `GET /orders?status=paid&created_from=2026-10-01T00:00:00Z&page=2&page_size=50`

### Decisions you should check

- **The date range is half-open: `from` is inclusive, `to` is exclusive.** We only said "from/to" before, so this is my choice. It means `created_from=Oct 1` and `created_to=Nov 1` covers exactly October, with no `23:59:59.999` hacks. If you'd rather have an inclusive `to`, change the `<` to `<=`.
- **Asking for a page past the end returns `200` with `items: []` and the real `total`, not a 404.** That's the usual pagination behavior, and it lets clients work out where the last page is.
- **Your separate indexes won't fit the common queries well.** "This customer's orders, newest first" filters on `customer_id` and sorts on `created_at`. With separate single-column indexes, Postgres will usually pick one and then sort. A composite `(customer_id, created_at DESC, id DESC)` index serves that query directly, and you could do the same for `status`. The single-column `status` index probably isn't selective enough to help much anyway.
- **`COUNT(*)` and deep `OFFSET` get slow as the table grows.** Every request runs both. That's fine at moderate size, but at millions of rows, an unfiltered `total` and page 4,000 will hurt. That's the point where you'd move to keyset (cursor) pagination on `(created_at, id)`, which the sort order already supports. I wouldn't do it now, but don't be surprised when it comes up.

I can also write the tests for this: filters, the sort tiebreak, the `total`, and the 422 envelope cases, using your savepoint fixture and the `get_session` override.
