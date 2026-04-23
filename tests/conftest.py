"""Shared test fixtures for MyQuant test suite."""

import numpy as np
import pandas as pd
import pytest

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
from core.backtest.engine import BacktestEngine


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """500-bar synthetic BTC 4h OHLCV data."""
    np.random.seed(42)
    n = 500
    dates = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    base_price = 40000.0
    returns = np.random.randn(n) * 0.01 + 0.0001
    close = base_price * np.cumprod(1 + returns)

    high = close * (1 + np.abs(np.random.randn(n)) * 0.005)
    low = close * (1 - np.abs(np.random.randn(n)) * 0.005)
    opn = close * (1 + np.random.randn(n) * 0.002)
    volume = np.random.randint(100, 10000, size=n).astype(float)

    df = pd.DataFrame(
        {"open": opn, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )
    df.index.name = "timestamp"
    return df


@pytest.fixture
def valid_dna() -> StrategyDNA:
    """Basic RSI strategy DNA for testing."""
    gene_entry = SignalGene(
        indicator="RSI",
        params={"period": 14},
        role=SignalRole.ENTRY_TRIGGER,
        field_name="RSI_14",
        condition={
            "type": "lt",
            "target_indicator": "RSI",
            "target_params": {"period": 14},
            "value": 30,
        },
    )
    gene_exit = SignalGene(
        indicator="RSI",
        params={"period": 14},
        role=SignalRole.EXIT_TRIGGER,
        field_name="RSI_14",
        condition={
            "type": "gt",
            "target_indicator": "RSI",
            "target_params": {"period": 14},
            "value": 70,
        },
    )
    return StrategyDNA(
        signal_genes=[gene_entry, gene_exit],
        logic_genes=LogicGenes(entry_logic="AND", exit_logic="AND"),
        execution=ExecutionGenes(timeframe="4h", symbol="BTCUSDT"),
        risk=RiskGenes(
            stop_loss=0.05,
            take_profit=0.10,
            position_size=0.5,
            leverage=1,
            direction="long",
        ),
    )


@pytest.fixture
def sample_engine() -> BacktestEngine:
    """BacktestEngine with 100k init cash."""
    return BacktestEngine(init_cash=100000)
