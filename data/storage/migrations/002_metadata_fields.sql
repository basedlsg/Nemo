-- Add Chinese government document metadata fields for improved retrieval
-- Implements deterministic constraints before ranking

-- Add text content fields
ALTER TABLE citations ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE citations ADD COLUMN IF NOT EXISTS headings TEXT;
ALTER TABLE citations ADD COLUMN IF NOT EXISTS body TEXT;

-- Add Chinese government document metadata
ALTER TABLE citations ADD COLUMN IF NOT EXISTS agency TEXT;           -- 发布机关
ALTER TABLE citations ADD COLUMN IF NOT EXISTS wenhao TEXT;           -- 文号
ALTER TABLE citations ADD COLUMN IF NOT EXISTS publish_date DATE;     -- 发布日期
ALTER TABLE citations ADD COLUMN IF NOT EXISTS effective_date DATE;   -- 实施日期
ALTER TABLE citations ADD COLUMN IF NOT EXISTS status TEXT DEFAULT '现行有效'; -- 状态 (现行有效/失效/废止)

-- Add normalized fields for filtering
ALTER TABLE citations ADD COLUMN IF NOT EXISTS province_normalized TEXT;
ALTER TABLE citations ADD COLUMN IF NOT EXISTS doc_class_normalized TEXT;

-- Enable trigram extension for fuzzy text matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create indexes for metadata-based filtering and search
CREATE INDEX IF NOT EXISTS cit_title_trgm ON citations USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS cit_headings_trgm ON citations USING gin (headings gin_trgm_ops);
CREATE INDEX IF NOT EXISTS cit_wenhao_idx ON citations (wenhao);
CREATE INDEX IF NOT EXISTS cit_meta_filter_idx ON citations (province_normalized, doc_class_normalized, status);
CREATE INDEX IF NOT EXISTS cit_publish_date_idx ON citations (publish_date DESC);
CREATE INDEX IF NOT EXISTS cit_effective_date_idx ON citations (effective_date DESC);
CREATE INDEX IF NOT EXISTS cit_status_idx ON citations (status);

-- Add comments for documentation
COMMENT ON COLUMN citations.title IS 'Document title for keyword search and display';
COMMENT ON COLUMN citations.headings IS 'Document headings/sections for keyword search';
COMMENT ON COLUMN citations.body IS 'Full document text content';
COMMENT ON COLUMN citations.agency IS '发布机关 - Government agency that published the document';
COMMENT ON COLUMN citations.wenhao IS '文号 - Official document number (e.g., 粤能规〔2023〕12号)';
COMMENT ON COLUMN citations.publish_date IS '发布日期 - Date document was published';
COMMENT ON COLUMN citations.effective_date IS '实施日期 - Date document becomes effective';
COMMENT ON COLUMN citations.status IS '状态 - Document status (现行有效/失效/废止/部分失效)';
COMMENT ON COLUMN citations.province_normalized IS 'Normalized province name for filtering';
COMMENT ON COLUMN citations.doc_class_normalized IS 'Normalized document class for filtering';
