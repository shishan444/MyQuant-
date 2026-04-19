export interface SignalGene {
  indicator: string;
  params: Record<string, unknown>;
  role: "entry_trigger" | "entry_guard" | "exit_trigger" | "exit_guard" | "add_trigger" | "add_guard" | "reduce_trigger" | "reduce_guard";
  field?: string;
  condition: {
    type: "lt" | "gt" | "le" | "ge" | "cross_above" | "cross_below" | "price_above" | "price_below";
    value?: number;
    ref_indicator?: string;
    ref_field?: string;
  };
}

export interface LogicGenes {
  entry_logic: "AND" | "OR";
  exit_logic: "AND" | "OR";
  add_logic?: "AND" | "OR";
  reduce_logic?: "AND" | "OR";
}

export interface ExecutionGenes {
  timeframe: string;
  symbol: string;
}

export interface RiskGenes {
  stop_loss: number;
  take_profit: number | null;
  position_size: number;
  leverage: number;
  direction: "long" | "short" | "mixed";
}

export interface TimeframeLayerModel {
  timeframe: string;
  signal_genes: SignalGene[];
  logic_genes: LogicGenes;
}

export interface DNA {
  signal_genes: SignalGene[];
  logic_genes: LogicGenes;
  execution_genes: ExecutionGenes;
  risk_genes: RiskGenes;
  strategy_id?: string;
  generation: number;
  parent_ids: string[];
  mutation_ops: string[];
  layers?: TimeframeLayerModel[] | null;
  cross_layer_logic?: "AND" | "OR";
}

export interface Strategy {
  strategy_id: string;
  name?: string;
  dna?: DNA;
  symbol: string;
  timeframe: string;
  source: string;
  source_task_id?: string;
  best_score?: number;
  generation: number;
  parent_ids?: string;
  tags?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface BacktestResult {
  result_id: string;
  strategy_id: string;
  symbol: string;
  timeframe: string;
  data_start?: string;
  data_end?: string;
  init_cash: number;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  total_score: number;
  template_name: string;
  dimension_scores?: Record<string, number>;
  equity_curve?: Array<{ timestamp: string; value: number }>;
  signals?: TradeSignal[];
  total_funding_cost: number;
  liquidated: boolean;
}

export interface TradeSignal {
  type: "buy" | "sell";
  timestamp: string;
  price: number;
  confidence?: number;
  reason: string;
}

export type EvolutionTaskStatus = "pending" | "running" | "paused" | "stopped" | "completed";

export interface EvolutionTask {
  task_id: string;
  status: EvolutionTaskStatus;
  target_score: number;
  score_template: string;
  symbol: string;
  timeframe: string;
  initial_dna?: DNA;
  champion_dna?: DNA;
  population_size: number;
  max_generations: number;
  current_generation: number;
  created_at: string;
  updated_at: string;
  stop_reason?: string;
  best_score?: number;
  indicator_pool?: string[];
  timeframe_pool?: string[];
  mode?: "auto" | "seed";
  leverage: number;
  direction: "long" | "short" | "mixed";
  data_start?: string;
  data_end?: string;
  data_time_start?: string;
  data_time_end?: string;
  data_row_count?: number;
  champion_metrics?: {
    annual_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    win_rate: number;
    calmar_ratio: number;
    total_trades: number;
  };
  champion_dimension_scores?: Record<string, number>;
  walk_forward_enabled?: boolean;
  continuous?: boolean;
  population_count?: number;
}

export interface EvolutionHistoryRecord {
  generation: number;
  best_score: number;
  avg_score: number;
  top3_summary?: string;
  created_at: string;
}

export interface Dataset {
  dataset_id: string;
  symbol: string;
  interval: string;
  row_count: number;
  time_start?: string;
  time_end?: string;
  quality_status: "complete" | "warning" | "error" | "unknown";
  gap_count: number;
  created_at: string;
  updated_at: string;
}

export interface OhlcvData {
  data: Array<{
    timestamp: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page?: number;
  page_size?: number;
}

export interface StrategyListResponse {
  strategies: Strategy[];
  total: number;
}

export interface EvolutionTaskListResponse {
  items: EvolutionTask[];
  total: number;
}

export interface DatasetListResponse {
  datasets: Dataset[];
  total: number;
}

export interface EvolutionHistoryResponse {
  records: EvolutionHistoryRecord[];
  total: number;
}

export interface GenerationUpdate {
  type: "generation_complete" | "evolution_complete" | "population_started";
  task_id: string;
  generation: number;
  best_score: number;
  avg_score: number;
  target_score: number;
  max_generations: number;
  champion_dna?: DNA;
  population_diversity?: number;
  last_mutations?: string[];
  population_count?: number;
  best_score_ever?: number;
  total_generations_so_far?: number;
}

export interface MutationRecord {
  generation: number;
  operation: string;
  details: string;
}

export interface EvolvedStrategy {
  strategy_id: string;
  dna: DNA;
  source: "champion" | "snapshot";
  generation?: number;
  score: number;
}

// ---------------------------------------------------------------------------
// Validation types (Strategy Lab v2.3)
// ---------------------------------------------------------------------------

export interface ConditionInput {
  subject: string;
  action: string;
  target: string;
  window?: number;
  logic: "AND" | "OR";
  timeframe?: string;
}

export interface ValidateRequest {
  pair: string;
  timeframe: string;
  base_timeframe?: string;
  start: string;
  end: string;
  when: ConditionInput[];
  then: ConditionInput[];
  indicator_params?: Record<string, unknown>;
}

export interface ChartIndicatorConfig {
  ema_periods: number[];
  ema_colors: string[];
  boll: { enabled: boolean; period: number; std: number; color: string };
  rsi: { enabled: boolean; period: number; overbought: number; oversold: number };
  vol: { enabled: boolean; position: "overlay" | "separate" };
}

export interface TriggerRecord {
  id: number;
  time: string;
  trigger_price: number;
  change_pct: number;
  matched: boolean;
  indicator_values: Record<string, number>;
}

export interface DistributionBucket {
  range: [number, number];
  match_count: number;
  mismatch_count: number;
  total_count: number;
}

export interface ValidateResponse {
  match_rate: number;
  total_count: number;
  match_count: number;
  mismatch_count: number;
  triggers: TriggerRecord[];
  distribution: DistributionBucket[];
  percentiles: Record<string, number>;
  concentration: Record<string, number[]>;
  signal_frequency: Record<string, number>;
  extremes: Array<{ change_pct: number; time: string; is_match: boolean }>;
  warnings: string[];
}

// ---------------------------------------------------------------------------
// Available data sources
// ---------------------------------------------------------------------------

export interface AvailableSource {
  symbol: string;
  timeframe: string;
  time_start?: string;
  time_end?: string;
}

export interface AvailableSourcesResponse {
  sources: AvailableSource[];
}

// ---------------------------------------------------------------------------
// Chart indicators (computed by backend)
// ---------------------------------------------------------------------------

export interface ChartIndicatorsResponse {
  ema: Record<string, Array<{ time: string; value: number }>>;
  boll: {
    upper: Array<{ time: string; value: number }>;
    middle: Array<{ time: string; value: number }>;
    lower: Array<{ time: string; value: number }>;
  } | null;
  rsi: Array<{ time: string; value: number }> | null;
  macd: {
    macd: Array<{ time: string; value: number }>;
    signal: Array<{ time: string; value: number }>;
    histogram: Array<{ time: string; value: number }>;
  } | null;
  kdj: {
    k: Array<{ time: string; value: number }>;
    d: Array<{ time: string; value: number }>;
    j: Array<{ time: string; value: number }>;
  } | null;
}
