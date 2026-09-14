
CREATE TABLE call_summary.workspaces (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	name TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_workspaces PRIMARY KEY (int_id), 
	CONSTRAINT uq_workspaces_id UNIQUE (id)
)

;

CREATE TABLE call_summary.integration_connections (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	provider TEXT NOT NULL, 
	transport TEXT NOT NULL, 
	external_account_id TEXT NOT NULL, 
	external_scope TEXT NOT NULL, 
	status TEXT DEFAULT 'active' NOT NULL, 
	secret_ref TEXT, 
	settings JSONB DEFAULT '{}'::jsonb NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_integration_connections PRIMARY KEY (int_id), 
	CONSTRAINT ck_integration_connections_transport CHECK (transport IN ('upload', 'integration')), 
	CONSTRAINT ck_integration_connections_status CHECK (status IN ('active', 'disabled', 'error')), 
	CONSTRAINT uq_integration_connections_id UNIQUE (id), 
	CONSTRAINT uq_integration_connections_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT uq_workspace_id_provider_transport_external_scope_exter_5b95 UNIQUE (workspace_id, provider, transport, external_scope, external_account_id), 
	CONSTRAINT fk_integration_connections_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;

CREATE TABLE call_summary.meetings (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	title TEXT NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	ended_at TIMESTAMP WITH TIME ZONE, 
	timezone TEXT DEFAULT 'UTC' NOT NULL, 
	status TEXT DEFAULT 'active' NOT NULL, 
	completeness_status TEXT DEFAULT 'pending' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_meetings PRIMARY KEY (int_id), 
	CONSTRAINT ck_meetings_status CHECK (status IN ('active', 'ended', 'finalized', 'failed')), 
	CONSTRAINT ck_meetings_completeness_status CHECK (completeness_status IN ('pending', 'complete', 'incomplete')), 
	CONSTRAINT ck_meetings_interval CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at), 
	CONSTRAINT uq_meetings_id UNIQUE (id), 
	CONSTRAINT uq_meetings_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_meetings_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;
CREATE INDEX ix_meetings_workspace_id_started_at_int_id ON call_summary.meetings (workspace_id, started_at, int_id);

CREATE TABLE call_summary.people (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	display_name TEXT NOT NULL, 
	CONSTRAINT pk_people PRIMARY KEY (int_id), 
	CONSTRAINT uq_people_id UNIQUE (id), 
	CONSTRAINT uq_people_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_people_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;

CREATE TABLE call_summary.action_items (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	description TEXT NOT NULL, 
	deadline_text TEXT, 
	due_at TIMESTAMP WITH TIME ZONE, 
	status TEXT DEFAULT 'open' NOT NULL, 
	review_status TEXT DEFAULT 'needs_review' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	meeting_id BIGINT NOT NULL, 
	assignee_id BIGINT, 
	CONSTRAINT pk_action_items PRIMARY KEY (int_id), 
	CONSTRAINT ck_action_items_status CHECK (status IN ('open', 'in_progress', 'done', 'cancelled')), 
	CONSTRAINT ck_action_items_review_status CHECK (review_status IN ('needs_review', 'confirmed')), 
	CONSTRAINT uq_action_items_id UNIQUE (id), 
	CONSTRAINT uq_action_items_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_action_items_meeting_id FOREIGN KEY(workspace_id, meeting_id) REFERENCES call_summary.meetings (workspace_id, int_id), 
	CONSTRAINT fk_action_items_assignee_id FOREIGN KEY(workspace_id, assignee_id) REFERENCES call_summary.people (workspace_id, int_id), 
	CONSTRAINT fk_action_items_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;
CREATE INDEX ix_action_items_workspace_id_assignee_id_status_meeting_id ON call_summary.action_items (workspace_id, assignee_id, status, meeting_id);
CREATE INDEX ix_action_items_workspace_id_meeting_id_created_at_int_id ON call_summary.action_items (workspace_id, meeting_id, created_at, int_id);

CREATE TABLE call_summary.integration_subscriptions (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	resource_key TEXT NOT NULL, 
	external_subscription_id TEXT, 
	cursor TEXT, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	last_synced_at TIMESTAMP WITH TIME ZONE, 
	status TEXT DEFAULT 'active' NOT NULL, 
	connection_id BIGINT NOT NULL, 
	CONSTRAINT pk_integration_subscriptions PRIMARY KEY (int_id), 
	CONSTRAINT ck_integration_subscriptions_status CHECK (status IN ('active', 'expired', 'disabled', 'error')), 
	CONSTRAINT uq_integration_subscriptions_id UNIQUE (id), 
	CONSTRAINT uq_integration_subscriptions_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_integration_subscriptions_connection_id FOREIGN KEY(workspace_id, connection_id) REFERENCES call_summary.integration_connections (workspace_id, int_id), 
	CONSTRAINT uq_connection_id_resource_key UNIQUE (connection_id, resource_key), 
	CONSTRAINT fk_integration_subscriptions_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;

CREATE TABLE call_summary.person_identities (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	provider TEXT NOT NULL, 
	identity_scope TEXT NOT NULL, 
	external_user_id TEXT NOT NULL, 
	display_name TEXT, 
	verification_status TEXT DEFAULT 'unverified' NOT NULL, 
	linked_at TIMESTAMP WITH TIME ZONE, 
	person_id BIGINT, 
	CONSTRAINT pk_person_identities PRIMARY KEY (int_id), 
	CONSTRAINT ck_person_identities_verification_status CHECK (verification_status IN ('unverified', 'verified', 'rejected')), 
	CONSTRAINT ck_person_identities_verified_person CHECK (verification_status <> 'verified' OR person_id IS NOT NULL), 
	CONSTRAINT uq_person_identities_id UNIQUE (id), 
	CONSTRAINT uq_person_identities_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_person_identities_person_id FOREIGN KEY(workspace_id, person_id) REFERENCES call_summary.people (workspace_id, int_id), 
	CONSTRAINT uq_workspace_id_provider_identity_scope_external_user_id UNIQUE (workspace_id, provider, identity_scope, external_user_id), 
	CONSTRAINT fk_person_identities_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;

CREATE TABLE call_summary.source_sessions (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	external_session_id TEXT NOT NULL, 
	external_room_id TEXT, 
	source_url TEXT, 
	ingestion_mode TEXT NOT NULL, 
	status TEXT DEFAULT 'active' NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	ended_at TIMESTAMP WITH TIME ZONE, 
	metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
	meeting_id BIGINT NOT NULL, 
	connection_id BIGINT NOT NULL, 
	CONSTRAINT pk_source_sessions PRIMARY KEY (int_id), 
	CONSTRAINT ck_source_sessions_status CHECK (status IN ('active', 'ended', 'failed')), 
	CONSTRAINT ck_source_sessions_ingestion_mode CHECK (ingestion_mode IN ('file_upload', 'chunk_upload', 'recording_import', 'live_capture')), 
	CONSTRAINT ck_source_sessions_interval CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at), 
	CONSTRAINT uq_source_sessions_id UNIQUE (id), 
	CONSTRAINT uq_source_sessions_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_source_sessions_meeting_id FOREIGN KEY(workspace_id, meeting_id) REFERENCES call_summary.meetings (workspace_id, int_id), 
	CONSTRAINT fk_source_sessions_connection_id FOREIGN KEY(workspace_id, connection_id) REFERENCES call_summary.integration_connections (workspace_id, int_id), 
	CONSTRAINT uq_connection_id_external_session_id UNIQUE (connection_id, external_session_id), 
	CONSTRAINT fk_source_sessions_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;
CREATE INDEX ix_source_sessions_workspace_id_meeting_id ON call_summary.source_sessions (workspace_id, meeting_id);

CREATE TABLE call_summary.integration_events (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	external_event_id TEXT, 
	deduplication_key TEXT NOT NULL, 
	event_type TEXT NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE, 
	received_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	payload JSONB DEFAULT '{}'::jsonb NOT NULL, 
	status TEXT DEFAULT 'pending' NOT NULL, 
	last_error TEXT, 
	connection_id BIGINT NOT NULL, 
	subscription_id BIGINT, 
	source_session_id BIGINT, 
	CONSTRAINT pk_integration_events PRIMARY KEY (int_id), 
	CONSTRAINT ck_integration_events_status CHECK (status IN ('pending', 'processing', 'succeeded', 'failed', 'ignored')), 
	CONSTRAINT uq_integration_events_id UNIQUE (id), 
	CONSTRAINT uq_integration_events_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_integration_events_connection_id FOREIGN KEY(workspace_id, connection_id) REFERENCES call_summary.integration_connections (workspace_id, int_id), 
	CONSTRAINT fk_integration_events_subscription_id FOREIGN KEY(workspace_id, subscription_id) REFERENCES call_summary.integration_subscriptions (workspace_id, int_id), 
	CONSTRAINT fk_integration_events_source_session_id FOREIGN KEY(workspace_id, source_session_id) REFERENCES call_summary.source_sessions (workspace_id, int_id), 
	CONSTRAINT uq_connection_id_deduplication_key UNIQUE (connection_id, deduplication_key), 
	CONSTRAINT fk_integration_events_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;
CREATE INDEX ix_integration_events_connection_id_received_at_int_id ON call_summary.integration_events (connection_id, received_at, int_id);

CREATE TABLE call_summary.meeting_participants (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	external_participant_id TEXT NOT NULL, 
	display_name TEXT NOT NULL, 
	role TEXT, 
	source_session_id BIGINT NOT NULL, 
	identity_id BIGINT, 
	CONSTRAINT pk_meeting_participants PRIMARY KEY (int_id), 
	CONSTRAINT uq_meeting_participants_id UNIQUE (id), 
	CONSTRAINT uq_meeting_participants_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_meeting_participants_source_session_id FOREIGN KEY(workspace_id, source_session_id) REFERENCES call_summary.source_sessions (workspace_id, int_id), 
	CONSTRAINT fk_meeting_participants_identity_id FOREIGN KEY(workspace_id, identity_id) REFERENCES call_summary.person_identities (workspace_id, int_id), 
	CONSTRAINT uq_source_session_id_external_participant_id UNIQUE (source_session_id, external_participant_id), 
	CONSTRAINT fk_meeting_participants_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;

CREATE TABLE call_summary.meeting_speakers (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	display_label TEXT NOT NULL, 
	identification_status TEXT DEFAULT 'unknown' NOT NULL, 
	identification_method TEXT DEFAULT 'unknown' NOT NULL, 
	meeting_id BIGINT NOT NULL, 
	person_id BIGINT, 
	participant_id BIGINT, 
	CONSTRAINT pk_meeting_speakers PRIMARY KEY (int_id), 
	CONSTRAINT ck_meeting_speakers_identification_status CHECK (identification_status IN ('unknown', 'proposed', 'confirmed', 'rejected')), 
	CONSTRAINT ck_meeting_speakers_identification_method CHECK (identification_method IN ('unknown', 'manual', 'provider', 'voice')), 
	CONSTRAINT uq_meeting_speakers_id UNIQUE (id), 
	CONSTRAINT uq_meeting_speakers_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_meeting_speakers_meeting_id FOREIGN KEY(workspace_id, meeting_id) REFERENCES call_summary.meetings (workspace_id, int_id), 
	CONSTRAINT fk_meeting_speakers_person_id FOREIGN KEY(workspace_id, person_id) REFERENCES call_summary.people (workspace_id, int_id), 
	CONSTRAINT fk_meeting_speakers_participant_id FOREIGN KEY(workspace_id, participant_id) REFERENCES call_summary.meeting_participants (workspace_id, int_id), 
	CONSTRAINT fk_meeting_speakers_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;

CREATE TABLE call_summary.participant_sessions (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	external_join_id TEXT NOT NULL, 
	joined_at TIMESTAMP WITH TIME ZONE, 
	left_at TIMESTAMP WITH TIME ZONE, 
	participant_id BIGINT NOT NULL, 
	CONSTRAINT pk_participant_sessions PRIMARY KEY (int_id), 
	CONSTRAINT ck_participant_sessions_interval CHECK (left_at IS NULL OR joined_at IS NULL OR left_at >= joined_at), 
	CONSTRAINT uq_participant_sessions_id UNIQUE (id), 
	CONSTRAINT uq_participant_sessions_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_participant_sessions_participant_id FOREIGN KEY(workspace_id, participant_id) REFERENCES call_summary.meeting_participants (workspace_id, int_id), 
	CONSTRAINT uq_participant_id_external_join_id UNIQUE (participant_id, external_join_id), 
	CONSTRAINT fk_participant_sessions_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;

CREATE TABLE call_summary.audio_streams (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	external_stream_key TEXT NOT NULL, 
	kind TEXT NOT NULL, 
	timeline_offset_ms BIGINT DEFAULT 0 NOT NULL, 
	status TEXT DEFAULT 'active' NOT NULL, 
	expected_chunk_count BIGINT, 
	is_primary BOOLEAN DEFAULT true NOT NULL, 
	metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
	source_session_id BIGINT NOT NULL, 
	participant_session_id BIGINT, 
	CONSTRAINT pk_audio_streams PRIMARY KEY (int_id), 
	CONSTRAINT ck_audio_streams_kind CHECK (kind IN ('mixed', 'per_person')), 
	CONSTRAINT ck_audio_streams_status CHECK (status IN ('active', 'ended', 'failed')), 
	CONSTRAINT ck_audio_streams_bounds CHECK (timeline_offset_ms >= 0 AND (expected_chunk_count IS NULL OR expected_chunk_count >= 0)), 
	CONSTRAINT uq_audio_streams_id UNIQUE (id), 
	CONSTRAINT uq_audio_streams_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_audio_streams_source_session_id FOREIGN KEY(workspace_id, source_session_id) REFERENCES call_summary.source_sessions (workspace_id, int_id), 
	CONSTRAINT fk_audio_streams_participant_session_id FOREIGN KEY(workspace_id, participant_session_id) REFERENCES call_summary.participant_sessions (workspace_id, int_id), 
	CONSTRAINT uq_source_session_id_external_stream_key UNIQUE (source_session_id, external_stream_key), 
	CONSTRAINT fk_audio_streams_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;

CREATE TABLE call_summary.audio_chunks (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	sequence_no BIGINT NOT NULL, 
	offset_ms BIGINT NOT NULL, 
	duration_ms BIGINT NOT NULL, 
	captured_at TIMESTAMP WITH TIME ZONE, 
	received_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	storage_key TEXT NOT NULL, 
	sha256 TEXT NOT NULL, 
	mime_type TEXT NOT NULL, 
	result_text TEXT DEFAULT '' NOT NULL, 
	transcription_status TEXT DEFAULT 'pending' NOT NULL, 
	analysis_status TEXT DEFAULT 'pending' NOT NULL, 
	processing_version BIGINT DEFAULT 1 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	meeting_id BIGINT NOT NULL, 
	stream_id BIGINT NOT NULL, 
	CONSTRAINT pk_audio_chunks PRIMARY KEY (int_id), 
	CONSTRAINT ck_audio_chunks_transcription_status CHECK (transcription_status IN ('pending', 'processing', 'succeeded', 'failed')), 
	CONSTRAINT ck_audio_chunks_analysis_status CHECK (analysis_status IN ('pending', 'processing', 'succeeded', 'failed', 'skipped')), 
	CONSTRAINT ck_audio_chunks_bounds CHECK (sequence_no >= 0 AND offset_ms >= 0 AND duration_ms >= 0 AND processing_version > 0), 
	CONSTRAINT ck_audio_chunks_sha256 CHECK (sha256 ~ '^[0-9a-f]{64}$'), 
	CONSTRAINT ck_audio_chunks_storage_key CHECK (storage_key ~ '^[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}\.[a-z0-9]+$'), 
	CONSTRAINT uq_audio_chunks_id UNIQUE (id), 
	CONSTRAINT uq_audio_chunks_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_audio_chunks_meeting_id FOREIGN KEY(workspace_id, meeting_id) REFERENCES call_summary.meetings (workspace_id, int_id), 
	CONSTRAINT fk_audio_chunks_stream_id FOREIGN KEY(workspace_id, stream_id) REFERENCES call_summary.audio_streams (workspace_id, int_id), 
	CONSTRAINT uq_stream_id_sequence_no UNIQUE (stream_id, sequence_no), 
	CONSTRAINT fk_audio_chunks_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;

CREATE TABLE call_summary.chunk_speakers (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	local_label TEXT NOT NULL, 
	chunk_id BIGINT NOT NULL, 
	meeting_speaker_id BIGINT, 
	CONSTRAINT pk_chunk_speakers PRIMARY KEY (int_id), 
	CONSTRAINT uq_chunk_speakers_id UNIQUE (id), 
	CONSTRAINT uq_chunk_speakers_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_chunk_speakers_chunk_id FOREIGN KEY(workspace_id, chunk_id) REFERENCES call_summary.audio_chunks (workspace_id, int_id), 
	CONSTRAINT fk_chunk_speakers_meeting_speaker_id FOREIGN KEY(workspace_id, meeting_speaker_id) REFERENCES call_summary.meeting_speakers (workspace_id, int_id), 
	CONSTRAINT uq_chunk_id_local_label UNIQUE (chunk_id, local_label), 
	CONSTRAINT fk_chunk_speakers_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;

CREATE TABLE call_summary.processing_jobs (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	kind TEXT NOT NULL, 
	status TEXT DEFAULT 'pending' NOT NULL, 
	attempts BIGINT DEFAULT 0 NOT NULL, 
	available_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	lease_until TIMESTAMP WITH TIME ZONE, 
	lease_token UUID, 
	last_error TEXT, 
	deduplication_key TEXT NOT NULL, 
	subscription_id BIGINT, 
	integration_event_id BIGINT, 
	chunk_id BIGINT, 
	meeting_id BIGINT, 
	CONSTRAINT pk_processing_jobs PRIMARY KEY (int_id), 
	CONSTRAINT ck_processing_jobs_status CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')), 
	CONSTRAINT ck_processing_jobs_kind CHECK (kind IN ('ingestion', 'transcription', 'analysis', 'finalization', 'poll', 'renew_subscription')), 
	CONSTRAINT ck_processing_jobs_attempts CHECK (attempts >= 0), 
	CONSTRAINT ck_processing_jobs_lease CHECK ((status = 'running' AND lease_until IS NOT NULL AND lease_token IS NOT NULL) OR (status <> 'running' AND lease_until IS NULL AND lease_token IS NULL)), 
	CONSTRAINT ck_processing_jobs_kind_target CHECK ((kind = 'ingestion' AND integration_event_id IS NOT NULL AND chunk_id IS NULL AND subscription_id IS NULL)
      OR (kind IN ('transcription', 'analysis') AND chunk_id IS NOT NULL AND integration_event_id IS NULL AND subscription_id IS NULL)
      OR (kind = 'finalization' AND meeting_id IS NOT NULL AND chunk_id IS NULL AND integration_event_id IS NULL AND subscription_id IS NULL)
      OR (kind IN ('poll', 'renew_subscription') AND subscription_id IS NOT NULL AND chunk_id IS NULL AND integration_event_id IS NULL AND meeting_id IS NULL)), 
	CONSTRAINT uq_processing_jobs_id UNIQUE (id), 
	CONSTRAINT uq_processing_jobs_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_processing_jobs_subscription_id FOREIGN KEY(workspace_id, subscription_id) REFERENCES call_summary.integration_subscriptions (workspace_id, int_id), 
	CONSTRAINT fk_processing_jobs_integration_event_id FOREIGN KEY(workspace_id, integration_event_id) REFERENCES call_summary.integration_events (workspace_id, int_id), 
	CONSTRAINT fk_processing_jobs_chunk_id FOREIGN KEY(workspace_id, chunk_id) REFERENCES call_summary.audio_chunks (workspace_id, int_id), 
	CONSTRAINT fk_processing_jobs_meeting_id FOREIGN KEY(workspace_id, meeting_id) REFERENCES call_summary.meetings (workspace_id, int_id), 
	CONSTRAINT uq_workspace_id_deduplication_key UNIQUE (workspace_id, deduplication_key), 
	CONSTRAINT fk_processing_jobs_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;
CREATE INDEX ix_processing_jobs_status_available_at ON call_summary.processing_jobs (status, available_at);

CREATE TABLE call_summary.utterances (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	ordinal BIGINT NOT NULL, 
	start_ms BIGINT NOT NULL, 
	end_ms BIGINT NOT NULL, 
	text TEXT NOT NULL, 
	meeting_id BIGINT NOT NULL, 
	chunk_id BIGINT NOT NULL, 
	chunk_speaker_id BIGINT, 
	CONSTRAINT pk_utterances PRIMARY KEY (int_id), 
	CONSTRAINT ck_utterances_bounds CHECK (ordinal >= 0 AND start_ms >= 0 AND end_ms >= start_ms), 
	CONSTRAINT uq_utterances_id UNIQUE (id), 
	CONSTRAINT uq_utterances_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_utterances_meeting_id FOREIGN KEY(workspace_id, meeting_id) REFERENCES call_summary.meetings (workspace_id, int_id), 
	CONSTRAINT fk_utterances_chunk_id FOREIGN KEY(workspace_id, chunk_id) REFERENCES call_summary.audio_chunks (workspace_id, int_id), 
	CONSTRAINT fk_utterances_chunk_speaker_id FOREIGN KEY(workspace_id, chunk_speaker_id) REFERENCES call_summary.chunk_speakers (workspace_id, int_id), 
	CONSTRAINT uq_chunk_id_ordinal UNIQUE (chunk_id, ordinal), 
	CONSTRAINT fk_utterances_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;
CREATE INDEX ix_utterances_workspace_id_meeting_id_start_ms_int_id ON call_summary.utterances (workspace_id, meeting_id, start_ms, int_id);

CREATE TABLE call_summary.action_item_events (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	event_type TEXT NOT NULL, 
	previous_values JSONB DEFAULT '{}'::jsonb NOT NULL, 
	new_values JSONB DEFAULT '{}'::jsonb NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	action_item_id BIGINT NOT NULL, 
	source_utterance_id BIGINT, 
	CONSTRAINT pk_action_item_events PRIMARY KEY (int_id), 
	CONSTRAINT uq_action_item_events_id UNIQUE (id), 
	CONSTRAINT uq_action_item_events_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_action_item_events_action_item_id FOREIGN KEY(workspace_id, action_item_id) REFERENCES call_summary.action_items (workspace_id, int_id), 
	CONSTRAINT fk_action_item_events_source_utterance_id FOREIGN KEY(workspace_id, source_utterance_id) REFERENCES call_summary.utterances (workspace_id, int_id), 
	CONSTRAINT fk_action_item_events_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;

CREATE TABLE call_summary.action_item_sources (
	int_id BIGINT GENERATED ALWAYS AS IDENTITY, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id BIGINT NOT NULL, 
	action_item_id BIGINT NOT NULL, 
	utterance_id BIGINT NOT NULL, 
	CONSTRAINT pk_action_item_sources PRIMARY KEY (int_id), 
	CONSTRAINT uq_action_item_sources_id UNIQUE (id), 
	CONSTRAINT uq_action_item_sources_workspace_id UNIQUE (workspace_id, int_id), 
	CONSTRAINT fk_action_item_sources_action_item_id FOREIGN KEY(workspace_id, action_item_id) REFERENCES call_summary.action_items (workspace_id, int_id), 
	CONSTRAINT fk_action_item_sources_utterance_id FOREIGN KEY(workspace_id, utterance_id) REFERENCES call_summary.utterances (workspace_id, int_id), 
	CONSTRAINT uq_action_item_id_utterance_id UNIQUE (action_item_id, utterance_id), 
	CONSTRAINT fk_action_item_sources_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES call_summary.workspaces (int_id)
)

;
