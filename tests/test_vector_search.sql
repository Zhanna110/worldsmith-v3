-- Test Script for Vector Search

-- 1. Insert a dummy 'Lore Entry'
-- We generate a fake vector of 1536 dimensions filled with 0.1
WITH vector_gen AS (
  SELECT array_agg(0.1)::vector(1536) as vec
  FROM generate_series(1, 1536)
)
INSERT INTO documents (content, embedding, metadata)
SELECT 
  'Lore Entry: The ancient artifact was found in the ruins.',
  vec,
  '{"type": "lore", "chapter": 1}'::jsonb
FROM vector_gen;

-- 2. Try to retrieve it using match_documents
-- We use the same vector to ensure a perfect match (similarity should be 1.0)
WITH vector_gen AS (
  SELECT array_agg(0.1)::vector(1536) as vec
  FROM generate_series(1, 1536)
)
SELECT * FROM match_documents(
  (SELECT vec FROM vector_gen),
  0.8, -- Threshold
  1,   -- Count
  '{"type": "lore"}'::jsonb -- Filter
);
