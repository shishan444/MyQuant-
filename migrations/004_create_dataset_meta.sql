-- Migration 004: Create dataset_meta table
CREATE TABLE IF NOT EXISTS dataset_meta (
    dataset_id      TEXT PRIMARY KEY,
    symbol          TEXT NOT NULL,
    interval        TEXT NOT NULL,
    parquet_path    TEXT NOT NULL,
    row_count       INTEGER NOT NULL DEFAULT 0,
    time_start      TEXT,
    time_end        TEXT,
    file_size_bytes INTEGER DEFAULT 0,
    source          TEXT NOT NULL DEFAULT 'csv_import',
    format_detected TEXT,
    timestamp_precision TEXT,
    ohlcv_stats     TEXT,
    gap_count       INTEGER DEFAULT 0,
    quality_status  TEXT DEFAULT 'unknown',
    quality_notes   TEXT,
    import_batch_id TEXT,
    last_import_at  TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
