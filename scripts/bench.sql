-- Phase 3: EXPLAIN (ANALYZE, BUFFERS) benchmarks.
-- Run from the same client against the same 200,000-row dataset before and after db/indexes.sql.

\echo === Q1: category + ORDER BY created_at LIMIT 20 ===
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title, created_at
FROM sounds
WHERE is_active AND category = 'Explosions'
ORDER BY created_at DESC
LIMIT 20;

\echo === Q2: tags array containment ===
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title, tags
FROM sounds
WHERE is_active AND tags @> ARRAY['ui', 'notification', 'feedback']::text[]
LIMIT 20;

\echo === Q3: ILIKE on title ===
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title
FROM sounds
WHERE is_active AND title ILIKE '%rusty hatch%'
LIMIT 20;

\echo === Q4: count per category ===
EXPLAIN (ANALYZE, BUFFERS)
SELECT category, count(*) AS total
FROM sounds
WHERE is_active
GROUP BY category
ORDER BY total DESC;

\echo === Q5: Postgres substring text search (comparison with Typesense) ===
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title
FROM sounds
WHERE is_active AND title ILIKE '%explosion%'
LIMIT 20;
