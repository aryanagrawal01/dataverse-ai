"""Alembic migration environment.

Resolves the database URL from app settings (env vars / .env), so migrations
always target the same database the app uses.
"""

from logging.config import fileConfig

from alembic import context

from dataverse.config import get_settings

# Import all model modules so autogenerate sees every table.
from dataverse.models import Base  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Reuse the app's engine factory: it creates the SQLite data directory
    # and applies connection pragmas, so migrations and app always agree.
    from dataverse.repositories.base import get_engine

    with get_engine().connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
