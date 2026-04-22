-- Migration 007: Add gene_signature column for dedup and indexes
ALTER TABLE strategy ADD COLUMN gene_signature TEXT;

-- Index for dedup lookups
CREATE INDEX IF NOT EXISTS idx_strategy_gene_signature ON strategy(gene_signature);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_strategy_source ON strategy(source);
CREATE INDEX IF NOT EXISTS idx_strategy_best_score ON strategy(best_score DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_source_task_id ON strategy(source_task_id);
