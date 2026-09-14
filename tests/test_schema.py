from uuid import uuid4

import pytest
from sqlalchemy import inspect, text, update
from sqlalchemy.exc import IntegrityError, ProgrammingError

from call_summary.db import models as m


def add(conn, table, **values):
    return conn.execute(
        table.insert().values(**values).returning(table.c.int_id)
    ).scalar_one()


def invalid(conn, statement):
    with pytest.raises(IntegrityError), conn.begin_nested():
        conn.execute(statement)


@pytest.fixture
def graph(conn):
    ws = add(conn, m.workspaces, name="test")
    other_ws = add(conn, m.workspaces, name="other")
    meeting = add(conn, m.meetings, workspace_id=ws, title="first")
    other_meeting = add(conn, m.meetings, workspace_id=ws, title="second")
    connection = add(
        conn,
        m.integration_connections,
        workspace_id=ws,
        provider="manual",
        transport="upload",
        external_account_id="local",
        external_scope="local",
    )
    source = add(
        conn,
        m.source_sessions,
        workspace_id=ws,
        meeting_id=meeting,
        connection_id=connection,
        external_session_id="session",
        ingestion_mode="file_upload",
    )
    streams = [
        add(
            conn,
            m.audio_streams,
            workspace_id=ws,
            source_session_id=source,
            external_stream_key=str(i),
            kind="mixed",
        )
        for i in range(2)
    ]
    chunk_values = {
        "workspace_id": ws,
        "meeting_id": meeting,
        "sequence_no": 0,
        "offset_ms": 0,
        "duration_ms": 1000,
        "storage_key": "/".join(str(uuid4()) for _ in range(4)) + ".ogg",
        "sha256": "a" * 64,
        "mime_type": "audio/ogg",
    }
    chunks = [add(conn, m.audio_chunks, stream_id=s, **chunk_values) for s in streams]
    utterance = add(
        conn,
        m.utterances,
        workspace_id=ws,
        meeting_id=meeting,
        chunk_id=chunks[0],
        ordinal=0,
        start_ms=0,
        end_ms=100,
        text="synthetic",
    )
    action = add(
        conn,
        m.action_items,
        workspace_id=ws,
        meeting_id=meeting,
        description="synthetic",
    )
    return {
        "ws": ws,
        "other_ws": other_ws,
        "meeting": meeting,
        "other_meeting": other_meeting,
        "source": source,
        "connection": connection,
        "streams": streams,
        "chunks": chunks,
        "chunk_values": chunk_values,
        "utterance": utterance,
        "action": action,
    }


def test_catalog_contract(engine):
    inspector = inspect(engine)
    names = set(inspector.get_table_names(schema="call_summary")) - {"alembic_version"}
    assert names == {t.name for t in m.Base.metadata.tables.values()}
    assert len(names) == 19
    for name in names:
        cols = {
            c["name"]: c for c in inspector.get_columns(name, schema="call_summary")
        }
        assert str(cols["id"]["type"]) == "UUID" and not cols["id"]["nullable"]
        assert "gen_random_uuid()" in cols["id"]["default"]
        assert (
            str(cols["int_id"]["type"]) == "BIGINT"
            and cols["int_id"]["identity"]["always"]
        )
        assert inspector.get_pk_constraint(name, schema="call_summary")[
            "constrained_columns"
        ] == ["int_id"]
        assert ["id"] in [
            u["column_names"]
            for u in inspector.get_unique_constraints(name, schema="call_summary")
        ]
        for fk in inspector.get_foreign_keys(name, schema="call_summary"):
            assert fk["referred_columns"] in (["int_id"], ["workspace_id", "int_id"])
            for c in fk["constrained_columns"]:
                assert str(cols[c]["type"]) == "BIGINT"
            if fk["referred_table"] != "workspaces":
                assert fk["constrained_columns"][0] == "workspace_id"


def test_workspace_and_meeting_isolation(conn, graph):
    g = graph
    invalid(
        conn,
        m.source_sessions.insert().values(
            workspace_id=g["other_ws"],
            meeting_id=g["meeting"],
            connection_id=g["connection"],
            external_session_id="bad",
            ingestion_mode="file_upload",
        ),
    )
    invalid(
        conn,
        m.audio_chunks.insert().values(
            **(
                g["chunk_values"]
                | {
                    "meeting_id": g["other_meeting"],
                    "stream_id": g["streams"][0],
                    "sequence_no": 1,
                }
            )
        ),
    )
    invalid(
        conn,
        m.utterances.insert().values(
            workspace_id=g["ws"],
            meeting_id=g["other_meeting"],
            chunk_id=g["chunks"][0],
            ordinal=1,
            start_ms=0,
            end_ms=1,
            text="bad",
        ),
    )
    invalid(
        conn,
        update(m.source_sessions)
        .where(m.source_sessions.c.int_id == g["source"])
        .values(meeting_id=g["other_meeting"]),
    )


def test_stream_sequences_and_intervals(conn, graph):
    g = graph
    assert len(g["chunks"]) == 2
    invalid(
        conn,
        m.audio_chunks.insert().values(**g["chunk_values"], stream_id=g["streams"][0]),
    )
    invalid(
        conn,
        m.audio_chunks.insert().values(
            **(g["chunk_values"] | {"sequence_no": -1}), stream_id=g["streams"][0]
        ),
    )
    invalid(
        conn,
        m.utterances.insert().values(
            workspace_id=g["ws"],
            meeting_id=g["meeting"],
            chunk_id=g["chunks"][0],
            ordinal=1,
            start_ms=20,
            end_ms=10,
            text="bad",
        ),
    )


def test_action_sources(conn, graph):
    g = graph
    values = {
        "workspace_id": g["ws"],
        "action_item_id": g["action"],
        "utterance_id": g["utterance"],
    }
    add(conn, m.action_item_sources, **values)
    invalid(conn, m.action_item_sources.insert().values(**values))
    other_action = add(
        conn,
        m.action_items,
        workspace_id=g["ws"],
        meeting_id=g["other_meeting"],
        description="other",
    )
    invalid(
        conn,
        m.action_item_sources.insert().values(
            **(values | {"action_item_id": other_action})
        ),
    )
    invalid(
        conn,
        m.action_item_events.insert().values(
            workspace_id=g["ws"],
            action_item_id=other_action,
            source_utterance_id=g["utterance"],
            event_type="created",
        ),
    )


def test_chunk_speaker_attribution(conn, graph):
    g = graph
    speaker = add(
        conn,
        m.meeting_speakers,
        workspace_id=g["ws"],
        meeting_id=g["other_meeting"],
        display_label="unknown",
    )
    invalid(
        conn,
        m.chunk_speakers.insert().values(
            workspace_id=g["ws"],
            chunk_id=g["chunks"][0],
            local_label="0",
            meeting_speaker_id=speaker,
        ),
    )
    local = add(
        conn,
        m.chunk_speakers,
        workspace_id=g["ws"],
        chunk_id=g["chunks"][1],
        local_label="0",
    )
    invalid(
        conn,
        update(m.utterances)
        .where(m.utterances.c.int_id == g["utterance"])
        .values(chunk_speaker_id=local),
    )


@pytest.mark.parametrize(
    "kind",
    [
        "ingestion",
        "transcription",
        "analysis",
        "finalization",
        "poll",
        "renew_subscription",
        "invalid",
    ],
)
def test_job_requires_target(conn, graph, kind):
    invalid(
        conn,
        m.processing_jobs.insert().values(
            workspace_id=graph["ws"], kind=kind, deduplication_key=kind
        ),
    )


def test_job_lease_and_deduplication(conn, graph):
    g = graph
    values = {
        "workspace_id": g["ws"],
        "kind": "transcription",
        "chunk_id": g["chunks"][0],
        "deduplication_key": "transcribe",
    }
    add(conn, m.processing_jobs, **values)
    invalid(conn, m.processing_jobs.insert().values(**values))
    invalid(
        conn,
        m.processing_jobs.insert().values(
            **(values | {"deduplication_key": "bad", "status": "running"})
        ),
    )
    invalid(
        conn,
        m.processing_jobs.insert().values(
            **(values | {"deduplication_key": "bad", "meeting_id": g["other_meeting"]})
        ),
    )


def test_application_role_has_no_ddl_or_migration_write(conn):
    assert conn.scalar(text("SELECT current_user")) == "call_summary_app"
    with pytest.raises(ProgrammingError), conn.begin_nested():
        conn.execute(text("CREATE TABLE call_summary.not_allowed (id int)"))
    with pytest.raises(ProgrammingError), conn.begin_nested():
        conn.execute(text("DELETE FROM call_summary.alembic_version"))
