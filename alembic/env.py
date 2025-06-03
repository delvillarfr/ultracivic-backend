"""
Alembic environment for Ultra Civic
-----------------------------------

• Reads DATABASE_URL_SYNC from .env via Settings
• Points Alembic at SQLModel.metadata for autogenerate to work
• Uses a *sync* SQLAlchemy engine for migrations (safe for both
  'revision --autogenerate' and 'upgrade')
"""

from logging.config import fileConfig
from alembic import context  # type: ignore[attr-defined]
from sqlalchemy import create_engine, pool

# ─── App imports ────────────────────────────────────────────────────────
from app.core.config import get_settings
from app import models  # noqa: F401  → imports all model modules (User, etc.)
from sqlmodel import SQLModel

# ─── Load DB URL from .env ──────────────────────────────────────────────
settings = get_settings()
config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

# ─── Logging (optional) ────────────────────────────────────────────────
if config.config_file_name:
    fileConfig(config.config_file_name)

# ─── Metadata target for autogenerate ──────────────────────────────────
target_metadata = SQLModel.metadata

# ─── OFFLINE (rare) ────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Generate SQL script without connecting to the DB."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

# ─── ONLINE (normal) ───────────────────────────────────────────────────
def run_migrations_online() -> None:
    """Run migrations against a live database using a *sync* engine."""
    connectable = create_engine(                 # ← sync psycopg2 engine
        settings.database_url_sync,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,   # detect column-type changes
        )
        with context.begin_transaction():
            context.run_migrations()

# ─── Entrypoint ────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

