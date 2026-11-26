-- Phase 1: Schema without secondary indexes (only PK and prompt_hash unique)
-- Indexes will be added in Phase 3 via indexes.sql

CREATE TABLE IF NOT EXISTS sounds (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    tags TEXT[] NOT NULL DEFAULT '{}',
    duration_ms INT NOT NULL,
    bpm INT,
    format TEXT NOT NULL CHECK (format IN ('wav', 'mp3', 'flac')),
    sample_rate INT NOT NULL,
    file_key TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('library', 'ai')),
    prompt_hash TEXT UNIQUE,
    license TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    indexed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS generation_jobs (
    id BIGSERIAL PRIMARY KEY,
    prompt TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'done', 'failed')) DEFAULT 'pending',
    sound_id BIGINT REFERENCES sounds(id),
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
