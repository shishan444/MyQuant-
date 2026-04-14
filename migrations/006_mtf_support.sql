-- Migration 006: MTF support and validation engine
-- Adds columns for multi-timeframe evolution tasks and validation tables

-- Add MTF-related columns to evolution_task
ALTER TABLE evolution_task ADD COLUMN indicator_pool TEXT;
ALTER TABLE evolution_task ADD COLUMN timeframe_pool TEXT;
ALTER TABLE evolution_task ADD COLUMN mode TEXT;
ALTER TABLE evolution_task ADD COLUMN population_size INTEGER DEFAULT 15;
ALTER TABLE evolution_task ADD COLUMN max_generations INTEGER DEFAULT 200;
ALTER TABLE evolution_task ADD COLUMN target_score REAL DEFAULT 80;
ALTER TABLE evolution_task ADD COLUMN elite_ratio REAL DEFAULT 0.5;
ALTER TABLE evolution_task ADD COLUMN n_workers INTEGER DEFAULT 6;
ALTER TABLE evolution_task ADD COLUMN current_generation INTEGER DEFAULT 0;
ALTER TABLE evolution_task ADD COLUMN champion_strategy_id TEXT;
