"""Pydantic V2 request/response models for the API layer."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Enums ──


class ImportFormat(str, Enum):
    BINANCE_OFFICIAL = "binance_official"
    GENERIC_OHLCV = "generic_ohlcv"


class TimestampPrecision(str, Enum):
    MILLISECOND = "ms"
    MICROSECOND = "us"


class ImportMode(str, Enum):
    MERGE = "merge"
    REPLACE = "replace"
    NEW = "new"


class ConditionType(str, Enum):
    LT = "lt"
    GT = "gt"
    LE = "le"
    GE = "ge"
    CROSS_ABOVE = "cross_above"
    CROSS_BELOW = "cross_below"
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"


class SignalRole(str, Enum):
    ENTRY_TRIGGER = "entry_trigger"
    ENTRY_GUARD = "entry_guard"
    EXIT_TRIGGER = "exit_trigger"
    EXIT_GUARD = "exit_guard"
    ADD_TRIGGER = "add_trigger"
    ADD_GUARD = "add_guard"
    REDUCE_TRIGGER = "reduce_trigger"
    REDUCE_GUARD = "reduce_guard"


class ScoreTemplate(str, Enum):
    PROFIT_FIRST = "profit_first"
    STEADY = "steady"
    RISK_FIRST = "risk_first"
    CUSTOM = "custom"


# ── DNA Component Models ──


class SignalGeneModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicator: str
    params: Dict[str, Any]
    role: SignalRole
    field: Optional[str] = None
    condition: Dict[str, Any] = Field(default_factory=dict)


class LogicGenesModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_logic: str = "AND"
    exit_logic: str = "AND"
    add_logic: str = "AND"
    reduce_logic: str = "AND"


class ExecutionGenesModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeframe: str = "4h"
    symbol: str = "BTCUSDT"


class RiskGenesModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stop_loss: float = 0.05
    take_profit: Optional[float] = None
    position_size: float = 0.3
    leverage: int = Field(default=1, ge=1, le=10)
    direction: str = Field(default="long", pattern="^(long|short|mixed)$")


class DNAModel(BaseModel):
    """Full StrategyDNA as a Pydantic model for API serialization."""

    model_config = ConfigDict(extra="forbid")

    signal_genes: List[SignalGeneModel] = Field(default_factory=list)
    logic_genes: LogicGenesModel = Field(default_factory=LogicGenesModel)
    execution_genes: ExecutionGenesModel = Field(default_factory=ExecutionGenesModel)
    risk_genes: RiskGenesModel = Field(default_factory=RiskGenesModel)
    strategy_id: Optional[str] = None
    generation: int = 0
    parent_ids: List[str] = Field(default_factory=list)
    mutation_ops: List[str] = Field(default_factory=list)
    layers: Optional[List[dict]] = None
    cross_layer_logic: str = "AND"


class TimeframeLayerModel(BaseModel):
    """A single timeframe layer within an MTF strategy."""

    model_config = ConfigDict(extra="forbid")

    timeframe: str
    signal_genes: List[SignalGeneModel] = Field(default_factory=list)
    logic_genes: LogicGenesModel = Field(default_factory=LogicGenesModel)
    role: Optional[str] = None  # "trend" | "execution"


# ── Strategy Schemas ──


class StrategyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    dna: DNAModel
    symbol: str
    timeframe: str
    source: str = "manual"
    source_task_id: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None


class StrategyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    strategy_id: str
    name: Optional[str] = None
    dna: Optional[DNAModel] = None
    symbol: str
    timeframe: str
    source: str = "manual"
    source_task_id: Optional[str] = None
    best_score: Optional[float] = None
    generation: int = 0
    parent_ids: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str


class StrategyListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: List[StrategyResponse]
    total: int


class StrategyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    dna: Optional[DNAModel] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    best_score: Optional[float] = None


# ── Backtest Schemas ──


class BacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: Optional[str] = None
    dna: Optional[DNAModel] = None
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    dataset_id: str
    init_cash: float = 100000.0
    fee: float = 0.001
    slippage: float = 0.0005
    score_template: str = "profit_first"
    data_start: Optional[str] = None
    data_end: Optional[str] = None
    timeframe_pool: Optional[List[str]] = None


class BacktestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result_id: str
    strategy_id: str
    symbol: str
    timeframe: str
    data_start: Optional[str] = None
    data_end: Optional[str] = None
    init_cash: float = 100000.0
    fee: float = 0.001
    slippage: float = 0.0005
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    total_score: float = 0.0
    template_name: str = "profit_first"
    dimension_scores: Optional[Dict[str, Any]] = None
    run_source: str = "lab"
    equity_curve: Optional[List[Dict[str, Any]]] = None
    signals: Optional[List[Dict[str, Any]]] = None
    total_funding_cost: float = 0.0
    liquidated: bool = False


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_ids: List[str]
    dataset_id: str
    init_cash: float = 100000.0
    fee: float = 0.001
    slippage: float = 0.0005
    score_template: str = "profit_first"


class CompareResultItem(BaseModel):
    strategy_id: str
    result_id: Optional[str] = None
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    total_score: float = 0.0
    dimension_scores: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CompareResponse(BaseModel):
    results: List[CompareResultItem]


# ── Evolution Schemas ──


class EvolutionTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initial_dna: Optional[DNAModel] = None
    symbol: str
    timeframe: str
    target_score: float = 80.0
    score_template: str = "profit_first"
    population_size: int = 15
    max_generations: int = 200
    elite_ratio: float = 0.5
    n_workers: int = 6
    indicator_pool: Optional[List[str]] = None
    timeframe_pool: Optional[List[str]] = None
    mode: Optional[str] = None
    walk_forward_enabled: bool = False
    leverage: int = Field(default=1, ge=1, le=10)
    direction: str = Field(default="long", pattern="^(long|short|mixed)$")
    data_start: Optional[str] = None
    data_end: Optional[str] = None
    continuous: bool = True
    strategy_threshold: float = Field(default=80.0, description="Score threshold for auto-extracting strategies")


class EvolutionTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    status: str
    target_score: float
    score_template: str
    symbol: str
    timeframe: str
    initial_dna: Optional[DNAModel] = None
    champion_dna: Optional[DNAModel] = None
    population_size: int = 15
    max_generations: int = 200
    elite_ratio: float = 0.5
    n_workers: int = 6
    current_generation: int = 0
    created_at: str
    updated_at: str
    stop_reason: Optional[str] = None
    best_score: Optional[float] = None
    leverage: int = 1
    direction: str = "long"
    data_start: Optional[str] = None
    data_end: Optional[str] = None
    data_time_start: Optional[str] = None
    data_time_end: Optional[str] = None
    data_row_count: int = 0
    indicator_pool: Optional[List[str]] = None
    timeframe_pool: Optional[List[str]] = None
    mode: Optional[str] = None
    champion_metrics: Optional[Dict[str, Any]] = None
    champion_dimension_scores: Optional[Dict[str, Any]] = None
    walk_forward_enabled: bool = False
    continuous: bool = True
    strategy_threshold: float = 80.0
    strategy_count: int = 0
    exploration_efficiency: float = 0.0


class EvolutionTaskListResponse(BaseModel):
    items: List[EvolutionTaskResponse]
    total: int
    page: int = 1
    page_size: int = 20


class EvolutionHistoryRecord(BaseModel):
    generation: int
    best_score: float
    avg_score: float
    top3_summary: Optional[str] = None
    created_at: str


class EvolutionHistoryResponse(BaseModel):
    task_id: str
    generations: List[EvolutionHistoryRecord]


# ── Data Schemas ──


class DataImportResponse(BaseModel):
    dataset_id: str
    symbol: str
    interval: str
    rows_imported: int
    format_detected: str
    timestamp_precision: str
    files_processed: int = 1
    time_range: Optional[List[str]] = None


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dataset_id: str
    symbol: str
    interval: str
    parquet_path: str
    row_count: int = 0
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    file_size_bytes: int = 0
    source: str = "csv_import"
    format_detected: Optional[str] = None
    timestamp_precision: Optional[str] = None
    quality_status: str = "unknown"
    quality_notes: Optional[str] = None
    gap_count: int = 0
    created_at: str
    updated_at: str


class DatasetListResponse(BaseModel):
    items: List[DatasetResponse]
    total: int


class DatasetPreviewResponse(BaseModel):
    dataset_id: str
    total_rows: int
    rows: List[Dict[str, Any]]


class OhlcvResponse(BaseModel):
    dataset_id: str
    data: List[Dict[str, Any]]


# ── Config Schemas ──


class AvailableSource(BaseModel):
    symbol: str
    timeframe: str
    time_start: Optional[str] = None
    time_end: Optional[str] = None


class AvailableSourcesResponse(BaseModel):
    sources: List[AvailableSource]


class ConfigResponse(BaseModel):
    symbols: List[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    timeframes: List[str] = Field(default_factory=lambda: ["1h", "4h", "1d"])
    backtest: Dict[str, Any] = Field(default_factory=dict)
    evolution: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    version: str = "0.9.0"
    timestamp: str = ""
