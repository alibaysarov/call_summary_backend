"""Relational model. Public UUIDs; internal, workspace-scoped BIGINT references."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.elements import conv


class Base(DeclarativeBase):
    metadata = MetaData(
        schema="call_summary",
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        },
    )


def col(name, type_=Text, *, nullable=False, default=None):
    return Column(
        name,
        type_,
        nullable=nullable,
        server_default=text(default) if default is not None else None,
    )


def stamp(name, nullable=False):
    return col(
        name,
        DateTime(timezone=True),
        nullable=nullable,
        default=None if nullable else "now()",
    )


def jsoncol(name):
    return col(name, JSONB, default="'{}'::jsonb")


def choice(name, values):
    return CheckConstraint(
        f"{name} IN ({', '.join(repr(v) for v in values.split())})", name=name
    )


def unique(*names):
    return UniqueConstraint(*names, name=conv("uq_" + "_".join(names)))


def table(name, *columns, refs=(), uniques=(), checks=(), scoped=True):
    fields = [
        Column("int_id", BigInteger, Identity(always=True), primary_key=True),
        col("id", UUID(as_uuid=True), default="gen_random_uuid()"),
        UniqueConstraint("id"),
    ]
    if scoped:
        fields += [
            Column(
                "workspace_id",
                BigInteger,
                ForeignKey("call_summary.workspaces.int_id"),
                nullable=False,
            ),
            UniqueConstraint("workspace_id", "int_id"),
        ]
    fields += list(columns)
    for field, target, nullable in refs:
        fields += [
            col(field, BigInteger, nullable=nullable),
            ForeignKeyConstraint(
                ["workspace_id", field],
                [
                    f"call_summary.{target}.workspace_id",
                    f"call_summary.{target}.int_id",
                ],
                name=f"fk_{name}_{field}",
            ),
        ]
    fields += [unique(*u) for u in uniques] + list(checks)
    return Table(name, Base.metadata, *fields)


workspaces = table("workspaces", col("name"), stamp("created_at"), scoped=False)
integration_connections = table(
    "integration_connections",
    col("provider"),
    col("transport"),
    col("external_account_id"),
    col("external_scope"),
    col("status", default="'active'"),
    col("secret_ref", nullable=True),
    jsoncol("settings"),
    stamp("created_at"),
    stamp("updated_at"),
    uniques=[
        (
            "workspace_id",
            "provider",
            "transport",
            "external_scope",
            "external_account_id",
        )
    ],
    checks=[
        choice("transport", "upload integration"),
        choice("status", "active disabled error"),
    ],
)
integration_subscriptions = table(
    "integration_subscriptions",
    col("resource_key"),
    col("external_subscription_id", nullable=True),
    col("cursor", nullable=True),
    stamp("expires_at", True),
    stamp("last_synced_at", True),
    col("status", default="'active'"),
    refs=[("connection_id", "integration_connections", False)],
    uniques=[("connection_id", "resource_key")],
    checks=[choice("status", "active expired disabled error")],
)
integration_events = table(
    "integration_events",
    col("external_event_id", nullable=True),
    col("deduplication_key"),
    col("event_type"),
    stamp("occurred_at", True),
    stamp("received_at"),
    jsoncol("payload"),
    col("status", default="'pending'"),
    col("last_error", nullable=True),
    refs=[
        ("connection_id", "integration_connections", False),
        ("subscription_id", "integration_subscriptions", True),
        ("source_session_id", "source_sessions", True),
    ],
    uniques=[("connection_id", "deduplication_key")],
    checks=[choice("status", "pending processing succeeded failed ignored")],
)
meetings = table(
    "meetings",
    col("title"),
    stamp("started_at", True),
    stamp("ended_at", True),
    col("timezone", default="'UTC'"),
    col("status", default="'active'"),
    col("completeness_status", default="'pending'"),
    stamp("created_at"),
    checks=[
        choice("status", "active ended finalized failed"),
        choice("completeness_status", "pending complete incomplete"),
        CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="interval",
        ),
    ],
)
source_sessions = table(
    "source_sessions",
    col("external_session_id"),
    col("external_room_id", nullable=True),
    col("source_url", nullable=True),
    col("ingestion_mode"),
    col("status", default="'active'"),
    stamp("started_at", True),
    stamp("ended_at", True),
    jsoncol("metadata"),
    refs=[
        ("meeting_id", "meetings", False),
        ("connection_id", "integration_connections", False),
    ],
    uniques=[("connection_id", "external_session_id")],
    checks=[
        choice("status", "active ended failed"),
        choice(
            "ingestion_mode", "file_upload chunk_upload recording_import live_capture"
        ),
        CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="interval",
        ),
    ],
)
people = table("people", col("display_name"))
person_identities = table(
    "person_identities",
    col("provider"),
    col("identity_scope"),
    col("external_user_id"),
    col("display_name", nullable=True),
    col("verification_status", default="'unverified'"),
    stamp("linked_at", True),
    refs=[("person_id", "people", True)],
    uniques=[("workspace_id", "provider", "identity_scope", "external_user_id")],
    checks=[
        choice("verification_status", "unverified verified rejected"),
        CheckConstraint(
            "verification_status <> 'verified' OR person_id IS NOT NULL",
            name="verified_person",
        ),
    ],
)
meeting_participants = table(
    "meeting_participants",
    col("external_participant_id"),
    col("display_name"),
    col("role", nullable=True),
    refs=[
        ("source_session_id", "source_sessions", False),
        ("identity_id", "person_identities", True),
    ],
    uniques=[("source_session_id", "external_participant_id")],
)
participant_sessions = table(
    "participant_sessions",
    col("external_join_id"),
    stamp("joined_at", True),
    stamp("left_at", True),
    refs=[("participant_id", "meeting_participants", False)],
    uniques=[("participant_id", "external_join_id")],
    checks=[
        CheckConstraint(
            "left_at IS NULL OR joined_at IS NULL OR left_at >= joined_at",
            name="interval",
        )
    ],
)
meeting_speakers = table(
    "meeting_speakers",
    col("display_label"),
    col("identification_status", default="'unknown'"),
    col("identification_method", default="'unknown'"),
    refs=[
        ("meeting_id", "meetings", False),
        ("person_id", "people", True),
        ("participant_id", "meeting_participants", True),
    ],
    checks=[
        choice("identification_status", "unknown proposed confirmed rejected"),
        choice("identification_method", "unknown manual provider voice"),
    ],
)
audio_streams = table(
    "audio_streams",
    col("external_stream_key"),
    col("kind"),
    col("timeline_offset_ms", BigInteger, default="0"),
    col("status", default="'active'"),
    col("expected_chunk_count", BigInteger, nullable=True),
    col("is_primary", Boolean, default="true"),
    jsoncol("metadata"),
    refs=[
        ("source_session_id", "source_sessions", False),
        ("participant_session_id", "participant_sessions", True),
    ],
    uniques=[("source_session_id", "external_stream_key")],
    checks=[
        choice("kind", "mixed per_person"),
        choice("status", "active ended failed"),
        CheckConstraint(
            "timeline_offset_ms >= 0 AND (expected_chunk_count IS NULL OR expected_chunk_count >= 0)",
            name="bounds",
        ),
    ],
)
audio_chunks = table(
    "audio_chunks",
    col("sequence_no", BigInteger),
    col("offset_ms", BigInteger),
    col("duration_ms", BigInteger),
    stamp("captured_at", True),
    stamp("received_at"),
    col("storage_key"),
    col("sha256"),
    col("mime_type"),
    col("result_text", default="''"),
    col("transcription_status", default="'pending'"),
    col("analysis_status", default="'pending'"),
    col("processing_version", BigInteger, default="1"),
    stamp("created_at"),
    refs=[("meeting_id", "meetings", False), ("stream_id", "audio_streams", False)],
    uniques=[("stream_id", "sequence_no")],
    checks=[
        choice("transcription_status", "pending processing succeeded failed"),
        choice("analysis_status", "pending processing succeeded failed skipped"),
        CheckConstraint(
            "sequence_no >= 0 AND offset_ms >= 0 AND duration_ms >= 0 AND processing_version > 0",
            name="bounds",
        ),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        CheckConstraint(
            "storage_key ~ '^[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}\\.[a-z0-9]+$'",
            name="storage_key",
        ),
    ],
)
chunk_speakers = table(
    "chunk_speakers",
    col("local_label"),
    refs=[
        ("chunk_id", "audio_chunks", False),
        ("meeting_speaker_id", "meeting_speakers", True),
    ],
    uniques=[("chunk_id", "local_label")],
)
utterances = table(
    "utterances",
    col("ordinal", BigInteger),
    col("start_ms", BigInteger),
    col("end_ms", BigInteger),
    col("text"),
    refs=[
        ("meeting_id", "meetings", False),
        ("chunk_id", "audio_chunks", False),
        ("chunk_speaker_id", "chunk_speakers", True),
    ],
    uniques=[("chunk_id", "ordinal")],
    checks=[
        CheckConstraint(
            "ordinal >= 0 AND start_ms >= 0 AND end_ms >= start_ms", name="bounds"
        )
    ],
)
action_items = table(
    "action_items",
    col("description"),
    col("deadline_text", nullable=True),
    stamp("due_at", True),
    col("status", default="'open'"),
    col("review_status", default="'needs_review'"),
    stamp("created_at"),
    stamp("updated_at"),
    refs=[("meeting_id", "meetings", False), ("assignee_id", "people", True)],
    checks=[
        choice("status", "open in_progress done cancelled"),
        choice("review_status", "needs_review confirmed"),
    ],
)
action_item_sources = table(
    "action_item_sources",
    refs=[
        ("action_item_id", "action_items", False),
        ("utterance_id", "utterances", False),
    ],
    uniques=[("action_item_id", "utterance_id")],
)
action_item_events = table(
    "action_item_events",
    col("event_type"),
    jsoncol("previous_values"),
    jsoncol("new_values"),
    stamp("created_at"),
    refs=[
        ("action_item_id", "action_items", False),
        ("source_utterance_id", "utterances", True),
    ],
)
processing_jobs = table(
    "processing_jobs",
    col("kind"),
    col("status", default="'pending'"),
    col("attempts", BigInteger, default="0"),
    stamp("available_at"),
    stamp("lease_until", True),
    col("lease_token", UUID(as_uuid=True), nullable=True),
    col("last_error", nullable=True),
    col("deduplication_key"),
    refs=[
        ("subscription_id", "integration_subscriptions", True),
        ("integration_event_id", "integration_events", True),
        ("chunk_id", "audio_chunks", True),
        ("meeting_id", "meetings", True),
    ],
    uniques=[("workspace_id", "deduplication_key")],
    checks=[
        choice("status", "pending running succeeded failed cancelled"),
        choice(
            "kind",
            "ingestion transcription analysis finalization poll renew_subscription",
        ),
        CheckConstraint("attempts >= 0", name="attempts"),
        CheckConstraint(
            "(status = 'running' AND lease_until IS NOT NULL AND lease_token IS NOT NULL) OR (status <> 'running' AND lease_until IS NULL AND lease_token IS NULL)",
            name="lease",
        ),
        CheckConstraint(
            """(kind = 'ingestion' AND integration_event_id IS NOT NULL AND chunk_id IS NULL AND subscription_id IS NULL)
      OR (kind IN ('transcription', 'analysis') AND chunk_id IS NOT NULL AND integration_event_id IS NULL AND subscription_id IS NULL)
      OR (kind = 'finalization' AND meeting_id IS NOT NULL AND chunk_id IS NULL AND integration_event_id IS NULL AND subscription_id IS NULL)
      OR (kind IN ('poll', 'renew_subscription') AND subscription_id IS NOT NULL AND chunk_id IS NULL AND integration_event_id IS NULL AND meeting_id IS NULL)""",
            name="kind_target",
        ),
    ],
)

for tbl, cols in [
    (utterances, ("workspace_id", "meeting_id", "start_ms", "int_id")),
    (action_items, ("workspace_id", "assignee_id", "status", "meeting_id")),
    (action_items, ("workspace_id", "meeting_id", "created_at", "int_id")),
    (meetings, ("workspace_id", "started_at", "int_id")),
    (source_sessions, ("workspace_id", "meeting_id")),
    (integration_events, ("connection_id", "received_at", "int_id")),
    (processing_jobs, ("status", "available_at")),
]:
    Index("ix_" + tbl.name + "_" + "_".join(cols), *(tbl.c[c] for c in cols))


# Explicit ORM names with the same Core tables used by bulk ingestion and migrations.
class Workspace(Base):
    __table__ = workspaces


class IntegrationConnection(Base):
    __table__ = integration_connections


class IntegrationSubscription(Base):
    __table__ = integration_subscriptions


class IntegrationEvent(Base):
    __table__ = integration_events


class Meeting(Base):
    __table__ = meetings


class SourceSession(Base):
    __table__ = source_sessions


class Person(Base):
    __table__ = people


class PersonIdentity(Base):
    __table__ = person_identities


class MeetingParticipant(Base):
    __table__ = meeting_participants


class ParticipantSession(Base):
    __table__ = participant_sessions


class MeetingSpeaker(Base):
    __table__ = meeting_speakers


class AudioStream(Base):
    __table__ = audio_streams


class AudioChunk(Base):
    __table__ = audio_chunks


class ChunkSpeaker(Base):
    __table__ = chunk_speakers


class Utterance(Base):
    __table__ = utterances


class ActionItem(Base):
    __table__ = action_items


class ActionItemSource(Base):
    __table__ = action_item_sources


class ActionItemEvent(Base):
    __table__ = action_item_events


class ProcessingJob(Base):
    __table__ = processing_jobs
