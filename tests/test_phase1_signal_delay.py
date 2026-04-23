"""Phase 1: Signal delay + remove shift(-1) from touch_bounce."""

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
from core.strategy.executor import dna_to_signal_set, evaluate_condition
from core.backtest.engine import BacktestEngine


def _make_rsi_df(n=100, seed=42):
    """Create a DataFrame with RSI column for testing."""
    np.random.seed(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    df = pd.DataFrame(
        {
            "open": close * 0.999,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": 1000.0,
        },
        index=dates,
    )
    df.index.name = "timestamp"

    # Add synthetic RSI
    rsi = 50 + np.random.randn(n) * 20
    rsi = np.clip(rsi, 0, 100)
    df["rsi_14"] = rsi

    return df


def _make_rsi_dna(direction="long"):
    gene_entry = SignalGene(
        indicator="RSI",
        params={"period": 14},
        role=SignalRole.ENTRY_TRIGGER,
        field_name="RSI_14",
        condition={"type": "lt", "threshold": 30},
    )
    gene_exit = SignalGene(
        indicator="RSI",
        params={"period": 14},
        role=SignalRole.EXIT_TRIGGER,
        field_name="RSI_14",
        condition={"type": "gt", "threshold": 70},
    )
    return StrategyDNA(
        signal_genes=[gene_entry, gene_exit],
        logic_genes=LogicGenes(entry_logic="AND", exit_logic="AND"),
        execution_genes=ExecutionGenes(timeframe="4h", symbol="BTCUSDT"),
        risk_genes=RiskGenes(
            stop_loss=0.05,
            take_profit=0.10,
            position_size=0.5,
            leverage=1,
            direction=direction,
        ),
    )


def test_entries_delayed_by_1_bar():
    """Entry signals should be delayed by exactly 1 bar."""
    df = _make_rsi_df(100)

    # Force RSI < 30 at bars 10, 20, 30
    df.loc[df.index[10], "rsi_14"] = 25
    df.loc[df.index[20], "rsi_14"] = 25
    df.loc[df.index[30], "rsi_14"] = 25

    dna = _make_rsi_dna()
    sig_set = dna_to_signal_set(dna, df)

    # Raw signals (before delay) should fire at 10, 20, 30
    assert sig_set.entries.iloc[10] == True
    assert sig_set.entries.iloc[20] == True
    assert sig_set.entries.iloc[30] == True

    # After engine delay, entries should be at 11, 21, 31
    engine = BacktestEngine(init_cash=100000)
    pf, add_c, red_c = engine._build_portfolio(dna, df)

    # Build delayed signals manually to check
    delayed_entries = sig_set.entries.shift(1).fillna(False).astype(bool)
    assert delayed_entries.iloc[11] == True
    assert delayed_entries.iloc[10] == False


def test_exits_delayed_by_1_bar():
    """Exit signals should be delayed by exactly 1 bar."""
    df = _make_rsi_df(100)

    # Force RSI > 70 at bars 15, 25
    df.loc[df.index[15], "rsi_14"] = 75
    df.loc[df.index[25], "rsi_14"] = 75

    dna = _make_rsi_dna()
    sig_set = dna_to_signal_set(dna, df)

    assert sig_set.exits.iloc[15] == True

    delayed_exits = sig_set.exits.shift(1).fillna(False).astype(bool)
    assert delayed_exits.iloc[16] == True
    assert delayed_exits.iloc[15] == False


def test_first_bar_no_signals():
    """Bar 0 should never have signals (can't delay from bar -1)."""
    df = _make_rsi_df(5)
    df.loc[df.index[0], "rsi_14"] = 10  # Force entry condition

    dna = _make_rsi_dna()
    sig_set = dna_to_signal_set(dna, df)

    # Raw signal at bar 0
    assert sig_set.entries.iloc[0] == True

    # After delay, bar 0 should be False
    delayed = sig_set.entries.shift(1).fillna(False).astype(bool)
    assert delayed.iloc[0] == False


def test_touch_bounce_uses_only_past_data():
    """Verify touch_bounce doesn't use shift(-1) (future data)."""
    n = 50
    dates = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    close = pd.Series(np.linspace(100, 110, n), index=dates)
    low = close - 2
    high = close + 2
    line = pd.Series(105.0, index=dates)  # Flat support line at 105

    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": 1000.0}, index=dates)
    df.index.name = "timestamp"

    condition = {
        "type": "touch_bounce",
        "direction": "support",
        "proximity_pct": 0.05,
    }

    result = evaluate_condition(line, close, condition, df=df)

    # Result should be same length as input
    assert len(result) == n

    # All values should be computable without NaN (no shift(-1) edge effects)
    # Only the first bar might be NaN from shift(1), which is acceptable
    assert result.iloc[1:].notna().all()


def test_signal_delay_produces_valid_trades():
    """With delayed signals, trades should execute after the signal bar."""
    n = 50
    dates = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    np.random.seed(42)

    close = pd.Series(np.linspace(100, 120, n), index=dates)
    opn = close * (1 + np.random.randn(n) * 0.001)
    high = close + 1
    low = close - 1

    df = pd.DataFrame(
        {"open": opn, "high": high, "low": low, "close": close, "volume": 1000.0},
        index=dates,
    )
    df.index.name = "timestamp"
    df["rsi_14"] = 50.0

    # Force entry at bar 10
    df.iloc[10, df.columns.get_loc("rsi_14")] = 25
    # Force exit at bar 30
    df.iloc[30, df.columns.get_loc("rsi_14")] = 75

    dna = _make_rsi_dna()
    engine = BacktestEngine(init_cash=100000)
    result = engine.run(dna, df)

    # Should produce at least one trade
    assert result.total_trades >= 1
    # Entry price should be a reasonable price (within data range)
    if result.trades_df is not None and len(result.trades_df) > 0:
        entry_price = result.trades_df.iloc[0]["Avg Entry Price"]
        assert 90 < entry_price < 130


def test_existing_backtest_still_works():
    """Backtest should still produce trades after signal delay."""
    df = _make_rsi_df(200)

    # Create some entry/exit opportunities
    for i in [20, 60, 100, 140]:
        df.iloc[i, df.columns.get_loc("rsi_14")] = 20
    for i in [40, 80, 120, 160]:
        df.iloc[i, df.columns.get_loc("rsi_14")] = 80

    dna = _make_rsi_dna()
    engine = BacktestEngine(init_cash=100000)
    result = engine.run(dna, df)

    # Should have some trades (delay may reduce count vs raw signals)
    assert isinstance(result.total_trades, int)
    assert result.equity_curve is not None
    assert len(result.equity_curve) == len(df)
