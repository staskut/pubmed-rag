-- Knowledge base schema for the Anesthesiology PubMed Q&A project.
-- Applied automatically on first container start (docker-entrypoint-initdb.d).

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Corpus: one row per article (the "dataset")
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS articles (
    pmid          TEXT PRIMARY KEY,
    pmcid         TEXT,
    doi           TEXT,
    title         TEXT NOT NULL,
    abstract      TEXT,
    full_text     TEXT,
    has_full_text BOOLEAN NOT NULL DEFAULT FALSE,
    authors       JSONB,
    journal       TEXT,
    pub_year      INT,
    mesh_terms    JSONB,
    source_url    TEXT,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS articles_year_idx ON articles (pub_year);
CREATE INDEX IF NOT EXISTS articles_fulltext_idx ON articles (has_full_text);

-- ---------------------------------------------------------------------------
-- Retrieval units: chunks with embeddings (populated in the embedding stage)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chunks (
    id           BIGSERIAL PRIMARY KEY,
    pmid         TEXT NOT NULL REFERENCES articles(pmid) ON DELETE CASCADE,
    chunk_index  INT  NOT NULL,
    section      TEXT,                         -- title | abstract | body
    content      TEXT NOT NULL,
    token_count  INT,
    embedding    vector(1536),                 -- OpenAI text-embedding-3-small
    tsv          tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    UNIQUE (pmid, chunk_index)
);
-- Keyword (full-text) index for the hybrid search's lexical arm
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING GIN (tsv);
-- Vector index for the semantic arm (cosine distance)
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- Monitoring: every query, and the feedback on it
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS query_logs (
    id                 BIGSERIAL PRIMARY KEY,
    ts                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    question           TEXT NOT NULL,
    rewritten_question TEXT,
    strategy           TEXT,                   -- keyword | vector | hybrid | hybrid_rerank
    top_k              INT,
    retrieved_pmids    JSONB,
    answer             TEXT,
    latency_ms         INT,
    prompt_tokens      INT,
    completion_tokens  INT,
    cost_usd           NUMERIC(10, 6)
);

CREATE TABLE IF NOT EXISTS feedback (
    id           BIGSERIAL PRIMARY KEY,
    query_log_id BIGINT REFERENCES query_logs(id) ON DELETE CASCADE,
    rating       SMALLINT NOT NULL,            -- +1 / -1
    comment      TEXT,
    ts           TIMESTAMPTZ NOT NULL DEFAULT now()
);
