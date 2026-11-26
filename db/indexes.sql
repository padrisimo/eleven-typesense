-- Phase 3: Secondary indexes for PostgreSQL performance
-- Applied after benchmarking in Phase 3 to measure before/after

-- Composite index for category + created_at ordering (common query pattern)
CREATE INDEX IF NOT EXISTS idx_sounds_category_created_at
    ON sounds (category, created_at DESC)
    WHERE is_active;

-- GIN index for tags array containment queries (tags @> ARRAY[...])
CREATE INDEX IF NOT EXISTS idx_sounds_tags_gin
    ON sounds USING GIN (tags)
    WHERE is_active;

-- B-tree index for source (library/ai) filter
CREATE INDEX IF NOT EXISTS idx_sounds_source
    ON sounds (source)
    WHERE is_active;

-- B-tree index for format filter
CREATE INDEX IF NOT EXISTS idx_sounds_format
    ON sounds (format)
    WHERE is_active;

-- Trigram index for ILIKE on title (supports non-left-anchored patterns)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_sounds_title_trgm
    ON sounds USING GIN (title gin_trgm_ops)
    WHERE is_active;

-- Index for generation_jobs lookups by prompt_hash (idempotency)
CREATE INDEX IF NOT EXISTS idx_generation_jobs_prompt_hash
    ON generation_jobs (prompt_hash);

-- Index for generation_jobs daily limit counting
CREATE INDEX IF NOT EXISTS idx_generation_jobs_created_at
    ON generation_jobs (created_at DESC);
