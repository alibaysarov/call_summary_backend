#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=app_password="$DB_APP_PASSWORD" --set=migration_password="$DB_MIGRATION_PASSWORD" <<'SQL'
CREATE ROLE call_summary_app LOGIN PASSWORD :'app_password';
CREATE ROLE call_summary_migrator LOGIN PASSWORD :'migration_password';
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA call_summary AUTHORIZATION call_summary_migrator;
SQL
