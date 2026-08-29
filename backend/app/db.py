"""
ReconLens — database engine setup.

PRODUCTION TARGET IS POSTGRESQL. This sandbox has a real PostgreSQL 16
instance running (installed and started for this project — see
docs/architecture.md Phase 5 notes) and DATABASE_URL defaults to it.

SQLite is used ONLY as an isolated-test fallback (e.g. if DATABASE_URL is
unset and no Postgres is reachable), per spec section 21's explicit
allowance — never silently substituted as the "real" persistence layer.
All models use only cross-dialect-portable SQLAlchemy types (no
Postgres-only column types) specifically so the test suite can run against
SQLite without masking a dialect-specific bug that would only appear in
production Postgres.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://postgres:reconlens@localhost:5432/reconlens"
)

# Isolated-test override: tests explicitly request SQLite via this env var
# rather than ever silently falling back to it in normal operation.
if os.environ.get("RECONLENS_TEST_SQLITE") == "1":
    DATABASE_URL = "sqlite:///:memory:"

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# SQLite's :memory: creates a SEPARATE database per connection by default —
# a real bug caught while adding FastAPI TestClient coverage in Phase 6:
# the test fixture's create_all() and the API's own request-scoped session
# were silently hitting two different in-memory databases. StaticPool keeps
# every connection on one shared in-memory DB for the life of the engine,
# which is what an isolated-test SQLite setup actually needs.
engine_kwargs = {"connect_args": connect_args}
if DATABASE_URL == "sqlite:///:memory:":
    engine_kwargs["poolclass"] = StaticPool
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. In production this should be superseded by Alembic
    migrations (scaffolded in backend/alembic/) — used directly here only to
    stand the schema up for this sandbox's demonstration and test runs."""
    from backend.app.models import (  # noqa: F401 — import registers tables on Base
        batch, source_record, decision, evidence, review, exception as exc_model, audit,
    )
    Base.metadata.create_all(bind=engine)
