-- Add archive support for chats (run once on existing Postgres DBs).
-- New installs get this column from SQLAlchemy create_all when the model includes it.

ALTER TABLE chats
  ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NULL;

CREATE INDEX IF NOT EXISTS ix_chats_archived_at ON chats (archived_at);
