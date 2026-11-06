Here it is, built on what we agreed: filters on status, customer_id and a created_at range; page and page_size with a default of 25 and a maximum of 100; sorting by created_at descending and then id descending; and a response of `{items, page, page_size, total}`. It uses only FastAPI, Pydantic v2, SQLAlchemy 2.0 async and the standard library. Validation failures go through your existing RequestValidationError handler, so they come back as 422 with the code `validation_error` in your error envelope.

You held off on the model earlier, so I've included a minimal one. If you already have an `Order` model, use yours instead.

**app/orders/models.py**
```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    status: Mapped[str] = mapped_column(Text, index=True)
    total_cents: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))
    shipping_country: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

**app/orders/schemas.py**
```python
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

OrderStatus = Literal["pending", "paid", "shipped", "cancelled"]


class OrderSearchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown query params -> 422

    status: OrderStatus | None = None
    customer_id: UUID | None = None
    created_from: AwareDatetime | None = None  # inclusive
    created_to: AwareDatetime | None = None    # exclusive
    page: int = Field(1, ge=1)
    page_size: int = Field(25, ge=1, le=100)

    @model_validator(mode="after")
    def check_date_range(self) -> "OrderSearchParams":
        if (
            self.created_from is not None
            and self.created_to is not None
            and self.created_from >= self.created_to
        ):
            raise ValueError("created_from must be earlier than created_to")
        return self


class OrderOut(BaseModel):
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
```

**app/orders/repository.py**
```python
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.orders.models import Order
from app.orders.schemas import OrderSearchParams


async def search_orders(
    session: AsyncSession, params: OrderSearchParams
) -> tuple[list[Order], int]:
    filters = []
    if params.status is not None:
        filters.append(Order.status == params.status)
    if params.customer_id is not None:
        filters.append(Order.customer_id == params.customer_id)
    if params.created_from is not None:
        filters.append(Order.created_at >= params.created_from)
    if params.created_to is not None:
        filters.append(Order.created_at < params.created_to)

    total = await session.scalar(
        select(func.count()).select_from(Order).where(*filters)
    )

    result = await session.scalars(
        select(Order)
        .where(*filters)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(params.page_size)
        .offset((params.page - 1) * params.page_size)
    )
    return list(result), total or 0
```

**app/orders/router.py**
```python
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.orders.repository import search_orders
from app.orders.schemas import OrderOut, OrderPage, OrderSearchParams

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=OrderPage)
async def list_orders(
    params: Annotated[OrderSearchParams, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrderPage:
    orders, total = await search_orders(session, params)
    return OrderPage(
        items=[OrderOut.model_validate(o) for o in orders],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )
```

A few decisions to check:

- **Date range is half-open,** `[created_from, created_to)`, so consecutive ranges such as one month followed by the next never double-count an order. `AwareDatetime` rejects timestamps without a timezone, which avoids clients silently querying in the wrong zone.
- **Unknown query parameters are rejected** because of `extra="forbid"`. A typo like `?stauts=paid` then fails loudly instead of quietly returning unfiltered results. Remove that line if you'd rather ignore extra parameters.
- **Requesting a page past the end** returns an empty `items` list with the correct `total`, not a 404. That is the usual behavior, and clients can work out the last page from `total`.
- **The model_validator message gets a prefix:** Pydantic delivers it as "Value error, created_from must be earlier than created_to". If your handler passes `msg` through unchanged, you may want to strip that prefix there.
- **The two queries run one after the other** on purpose. A single AsyncSession can't run statements concurrently, so don't wrap them in `asyncio.gather`.
- **Indexing:** the single-column indexes work, but the common query "one customer's orders, newest first" would benefit from a composite index on `(customer_id, created_at DESC, id DESC)`. If you add it, use a separate migration with `CREATE INDEX CONCURRENTLY`.

Then register it with `app.include_router(router)` in your application factory. I can write the tests next, using your rollback-per-test session fixture and httpx with ASGITransport.
