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

// -- Evolution Detail Types --

export interface GenerationHistoryPoint {
  generation: number;
  best_score: number;
  avg_score: number;
  worst_score: number;
  diversity: number;
}

export interface MutationLogEntry {
  generation: number;
  timestamp: string;
  operation: string;
  description: string;
  score_delta: number;
}

export interface BestStrategy {
  generation: number;
  total_score: number;
  dimension_scores: DimensionScores;
  signal_genes: SignalGene[];
  risk_genes: RiskGenes;
}

export interface PopulationState {
  diversity: number;
  score_distribution: number[];
  elite_count: number;
  total_count: number;
}

export interface EvolutionTaskDetail extends EvolutionTask {
  best_strategy: BestStrategy | null;
  population: PopulationState | null;
  mutation_logs: MutationLogEntry[];
  target_score: number;
}

export interface WsEvolutionMessage {
  type: 'generation_complete' | 'task_completed' | 'task_failed';
  generation: number;
  best_score: number;
  avg_score: number;
  mutation_log: MutationLogEntry | null;
}

// -- Strategy Library Types --

export type StrategySource = 'manual' | 'evolution' | 'import';

export interface StrategyListItem {
  id: string;
  short_id: string;
  name: string;
  description: string;
  type: StrategyType;
  source: StrategySource;
  symbol: SymbolType;
  timeframe: TimeframeType;
  total_score: number;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  total_trades: number;
  win_rate: number;
  dimension_scores: DimensionScores;
  signal_genes: SignalGene[];
  risk_genes: RiskGenes;
  created_at: string;
  updated_at: string;
}

export type StrategySortField = 'total_score' | 'total_return' | 'sharpe_ratio' | 'max_drawdown' | 'total_trades' | 'created_at';
export type SortOrder = 'asc' | 'desc';

export interface StrategyListParams {
  symbol?: SymbolType;
  timeframe?: TimeframeType;
  source?: StrategySource;
  sort_by?: StrategySortField;
  sort_order?: SortOrder;
  search?: string;
  page?: number;
  page_size?: number;
}

export interface CompareResult {
  strategies: StrategyListItem[];
  equity_curves: { strategy_id: string; curve: EquityPoint[] }[];
}

// -- Config Types --

export interface EvolutionConfig {
  population_size: number;
  max_generations: number;
  parallel_count: number;
  target_score: number;
  mutation_rate_early: number;
  mutation_rate_mid: number;
  mutation_rate_late: number;
  stagnation_threshold: number;
  stagnation_generations: number;
  degradation_generations: number;
}

export interface AppConfig {
  evolution: EvolutionConfig;
  claude_api_key: string;
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
