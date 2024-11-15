from __future__ import with_statement

import pathlib

# Add the path of your app to sys.path
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlmodel import SQLModel

from alembic import context
from app.config import settings
from app.models import *  # Import your models

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

# Create a standard synchronous engine
sync_engine = create_engine(settings.DB_SYNC_URL)

# Alembic configuration
config = context.config
fileConfig(config.config_file_name)
target_metadata = SQLModel.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.
    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.
    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = settings.DB_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode using a synchronous engine."""
    with sync_engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
