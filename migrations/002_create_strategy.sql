-- Migration 002: Create strategy table
CREATE TABLE IF NOT EXISTS strategy (
    strategy_id     TEXT PRIMARY KEY,
    name            TEXT,
    dna_json        TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'manual',
    source_task_id  TEXT,
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    best_score      REAL,
    generation      INTEGER DEFAULT 0,
    parent_ids      TEXT,
    tags            TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
