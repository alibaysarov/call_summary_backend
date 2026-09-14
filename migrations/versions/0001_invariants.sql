-- Frozen migration: ownership anchors are immutable, attribution remains editable.
CREATE FUNCTION call_summary.guard_ownership() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE key text;
BEGIN
  FOREACH key IN ARRAY TG_ARGV LOOP
    IF to_jsonb(NEW)->key IS DISTINCT FROM to_jsonb(OLD)->key THEN
      RAISE EXCEPTION 'Immutable ownership key: %.%', TG_TABLE_NAME, key USING ERRCODE='23514';
    END IF;
  END LOOP;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.workspaces FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.integration_connections FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.integration_subscriptions FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id','connection_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.integration_events FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id','connection_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.meetings FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.source_sessions FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id','meeting_id','connection_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.people FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.person_identities FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.meeting_participants FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id','source_session_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.participant_sessions FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id','participant_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.meeting_speakers FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id','meeting_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.audio_streams FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id','source_session_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.audio_chunks FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id','meeting_id','stream_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.chunk_speakers FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id','chunk_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.utterances FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id','meeting_id','chunk_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.action_items FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id','meeting_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.action_item_sources FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id','action_item_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.action_item_events FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id','action_item_id');
CREATE TRIGGER guard_ownership BEFORE UPDATE ON call_summary.processing_jobs FOR EACH ROW EXECUTE FUNCTION call_summary.guard_ownership('int_id','id','workspace_id');
CREATE FUNCTION call_summary.check_integration_events() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM call_summary.integration_subscriptions p WHERE p.workspace_id=NEW.workspace_id AND p.int_id=NEW.subscription_id AND p.connection_id<>NEW.connection_id) THEN RAISE EXCEPTION 'Inconsistent relationship in integration_events' USING ERRCODE='23514'; END IF;
  IF EXISTS (SELECT 1 FROM call_summary.source_sessions p WHERE p.workspace_id=NEW.workspace_id AND p.int_id=NEW.source_session_id AND p.connection_id<>NEW.connection_id) THEN RAISE EXCEPTION 'Inconsistent relationship in integration_events' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER check_relationships BEFORE INSERT OR UPDATE ON call_summary.integration_events FOR EACH ROW EXECUTE FUNCTION call_summary.check_integration_events();
CREATE FUNCTION call_summary.check_meeting_speakers() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM call_summary.meeting_participants p JOIN call_summary.source_sessions s ON (s.workspace_id,s.int_id)=(p.workspace_id,p.source_session_id) WHERE p.workspace_id=NEW.workspace_id AND p.int_id=NEW.participant_id AND s.meeting_id<>NEW.meeting_id) THEN RAISE EXCEPTION 'Inconsistent relationship in meeting_speakers' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER check_relationships BEFORE INSERT OR UPDATE ON call_summary.meeting_speakers FOR EACH ROW EXECUTE FUNCTION call_summary.check_meeting_speakers();
CREATE FUNCTION call_summary.check_audio_streams() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM call_summary.participant_sessions p JOIN call_summary.meeting_participants m ON (m.workspace_id,m.int_id)=(p.workspace_id,p.participant_id) WHERE p.workspace_id=NEW.workspace_id AND p.int_id=NEW.participant_session_id AND m.source_session_id<>NEW.source_session_id) THEN RAISE EXCEPTION 'Inconsistent relationship in audio_streams' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER check_relationships BEFORE INSERT OR UPDATE ON call_summary.audio_streams FOR EACH ROW EXECUTE FUNCTION call_summary.check_audio_streams();
CREATE FUNCTION call_summary.check_audio_chunks() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM call_summary.audio_streams p JOIN call_summary.source_sessions s ON (s.workspace_id,s.int_id)=(p.workspace_id,p.source_session_id) WHERE p.workspace_id=NEW.workspace_id AND p.int_id=NEW.stream_id AND s.meeting_id<>NEW.meeting_id) THEN RAISE EXCEPTION 'Inconsistent relationship in audio_chunks' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER check_relationships BEFORE INSERT OR UPDATE ON call_summary.audio_chunks FOR EACH ROW EXECUTE FUNCTION call_summary.check_audio_chunks();
CREATE FUNCTION call_summary.check_chunk_speakers() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM call_summary.audio_chunks c JOIN call_summary.meeting_speakers s ON s.workspace_id=c.workspace_id WHERE c.workspace_id=NEW.workspace_id AND c.int_id=NEW.chunk_id AND s.int_id=NEW.meeting_speaker_id AND c.meeting_id<>s.meeting_id) THEN RAISE EXCEPTION 'Inconsistent relationship in chunk_speakers' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER check_relationships BEFORE INSERT OR UPDATE ON call_summary.chunk_speakers FOR EACH ROW EXECUTE FUNCTION call_summary.check_chunk_speakers();
CREATE FUNCTION call_summary.check_utterances() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM call_summary.audio_chunks p WHERE p.workspace_id=NEW.workspace_id AND p.int_id=NEW.chunk_id AND p.meeting_id<>NEW.meeting_id) THEN RAISE EXCEPTION 'Inconsistent relationship in utterances' USING ERRCODE='23514'; END IF;
  IF EXISTS (SELECT 1 FROM call_summary.chunk_speakers p WHERE p.workspace_id=NEW.workspace_id AND p.int_id=NEW.chunk_speaker_id AND p.chunk_id<>NEW.chunk_id) THEN RAISE EXCEPTION 'Inconsistent relationship in utterances' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER check_relationships BEFORE INSERT OR UPDATE ON call_summary.utterances FOR EACH ROW EXECUTE FUNCTION call_summary.check_utterances();
CREATE FUNCTION call_summary.check_action_item_sources() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM call_summary.action_items a JOIN call_summary.utterances u ON a.workspace_id=u.workspace_id WHERE a.workspace_id=NEW.workspace_id AND a.int_id=NEW.action_item_id AND u.int_id=NEW.utterance_id AND a.meeting_id<>u.meeting_id) THEN RAISE EXCEPTION 'Inconsistent relationship in action_item_sources' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER check_relationships BEFORE INSERT OR UPDATE ON call_summary.action_item_sources FOR EACH ROW EXECUTE FUNCTION call_summary.check_action_item_sources();
CREATE FUNCTION call_summary.check_action_item_events() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM call_summary.action_items a JOIN call_summary.utterances u ON a.workspace_id=u.workspace_id WHERE a.workspace_id=NEW.workspace_id AND a.int_id=NEW.action_item_id AND u.int_id=NEW.source_utterance_id AND a.meeting_id<>u.meeting_id) THEN RAISE EXCEPTION 'Inconsistent relationship in action_item_events' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER check_relationships BEFORE INSERT OR UPDATE ON call_summary.action_item_events FOR EACH ROW EXECUTE FUNCTION call_summary.check_action_item_events();
CREATE FUNCTION call_summary.check_processing_jobs() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM 1 FROM call_summary.integration_events WHERE workspace_id=NEW.workspace_id AND int_id=NEW.integration_event_id FOR UPDATE;
  IF EXISTS (SELECT 1 FROM call_summary.audio_chunks c WHERE c.workspace_id=NEW.workspace_id AND c.int_id=NEW.chunk_id AND c.meeting_id<>NEW.meeting_id) THEN RAISE EXCEPTION 'Inconsistent relationship in processing_jobs' USING ERRCODE='23514'; END IF;
  IF EXISTS (SELECT 1 FROM call_summary.integration_events e JOIN call_summary.source_sessions s ON (s.workspace_id,s.int_id)=(e.workspace_id,e.source_session_id) WHERE e.workspace_id=NEW.workspace_id AND e.int_id=NEW.integration_event_id AND s.meeting_id<>NEW.meeting_id) THEN RAISE EXCEPTION 'Inconsistent relationship in processing_jobs' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER check_relationships BEFORE INSERT OR UPDATE ON call_summary.processing_jobs FOR EACH ROW EXECUTE FUNCTION call_summary.check_processing_jobs();

CREATE FUNCTION call_summary.guard_event_resolution() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.source_session_id IS NOT NULL AND NEW.source_session_id IS DISTINCT FROM OLD.source_session_id THEN
    RAISE EXCEPTION 'Resolved event cannot be reparented' USING ERRCODE='23514';
  END IF;
  IF EXISTS (SELECT 1 FROM call_summary.processing_jobs j
    JOIN call_summary.source_sessions s ON s.workspace_id=j.workspace_id
    WHERE j.workspace_id=NEW.workspace_id AND j.integration_event_id=NEW.int_id
      AND s.int_id=NEW.source_session_id AND j.meeting_id<>s.meeting_id) THEN
    RAISE EXCEPTION 'Event resolution disagrees with job meeting' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_event_resolution BEFORE UPDATE ON call_summary.integration_events
FOR EACH ROW EXECUTE FUNCTION call_summary.guard_event_resolution();
