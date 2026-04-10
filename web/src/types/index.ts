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

// -- Backtest Types --

export type SignalRole = 'entry_trigger' | 'entry_guard' | 'exit_trigger' | 'exit_guard';
export type ConditionType = 'gt' | 'lt' | 'ge' | 'le' | 'cross_above' | 'cross_below' | 'price_above' | 'price_below';
export type TemplateType = 'profit_first' | 'steady' | 'risk_first';
export type SymbolType = 'BTCUSDT' | 'ETHUSDT';
export type TimeframeType = '1h' | '4h' | '1d';

export interface SignalGene {
  id: string;
  indicator: string;
  params: Record<string, number>;
  role: SignalRole;
  condition: ConditionType;
  threshold: number;
}

export interface LogicGenes {
  entry_logic: 'AND';
  exit_logic: 'OR';
}

export interface ExecutionGenes {
  timeframe: TimeframeType;
  symbol: SymbolType;
}

export interface RiskGenes {
  stop_loss: number;
  take_profit: number;
  position_size: number;
}

export interface BacktestRequest {
  signal_genes: Omit<SignalGene, 'id'>[];
  logic_genes: LogicGenes;
  execution_genes: ExecutionGenes;
  risk_genes: RiskGenes;
  template: TemplateType;
}

export interface EquityPoint {
  time: string;
  equity: number;
  benchmark: number;
}

export interface BacktestTrade {
  trade_id: number;
  entry_time: string;
  exit_time: string;
  direction: 'long' | 'short';
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  pnl_pct: number;
  fee: number;
}

export interface DimensionScores {
  profitability: number;
  stability: number;
  risk_control: number;
  efficiency: number;
}

export interface BacktestResponse {
  result_id: string;
  strategy_id: string;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  total_score: number;
  dimension_scores: DimensionScores;
  equity_curve: EquityPoint[];
  trades_json: BacktestTrade[];
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
