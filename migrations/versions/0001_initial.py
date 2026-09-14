"""Initial 19-table schema; SQL snapshots do not import mutable application models."""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    for name in ("0001_schema.sql", "0001_invariants.sql"):
        op.execute(Path(__file__).with_name(name).read_text())
    # Role provisioned separately; schema ownership belongs to migration login.
    op.execute("REVOKE ALL ON SCHEMA call_summary FROM PUBLIC")
    op.execute("GRANT USAGE ON SCHEMA call_summary TO call_summary_app")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA call_summary TO call_summary_app"
    )
    op.execute("REVOKE ALL ON call_summary.alembic_version FROM call_summary_app")
    op.execute(
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA call_summary TO call_summary_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA call_summary GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO call_summary_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA call_summary GRANT USAGE, SELECT ON SEQUENCES TO call_summary_app"
    )


def downgrade():
    # Keep Alembic's own version table intact. Destructive only on explicit downgrade.
    op.execute("""DO $$ DECLARE obj record; BEGIN
      FOR obj IN SELECT tablename FROM pg_tables WHERE schemaname='call_summary' AND tablename<>'alembic_version' LOOP
        EXECUTE format('DROP TABLE call_summary.%I CASCADE', obj.tablename);
      END LOOP;
      FOR obj IN SELECT p.oid::regprocedure AS signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='call_summary' LOOP
        EXECUTE format('DROP FUNCTION %s CASCADE', obj.signature);
      END LOOP;
    END $$""")
