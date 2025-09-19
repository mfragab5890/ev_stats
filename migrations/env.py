# migrations/env.py
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# --- Add project root to sys.path so we can import your app and models ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# --- Import your Flask app and SQLAlchemy metadata ---
from app import app           # your Flask app (already configures SQLALCHEMY_DATABASE_URI)
from apps.ev.models import db # imports models so Alembic “sees” tables

# --- Alembic Config ---
config = context.config

# If you prefer, you can leave alembic.ini's sqlalchemy.url as a dummy; we override it here:
config.set_main_option("sqlalchemy.url", app.config["SQLALCHEMY_DATABASE_URI"])

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is the target metadata for 'autogenerate'
target_metadata = db.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,             # detect type changes
        compare_server_default=True,   # detect default changes
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
