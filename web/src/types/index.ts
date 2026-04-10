// ============================================================
// Domain Types - BTC/ETH Quant Trading Assistant
// ============================================================

// -- Strategy Types --

export interface Strategy {
  id: string;
  name: string;
  description: string;
  type: StrategyType;
  parameters: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type StrategyType = 'trend_following' | 'mean_reversion' | 'breakout' | 'custom';

export interface StrategyCreateRequest {
  name: string;
  description: string;
  type: StrategyType;
  parameters: Record<string, unknown>;
}

// -- Evolution Types --

export interface EvolutionTask {
  id: string;
  name: string;
  status: EvolutionStatus;
  strategy_id: string;
  symbol: string;
  interval: string;
  start_date: string;
  end_date: string;
  current_generation: number;
  max_generations: number;
  best_fitness: number;
  created_at: string;
  updated_at: string;
}

export type EvolutionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'paused';

// -- Data Management Types --

export interface Dataset {
  id: string;
  symbol: string;
  interval: string;
  start_time: string;
  end_time: string;
  row_count: number;
  file_size: number;
  file_size_display: string;
  format: string;
  created_at: string;
  updated_at: string;
}

export interface DatasetPreview {
  columns: string[];
  rows: Record<string, string | number>[];
  total_rows: number;
}

export interface CsvDetectResult {
  symbol: string;
  interval: string;
  format: string;
  timestamp_precision: string;
  columns: string[];
  preview_rows: Record<string, string | number>[];
}

export type ImportStrategy = 'merge' | 'replace' | 'new';

export interface ImportRequest {
  file: File;
  strategy: ImportStrategy;
  target_dataset_id?: string;
}

export interface ImportResponse {
  dataset_id: string;
  rows_imported: number;
  message: string;
}

// -- Common Types --

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiError {
  detail: string;
  code?: string;
}
