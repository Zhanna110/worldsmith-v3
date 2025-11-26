-- Enable the pgvector extension to work with embedding vectors
create extension if not exists vector;

-- Create a table to store your documents
create table documents (
  id uuid primary key default gen_random_uuid(),
  content text,
  embedding vector(768), -- 768 is the dimension for Gemini text-embedding-004
  metadata jsonb
);

-- Create a function to search for documents
create or replace function match_documents (
  query_embedding vector(768),
  match_threshold float,
  match_count int,
  filter jsonb DEFAULT '{}'
) returns table (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
) language plpgsql stable as $$
begin
  return query
  select
    documents.id,
    documents.content,
    documents.metadata,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where 1 - (documents.embedding <=> query_embedding) > match_threshold
  and documents.metadata @> filter
  order by documents.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- Create an HNSW index for faster queries
create index on documents using hnsw (embedding vector_cosine_ops);
