import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

from call_summary.db.models import Base

load_dotenv()
url = os.environ["MIGRATION_DATABASE_URL"]


def configure(connection=None):
    context.configure(
        connection=connection,
        url=url if connection is None else None,
        target_metadata=Base.metadata,
        include_schemas=True,
        version_table_schema="call_summary",
        compare_type=True,
    )


if context.is_offline_mode():
    configure()
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        configure(connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
