"""Unified test data factory for MyQuant test suite.

Replaces duplicated fixture setup across 40+ test files with
a single source of truth for test data generation.

Usage:
    from tests.helpers.data_factory import make_ohlcv, make_dna, make_mtf_dna
"""

import numpy as np
import pandas as pd

from core.strategy.dna import (
    ConditionType,
    ExecutionGenes,
    LogicGenes,
    RiskGenes,
    SignalGene,
    SignalRole,
    StrategyDNA,
    TimeframeLayer,
)


# ---------------------------------------------------------------------------
# OHLCV data
# ---------------------------------------------------------------------------

def make_ohlcv(
    n: int = 500,
    freq: str = "4h",
    base_price: float = 40000.0,
    seed: int = 42,
    start: str = "2024-01-01",
) -> pd.DataFrame:
    """Generate synthetic OHLCV DataFrame.

    Args:
        n: Number of bars.
        freq: Pandas frequency string (e.g. "4h", "1h", "1d", "15m").
        base_price: Starting price.
        seed: Random seed for reproducibility.
        start: Start date string.

    Returns:
        DataFrame with columns: open, high, low, close, volume.
        Index: DatetimeIndex named "timestamp" with UTC timezone.
    """
    rng = np.random.default_rng(seed)
    returns = rng.standard_normal(n) * 0.01 + 0.0001
    close = base_price * np.cumprod(1 + returns)

    high = close * (1 + np.abs(rng.standard_normal(n)) * 0.005)
    low = close * (1 - np.abs(rng.standard_normal(n)) * 0.005)
    opn = close * (1 + rng.standard_normal(n) * 0.002)
    volume = rng.integers(100, 10000, size=n).astype(float)

    dates = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    df = pd.DataFrame(
        {"open": opn, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )
    df.index.name = "timestamp"
    return df


# ---------------------------------------------------------------------------
# Signal Gene helpers
# ---------------------------------------------------------------------------

def make_signal_gene(
    indicator: str = "RSI",
    params: dict | None = None,
    role: SignalRole = SignalRole.ENTRY_TRIGGER,
    condition_type: str = "lt",
    condition_value: float = 30,
    field_name: str | None = None,
) -> SignalGene:
    """Create a SignalGene with sensible defaults.

    Args:
        indicator: Indicator name (e.g. "RSI", "EMA", "MACD").
        params: Indicator parameters dict.
        role: SignalRole enum value.
        condition_type: Condition type string (e.g. "lt", "gt", "price_above").
        condition_value: Threshold value for comparison conditions.
        field_name: Optional field name for multi-output indicators.

    Returns:
        SignalGene instance.
    """
    if params is None:
        params = {"period": 14} if indicator in ("RSI", "EMA") else {}

    condition = {"type": condition_type, "threshold": condition_value}
    if condition_type in ("price_above", "price_below"):
        condition = {"type": condition_type}

    return SignalGene(
        indicator=indicator,
        params=params,
        role=role,
        field_name=field_name,
        condition=condition,
    )


# ---------------------------------------------------------------------------
# Strategy DNA
# ---------------------------------------------------------------------------

def make_dna(
    indicator: str = "RSI",
    timeframe: str = "4h",
    symbol: str = "BTCUSDT",
    direction: str = "long",
    stop_loss: float = 0.05,
    take_profit: float = 0.10,
    position_size: float = 0.5,
    leverage: int = 1,
    entry_condition: str = "lt",
    entry_value: float = 30,
    exit_condition: str = "gt",
    exit_value: float = 70,
) -> StrategyDNA:
    """Create a simple single-timeframe StrategyDNA for testing.

    Args:
        indicator: Indicator name for both entry and exit.
        timeframe: Execution timeframe.
        symbol: Trading pair.
        direction: "long" or "short".
        stop_loss: Stop loss fraction.
        take_profit: Take profit fraction.
        position_size: Position size fraction.
        leverage: Leverage multiplier.
        entry_condition: Entry condition type.
        entry_value: Entry threshold.
        exit_condition: Exit condition type.
        exit_value: Exit threshold.

    Returns:
        StrategyDNA with entry + exit signal genes.
    """
    gene_entry = make_signal_gene(
        indicator=indicator,
        role=SignalRole.ENTRY_TRIGGER,
        condition_type=entry_condition,
        condition_value=entry_value,
    )
    gene_exit = make_signal_gene(
        indicator=indicator,
        role=SignalRole.EXIT_TRIGGER,
        condition_type=exit_condition,
        condition_value=exit_value,
    )
    return StrategyDNA(
        signal_genes=[gene_entry, gene_exit],
        logic_genes=LogicGenes(entry_logic="AND", exit_logic="AND"),
        execution_genes=ExecutionGenes(timeframe=timeframe, symbol=symbol),
        risk_genes=RiskGenes(
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
            leverage=leverage,
            direction=direction,
        ),
    )


def make_ema_dna(
    timeframe: str = "4h",
    direction: str = "long",
) -> StrategyDNA:
    """Create an EMA crossover strategy DNA."""
    gene_entry = make_signal_gene(
        indicator="EMA",
        params={"period": 20},
        role=SignalRole.ENTRY_TRIGGER,
        condition_type="price_above",
    )
    gene_exit = make_signal_gene(
        indicator="EMA",
        params={"period": 20},
        role=SignalRole.EXIT_TRIGGER,
        condition_type="price_below",
    )
    return StrategyDNA(
        signal_genes=[gene_entry, gene_exit],
        logic_genes=LogicGenes(entry_logic="AND", exit_logic="AND"),
        execution_genes=ExecutionGenes(timeframe=timeframe),
        risk_genes=RiskGenes(direction=direction),
    )


def make_mtf_dna(
    timeframes: tuple[str, ...] = ("1d", "4h", "15m"),
    cross_layer_logic: str = "AND",
    mtf_mode: str | None = None,
    confluence_threshold: float = 0.3,
    proximity_mult: float = 1.5,
) -> StrategyDNA:
    """Create a multi-timeframe StrategyDNA with RSI on each layer.

    Args:
        timeframes: Tuple of timeframe strings. First is the execution layer.
        cross_layer_logic: "AND" or "OR".
        mtf_mode: MTF engine mode (None for legacy AND/OR).
        confluence_threshold: Confluence score threshold.
        proximity_mult: Proximity multiplier.

    Returns:
        StrategyDNA with MTF layers. Execution timeframe is timeframes[-1].
    """
    layers = []
    for tf in timeframes:
        entry = make_signal_gene(
            indicator="RSI",
            params={"period": 14},
            role=SignalRole.ENTRY_TRIGGER,
            condition_type="lt",
            condition_value=30,
        )
        exit_gene = make_signal_gene(
            indicator="RSI",
            params={"period": 14},
            role=SignalRole.EXIT_TRIGGER,
            condition_type="gt",
            condition_value=70,
        )
        layers.append(TimeframeLayer(
            timeframe=tf,
            signal_genes=[entry, exit_gene],
            logic_genes=LogicGenes(entry_logic="AND", exit_logic="AND"),
        ))

    return StrategyDNA(
        signal_genes=[],
        logic_genes=LogicGenes(entry_logic="AND", exit_logic="AND"),
        execution_genes=ExecutionGenes(timeframe=timeframes[-1]),
        risk_genes=RiskGenes(direction="long"),
        layers=layers,
        cross_layer_logic=cross_layer_logic,
        mtf_mode=mtf_mode,
        confluence_threshold=confluence_threshold,
        proximity_mult=proximity_mult,
    )


# ---------------------------------------------------------------------------
# SignalSet helpers
# ---------------------------------------------------------------------------

def make_signal_set(
    n: int = 100,
    entries: int = 5,
    exits: int = 5,
    adds: int = 0,
    reduces: int = 0,
    freq: str = "4h",
    seed: int = 42,
) -> dict:
    """Create a signal set dict suitable for backtest engine input.

    Args:
        n: Number of bars.
        entries: Number of True entry signals.
        exits: Number of True exit signals.
        adds: Number of True add signals.
        reduces: Number of True reduce signals.
        freq: Bar frequency.
        seed: Random seed.

    Returns:
        Dict with keys: entries, exits, adds, reduces (all pd.Series of bool).
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC")

    def _sparse_bool(count: int) -> pd.Series:
        arr = np.zeros(n, dtype=bool)
        if count > 0 and count < n:
            indices = rng.choice(n, size=count, replace=False)
            arr[indices] = True
        return pd.Series(arr, index=dates)

    return {
        "entries": _sparse_bool(entries),
        "exits": _sparse_bool(exits),
        "adds": _sparse_bool(adds),
        "reduces": _sparse_bool(reduces),
    }
