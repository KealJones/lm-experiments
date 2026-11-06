Yep, here it is. It sticks to the spec: optional `status` / `customer_id` / `created_at` range filters, offset pagination, `created_at DESC, id DESC` ordering, a `total` that only counts rows matching the filters, and every error in the envelope. No new dependencies. Adjust the import paths to fit your layout.

### `app/schemas/orders.py`

```python
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

ORDER_STATUSES = ("pending", "paid", "shipped", "cancelled")


def _as_utc(value: datetime) -> datetime:
    # Naive input is treated as UTC; aware input is converted to UTC.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class OrderFilterParams(BaseModel):
    status: str | None = None
    customer_id: UUID | None = None
    created_from: datetime | None = None  # inclusive
    created_to: datetime | None = None    # exclusive
    page: int = Field(1, ge=1)
    page_size: int = Field(25, ge=1, le=100)

    @field_validator("status")
    @classmethod
    def check_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ORDER_STATUSES:
            raise ValueError(f"status must be one of {', '.join(ORDER_STATUSES)}")
        return v

    @field_validator("created_from")
    @classmethod
    def normalize_from(cls, v: datetime | None) -> datetime | None:
        return _as_utc(v) if v is not None else None

    @field_validator("created_to")
    @classmethod
    def normalize_to(cls, v: datetime | None, info: ValidationInfo) -> datetime | None:
        if v is None:
            return None
        v = _as_utc(v)
        start = info.data.get("created_from")
        if start is not None and v <= start:
            raise ValueError("created_to must be after created_from")
        return v


class OrderOut(BaseModel):
    # If you already have the single-order schema, reuse it and delete this.
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    status: str
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

`created_to` is exclusive, so `created_from=2026-11-01T00:00:00Z&created_to=2026-11-02T00:00:00Z` gives you exactly one day without any 23:59:59.999 hacks. asyncpg hands back UTC-aware datetimes, and Pydantic v2 serializes those with a `Z`, so the timestamp format is handled.

### `app/services/orders.py`

I pulled the query out of the route so you can test it straight against the session.

```python
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order
from app.schemas.orders import OrderFilterParams, OrderOut, OrderPage


async def search_orders(session: AsyncSession, params: OrderFilterParams) -> OrderPage:
    conditions = []
    if params.status is not None:
        conditions.append(Order.status == params.status)
    if params.customer_id is not None:
        conditions.append(Order.customer_id == params.customer_id)
    if params.created_from is not None:
        conditions.append(Order.created_at >= params.created_from)
    if params.created_to is not None:
        conditions.append(Order.created_at < params.created_to)

    total = await session.scalar(
        select(func.count()).select_from(Order).where(*conditions)
    )

    rows = await session.scalars(
        select(Order)
        .where(*conditions)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    )

    return OrderPage(
        items=[OrderOut.model_validate(o) for o in rows],
        page=params.page,
        page_size=params.page_size,
        total=total or 0,
    )
```

### `app/routers/orders.py`

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.orders import OrderFilterParams, OrderPage
from app.services.orders import search_orders

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=OrderPage)
async def list_orders(
    params: Annotated[OrderFilterParams, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrderPage:
    return await search_orders(session, params)
```

### `app/errors.py` (add this next to your `AppError` handler)

```python
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

_LOC_PREFIXES = {"query", "path", "body", "header", "cookie"}


def _validation_message(err: dict) -> str:
    # Our own ValueErrors carry a clean message, e.g. "status must be one of ...".
    ctx_error = err.get("ctx", {}).get("error")
    if err.get("type") == "value_error" and ctx_error is not None:
        return str(ctx_error)
    field = ".".join(str(p) for p in err.get("loc", ()) if p not in _LOC_PREFIXES)
    msg = err.get("msg", "invalid request")
    return f"{field}: {msg}" if field else msg


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    message = _validation_message(errors[0]) if errors else "invalid request"
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": message}},
    )


def register_error_handlers(app: FastAPI) -> None:
    # ... existing AppError registration ...
    app.add_exception_handler(RequestValidationError, validation_error_handler)
```

So `?status=refunded` gives you `422 {"error": {"code": "validation_error", "message": "status must be one of pending, paid, shipped, cancelled"}}`, and `?page_size=500` gives you `"page_size: Input should be less than or equal to 100"`. It only reports the first error. If you want all of them, join the messages.

### `tests/test_orders_search.py`

```python
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.models import Order
from app.schemas.orders import OrderFilterParams
from app.services.orders import search_orders


@pytest.mark.parametrize(
    "kwargs",
    [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"status": "refunded"}],
)
def test_filter_params_rejects_bad_input(kwargs):
    with pytest.raises(ValidationError):
        OrderFilterParams(**kwargs)


def test_created_range_must_be_ordered():
    t = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        OrderFilterParams(created_from=t, created_to=t)


@pytest.mark.asyncio
async def test_filters_total_and_ordering(session, customer):  # customer: your existing fixture
    base = datetime.now(timezone.utc)
    for i, status in enumerate(["paid", "paid", "paid", "pending"]):
        session.add(Order(
            customer_id=customer.id, status=status, total_cents=1000,
            currency="USD", shipping_country="US",
            created_at=base - timedelta(minutes=i),
        ))
    await session.flush()

    result = await search_orders(session, OrderFilterParams(status="paid", page_size=2))

    assert result.total == 3  # counts every matching row, not just this page
    assert len(result.items) == 2
    assert result.items[0].created_at > result.items[1].created_at

    page2 = await search_orders(session, OrderFilterParams(status="paid", page=2, page_size=2))
    assert len(page2.items) == 1
    assert {o.id for o in page2.items}.isdisjoint({o.id for o in result.items})
```

These all run on your savepoint-rollback `session` fixture, so nothing is left behind. I didn't write HTTP-level tests because `TestClient`/`AsyncClient` need `httpx`, and that isn't on the approved list. If it's already in your lockfile as a FastAPI test extra, a single test that hits `/orders?status=refunded` and checks the envelope would be worth adding.

Two things worth knowing:

- **Deep offsets get slow.** `page` has no upper bound, and `OFFSET 50000` still makes Postgres walk through all the rows it skips. Offset was the agreed approach, so it's fine for now. If this ever backs a "scroll everything" UI, switch to a `(created_at, id)` keyset cursor.
- **Indexes.** The separate `status` and `created_at` indexes work, but the most common query, filter by status and sort by date, would be better served by a composite `(status, created_at DESC, id DESC)` index, and `(customer_id, created_at DESC, id DESC)` for the customer case. Before you add a migration for either, check the plan with `EXPLAIN ANALYZE` on real data.
