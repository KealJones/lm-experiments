Here is the paginated search endpoint, built on what we agreed: filters for status, customer_id, and a created_at range, page and page_size with a default of 25 and a maximum of 100, sorting by created_at descending with id as the tiebreaker, and a response with items, page, page_size, and total. It uses only FastAPI, Pydantic v2, and SQLAlchemy, so there are no new dependencies. Query parameter models need FastAPI 0.115 or newer, so check your lock file first.

**app/schemas/orders.py**

```python
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class OrderSearchParams(BaseModel):
    status: OrderStatus | None = None
    customer_id: UUID | None = None
    created_from: datetime | None = None  # inclusive
    created_to: datetime | None = None    # exclusive
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)

    @field_validator("created_from", "created_to")
    @classmethod
    def require_utc_offset(cls, v: datetime | None) -> datetime | None:
        # Naive datetimes cannot be compared with timestamptz values, so reject them with a 422.
        if v is not None and v.tzinfo is None:
            raise ValueError("must include a UTC offset, for example 2026-11-01T00:00:00Z")
        return v

    @model_validator(mode="after")
    def check_date_range(self):
        if self.created_from and self.created_to and self.created_from >= self.created_to:
            raise ValueError("created_from must be earlier than created_to")
        return self


class OrderPage(BaseModel):
    items: list[OrderOut]
    page: int
    page_size: int
    total: int
```

**app/api/orders.py**

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session        # adjust to your module path
from app.models import Order          # adjust to your module path
from app.schemas.orders import OrderOut, OrderPage, OrderSearchParams

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=OrderPage)
async def search_orders(
    params: Annotated[OrderSearchParams, Query()],
    session: AsyncSession = Depends(get_session),
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

    # The count uses the same filters, so total reflects the active filters.
    total = await session.scalar(
        select(func.count()).select_from(Order).where(*filters)
    )

    offset = (params.page - 1) * params.page_size
    result = await session.scalars(
        select(Order)
        .where(*filters)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .offset(offset)
        .limit(params.page_size)
    )

    return OrderPage(
        items=[OrderOut.model_validate(order) for order in result],
        page=params.page,
        page_size=params.page_size,
        total=total or 0,
    )
```

Register the router in your application factory with `app.include_router(orders.router)`.

Notes:

- Validation failures, such as page set to 0, page_size above 100, a status outside the four values, a naive timestamp, or an inverted date range, go through the RequestValidationError handler we set up earlier. The client gets a 422 with the code validation_error in the standard envelope. The message for the date range check will be Pydantic's wording, so if you want something friendlier, change the ValueError text.
- The date range is half-open, with created_from inclusive and created_to exclusive. That makes adjacent ranges such as one day to the next line up without overlap. If your API consumers expect both ends inclusive, change the operator and say so in the API docs.
- Both queries run sequentially on the same session, because an AsyncSession should not run concurrent statements. Offset pagination means deep pages get slower, as we discussed.
- If the customer_id filter is common and paired with date ranges, a composite index on (customer_id, created_at DESC) may serve the query better than the separate single-column indexes. Check it with EXPLAIN (ANALYZE, BUFFERS) on realistic data before adding it. If you do add it, create it with CREATE INDEX CONCURRENTLY in a migration that runs outside a transaction.
- For tests, the cleanest approach is the rollback-based session fixture we settled on, creating a handful of orders and checking the filter combinations, the page boundaries, and the total.
