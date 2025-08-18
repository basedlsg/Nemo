-- Initial schema for geo-adaptive energy assistant
-- Creates citations, packs, and sources tables with pgvector support

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Citations table (AlloyDB + pgvector)
CREATE TABLE citations (
    citation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    province TEXT NOT NULL,
    doc_class TEXT NOT NULL CHECK (doc_class IN ('market_rules', 'grid_connection', 'dispatch_ops')),
    asset TEXT CHECK (asset IN ('wind', 'solar', 'bess', 'coal_flex')),
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    effective_date DATE NOT NULL,
    checksum TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536),
    superseded_by UUID REFERENCES citations(citation_id),
    chunk_id TEXT,
    parent_citation_id UUID REFERENCES citations(citation_id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for citations table
CREATE INDEX cit_idx ON citations (province, doc_class, asset);
CREATE INDEX cit_effective_idx ON citations (province, doc_class, effective_date DESC);
CREATE INDEX cit_embedding_idx ON citations USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX cit_checksum_idx ON citations (checksum);
CREATE INDEX cit_chunk_idx ON citations (chunk_id) WHERE chunk_id IS NOT NULL;

-- Packs table (compiled outputs)
CREATE TABLE packs (
    pack_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP DEFAULT NOW(),
    province TEXT,
    asset TEXT,
    doc_class TEXT,
    query_fingerprint TEXT NOT NULL,
    citation_ids UUID[] NOT NULL,
    answer_zh TEXT,
    pack_status TEXT DEFAULT 'generated' CHECK (pack_status IN ('generated', 'delivered', 'expired'))
);

-- Index for packs table
CREATE INDEX pack_qf_idx ON packs (query_fingerprint);
CREATE INDEX pack_created_idx ON packs (created_at DESC);
CREATE INDEX pack_province_idx ON packs (province, doc_class, asset);

-- Sources registry table
CREATE TABLE sources (
    domain TEXT PRIMARY KEY,
    province TEXT,
    label TEXT,
    cadence TEXT,
    robots TEXT DEFAULT 'allow' CHECK (robots IN ('allow', 'disallow')),
    last_crawled_at TIMESTAMP,
    owner TEXT,
    doc_classes TEXT[] DEFAULT '{}',
    fetch_method TEXT DEFAULT 'html' CHECK (fetch_method IN ('html', 'pdf', 'both')),
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for sources table
CREATE INDEX sources_province_idx ON sources (province);
CREATE INDEX sources_enabled_idx ON sources (enabled) WHERE enabled = true;
CREATE INDEX sources_crawl_idx ON sources (last_crawled_at DESC);

-- Evaluation metrics table for tracking quality gates
CREATE TABLE evaluation_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    province TEXT NOT NULL,
    doc_class TEXT NOT NULL,
    evaluation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    groundedness_score DECIMAL(3,2) CHECK (groundedness_score >= 0 AND groundedness_score <= 1),
    citation_precision DECIMAL(3,2) CHECK (citation_precision >= 0 AND citation_precision <= 1),
    refusal_accuracy DECIMAL(3,2) CHECK (refusal_accuracy >= 0 AND refusal_accuracy <= 1),
    avg_latency_ms INTEGER,
    p95_latency_ms INTEGER,
    total_queries INTEGER DEFAULT 0,
    passed_queries INTEGER DEFAULT 0,
    refused_queries INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for evaluation metrics
CREATE INDEX eval_metrics_province_idx ON evaluation_metrics (province, doc_class, evaluation_date DESC);
CREATE INDEX eval_metrics_date_idx ON evaluation_metrics (evaluation_date DESC);

-- Query logs table for observability
CREATE TABLE query_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trace_id TEXT NOT NULL,
    user_id TEXT,
    province TEXT,
    doc_class TEXT,
    asset TEXT,
    question_hash TEXT,
    verdict TEXT CHECK (verdict IN ('ok', 'refused', 'error')),
    refusal_reason TEXT,
    citation_ids UUID[],
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for query logs
CREATE INDEX query_logs_trace_idx ON query_logs (trace_id);
CREATE INDEX query_logs_created_idx ON query_logs (created_at DESC);
CREATE INDEX query_logs_verdict_idx ON query_logs (verdict);
CREATE INDEX query_logs_province_idx ON query_logs (province, doc_class);

-- Ingestion jobs table for pipeline tracking
CREATE TABLE ingestion_jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_domain TEXT NOT NULL REFERENCES sources(domain),
    url TEXT NOT NULL,
    job_status TEXT DEFAULT 'pending' CHECK (job_status IN ('pending', 'processing', 'completed', 'failed', 'retrying')),
    job_type TEXT DEFAULT 'discovery' CHECK (job_type IN ('discovery', 'verification', 'ingestion', 'ocr', 'normalization')),
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    scheduled_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for ingestion jobs
CREATE INDEX ingestion_jobs_status_idx ON ingestion_jobs (job_status);
CREATE INDEX ingestion_jobs_domain_idx ON ingestion_jobs (source_domain);
CREATE INDEX ingestion_jobs_scheduled_idx ON ingestion_jobs (scheduled_at);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_citations_updated_at BEFORE UPDATE ON citations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sources_updated_at BEFORE UPDATE ON sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE citations IS 'Stores normalized energy regulation citations with embeddings';
COMMENT ON TABLE packs IS 'Stores generated compliance packs with citation references';
COMMENT ON TABLE sources IS 'Registry of official energy regulation sources';
COMMENT ON TABLE evaluation_metrics IS 'Quality metrics for province/doc_class combinations';
COMMENT ON TABLE query_logs IS 'Structured logs for all query requests and responses';
COMMENT ON TABLE ingestion_jobs IS 'Pipeline job tracking for document ingestion';

COMMENT ON COLUMN citations.embedding IS 'Vector embedding for semantic search (1536 dimensions)';
COMMENT ON COLUMN citations.superseded_by IS 'Reference to newer citation that supersedes this one';
COMMENT ON COLUMN citations.chunk_id IS 'Identifier for text chunk within parent document';
COMMENT ON COLUMN packs.query_fingerprint IS 'Hash of normalized query for caching and analytics';
COMMENT ON COLUMN sources.cadence IS 'Crawling frequency in ISO8601 interval format';
COMMENT ON COLUMN query_logs.verdict IS 'Final outcome: ok (answered), refused (no citation), error (system failure)';