-- GAEA Database Setup for AlloyDB
-- Run this after AlloyDB cluster is created

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create database if it doesn't exist
CREATE DATABASE gaea_db;

-- Connect to gaea_db
\c gaea_db;

-- Enable extensions in the new database
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create citations table with vector support
CREATE TABLE IF NOT EXISTS citations (
    citation_id VARCHAR(255) PRIMARY KEY,
    province VARCHAR(50) NOT NULL,
    doc_class VARCHAR(50) NOT NULL,
    asset VARCHAR(50),
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    effective_date DATE NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536), -- OpenAI/Google embedding dimension
    superseded_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes for performance
    CONSTRAINT fk_superseded_by FOREIGN KEY (superseded_by) REFERENCES citations(citation_id)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_citations_province_doc_class ON citations(province, doc_class);
CREATE INDEX IF NOT EXISTS idx_citations_asset ON citations(asset);
CREATE INDEX IF NOT EXISTS idx_citations_effective_date ON citations(effective_date);
CREATE INDEX IF NOT EXISTS idx_citations_superseded ON citations(superseded_by);

-- Vector similarity index (HNSW for fast approximate search)
CREATE INDEX IF NOT EXISTS idx_citations_embedding ON citations 
USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);

-- Create sources table for registry management
CREATE TABLE IF NOT EXISTS sources (
    domain VARCHAR(255) PRIMARY KEY,
    province VARCHAR(50) NOT NULL,
    label TEXT NOT NULL,
    doc_classes TEXT[] NOT NULL,
    cadence VARCHAR(100),
    robots_policy VARCHAR(20) DEFAULT 'respect',
    owner VARCHAR(50) DEFAULT 'CC',
    active BOOLEAN DEFAULT true,
    last_crawled TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for sources
CREATE INDEX IF NOT EXISTS idx_sources_province ON sources(province);
CREATE INDEX IF NOT EXISTS idx_sources_active ON sources(active);

-- Create snapshots table for document tracking
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    content_type VARCHAR(100),
    file_size BIGINT,
    storage_path TEXT NOT NULL,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'pending',
    
    -- Unique constraint to prevent duplicate snapshots
    UNIQUE(url, checksum)
);

-- Create indexes for snapshots
CREATE INDEX IF NOT EXISTS idx_snapshots_domain ON snapshots(domain);
CREATE INDEX IF NOT EXISTS idx_snapshots_status ON snapshots(status);
CREATE INDEX IF NOT EXISTS idx_snapshots_discovered ON snapshots(discovered_at);

-- Create query_logs table for analytics
CREATE TABLE IF NOT EXISTS query_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trace_id VARCHAR(100) NOT NULL,
    province VARCHAR(50),
    doc_class VARCHAR(50),
    asset VARCHAR(50),
    question TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'zh',
    response_status VARCHAR(20) NOT NULL,
    refusal_reason VARCHAR(50),
    citations_count INTEGER DEFAULT 0,
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for query logs
CREATE INDEX IF NOT EXISTS idx_query_logs_trace_id ON query_logs(trace_id);
CREATE INDEX IF NOT EXISTS idx_query_logs_created_at ON query_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_query_logs_status ON query_logs(response_status);

-- Insert initial registry data (placeholder - will be replaced)
INSERT INTO sources (domain, province, label, doc_classes) VALUES
('gzpec.cn', 'guangdong', '广东电力交易中心', ARRAY['market_rules', 'dispatch_ops']),
('sdpxc.cn', 'shandong', '山东电力交易中心', ARRAY['market_rules', 'grid_connection']),
('impex.org.cn', 'inner_mongolia', '内蒙古电力交易中心', ARRAY['market_rules'])
ON CONFLICT (domain) DO NOTHING;

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for automatic timestamp updates
CREATE TRIGGER update_citations_updated_at BEFORE UPDATE ON citations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sources_updated_at BEFORE UPDATE ON sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust as needed for your service account)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO gaea_services;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO gaea_services;