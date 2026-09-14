"""Idempotent local workspace only; no authorized provider accounts."""

from sqlalchemy.dialects.postgresql import insert

from call_summary.config import get_settings
from call_summary.db.models import workspaces
from call_summary.db.session import get_engine


def main():
    with get_engine().begin() as conn:
        conn.execute(
            insert(workspaces)
            .values(id=get_settings().local_workspace_id, name="Local")
            .on_conflict_do_nothing(index_elements=[workspaces.c.id])
        )


if __name__ == "__main__":
    main()
