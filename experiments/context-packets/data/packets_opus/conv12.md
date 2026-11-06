GIST: A backend engineer working through a series of work items (code reviews, design docs, Git, testing) on a Python FastAPI service. Earlier they described the orders table and the search requirements and said they would ask for the endpoint later.

REFERENCES RESOLVED: "the endpoint for paginated search over the orders table that we discussed" = a GET list/search endpoint for orders with filters, offset pagination, sorting and a total count, as specified below.

RELEVANT FACTS:
- Stack: Python 3.11, FastAPI (recent), Pydantic v2, PostgreSQL 15, SQLAlchemy 2.0 async with asyncpg, uvicorn, Kubernetes.
- Hard rules: (1) every error uses the envelope {"error": {"code": "...", "message": "..."}}; (2) NO new third-party dependencies. Only FastAPI, Pydantic, SQLAlchemy, asyncpg and the standard library.
- Orders table: id UUID PK; customer_id UUID FK to customers; status text (pending, paid, shipped, cancelled); total_cents int not null; currency 3-char code; shipping_country 2-char code; created_at timestamptz default now(); updated_at timestamptz. Indexes on customer_id, status, created_at. No SQLAlchemy model written yet; the user deferred it, so the endpoint likely needs one.
- Endpoint spec: optional filters status, customer_id, created_at date range (from/to; exact param names not fixed). Params page (>=1, default 1) and page_size (default 25, 1-100). Sort by created_at DESC, then id as a secondary sort (agreed). Response object: {items, page, page_size, total}, where total counts only rows matching the filters. Item schema should match the single-order representation.
- Validation failures: HTTP 422, code "validation_error", in the envelope (e.g. "status must be one of pending, paid, shipped, cancelled"). Use a Literal/Enum for status. Pydantic query model via Annotated[FilterParams, Query()] is OK; model_validator can check that the range start is not after the end.
- Existing conventions: AppError (status, code, message) plus handlers in app/errors.py, including overrides for RequestValidationError and HTTPException. Session dependency get_session() via async_sessionmaker(expire_on_commit=False), injected with Depends.
- Timestamps: timezone-aware UTC, serialized as ISO 8601.
- Earlier caveats: offset pagination gets slow on deep pages, and COUNT can be costly on very large tables.
- Tests use pytest-asyncio with a rollback-per-test session.
