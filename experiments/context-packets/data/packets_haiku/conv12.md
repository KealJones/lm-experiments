GIST: The user is building a Python 3.11 FastAPI backend on PostgreSQL 15 with SQLAlchemy 2.0 async (asyncpg), deployed on Kubernetes. The conversation covered code reviews, design docs, Git, testing, migrations, and the design of the orders search API.

REFERENCES RESOLVED: "the endpoint for paginated search over the orders table that we discussed" is the orders search endpoint specified in the conversation: filters on status, customer_id, and a created_at date range, page/page_size pagination, and created_at descending order.

RELEVANT FACTS:
- Hard rules: every error uses the envelope {"error": {"code": "...", "message": "..."}}. No new third-party dependencies without architecture group approval. Use only what is already present: FastAPI, Pydantic v2, SQLAlchemy, asyncpg, pytest-asyncio, and the standard library.
- Orders table: id (UUID PK), customer_id (UUID FK to customers), status (text: pending, paid, shipped, cancelled), total_cents (int, not null), currency (3-char code), shipping_country (2-char code), created_at (timestamptz, default now()), updated_at (timestamptz). Indexes exist on customer_id, status, and created_at.
- Filters: status, customer_id, and created_at range. All are optional.
- Pagination: page (minimum 1) and page_size (default 25, range 1 to 100). Offset pagination is accepted.
- Ordering: created_at DESC, with id as a secondary sort so ordering is deterministic.
- Response shape: an object with items, page, page_size, and total. total counts only rows matching the active filters. Each item should match the single-order representation.
- Validation failures (bad page, page_size out of range, invalid status) return 422 with code validation_error. Example message: "status must be one of pending, paid, shipped, cancelled". The RequestValidationError handler should produce the envelope.
- Error plumbing: a custom AppError carrying status, code, and message, with handlers registered in app/errors.py.
- Query parameters: declare a Pydantic v2 model and receive it with Annotated[FilterParams, Query()]. Use field_validator.
- Session: engine from create_async_engine with postgresql+asyncpg; async_sessionmaker(expire_on_commit=False); get_session is an async generator dependency injected with Depends.
- Timestamps: timezone-aware UTC, serialized as ISO 8601 with Z. Use datetime.now(timezone.utc), not utcnow.
- Tests: pytest-asyncio, with per-test rollback (join_transaction_mode="create_savepoint"). The test session fixture overrides get_session.
