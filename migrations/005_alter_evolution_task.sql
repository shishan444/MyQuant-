-- Migration 005: Add extended columns to evolution_task
-- These ALTER TABLE statements use IF NOT EXISTS equivalent via try/catch in Python.

-- champion_strategy_id: links to the winning strategy
ALTER TABLE evolution_task ADD COLUMN champion_strategy_id TEXT;

-- population_size: number of individuals per generation
-- (applied in Python with default check)

-- max_generations: cap on evolution iterations
-- (applied in Python with default check)

-- elite_ratio: fraction of top performers kept
-- (applied in Python with default check)

-- n_workers: parallel worker count
-- (applied in Python with default check)

-- current_generation: tracks progress
-- (applied in Python with default check)
