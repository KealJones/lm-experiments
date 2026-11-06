GIST: Long mixed-topic conversation with a backend engineer (Python 3.11, FastAPI) covering code review, design docs, Git, testing, Kubernetes, and Postgres. The user deferred writing the orders search endpoint until now.

REFERENCES RESOLVED: "the endpoint ... that we discussed" = the GET orders search/list endpoint (filter by status, customer_id, created_at range; page/page_size pagination; total count). "The orders table" = the schema below.

RELEVANT FACTS:
Stack: Python 3.11, FastAPI (recent), Pydantic v2 (model_validator/field_validator OK; query-param models via Annotated[FilterParams, Query()]), PostgreSQL 15, SQLAlchemy 2.0 async with asyncpg, deployed on Kubernetes (one uvicorn process per pod). Session dependency: async_sessionmaker(engine, expire_on_commit=False); `get_session` async generator; endpoints use `session: AsyncSession = Depends(get_session)`.

HARD RULES: (1) All errors use envelope {"error": {"code": "...", "message": "..."}}. Validation failures are HTTP 422 with code "validation_error", e.g. message "status must be one of pending, paid, shipped, cancelled"; handlers for AppError, RequestValidationError and Starlette HTTPException live in app/errors.py. (2) No new third-party dependencies (only FastAPI, Pydantic, SQLAlchemy, asyncpg, stdlib).

orders table: id UUID PK; customer_id UUID FK to customers; status text (pending, paid, shipped, cancelled); total_cents integer not null; currency 3-char code (e.g. USD); shipping_country 2-char code; created_at timestamptz default now(); updated_at timestamptz. Indexes on customer_id, status, created_at. (The SQLAlchemy model has NOT been written; the user said "not yet" earlier, so the endpoint code may need to include or assume it.)

Endpoint spec (confirmed by user):
- Filters: status (Literal/Enum of the four values), customer_id, created_at date range (from/to).
- Pagination: page (>=1) and page_size (default 25, min 1, max 100); offset pagination.
- Sort: created_at DESC, then id as secondary sort for determinism (user explicitly agreed).
- Response shape: {items, page, page_size, total}; total counts only rows matching the active filters. Order item schema should match the single-order endpoint schema.
- Timestamps serialized as ISO 8601 UTC (timezone-aware datetimes).
- Validation errors in the envelope as above.

Prior related patterns: get_order(session, order_id) returns Optional; a service layer function like get_order_or_404 raises AppError (e.g. code order_not_found, 404). Tests use pytest-asyncio with rollback-per-test sessions (join_transaction_mode="create_savepoint") and a get_session dependency override.
