"""Phase B: Funding cost fixes.

Verifies:
- A2: Funding costs only deducted while position is open
- A2: No funding costs when no position is held
- B2: Proportional period calculation (not ceil)
- B2: 4h bars charge 0.5 period (not 1 full period)
"""
import numpy as np
import pandas as pd
import pytest

from core.backtest.engine import BacktestEngine, _apply_funding_costs
from core.strategy.dna import (
    ExecutionGenes,
    LogicGenes,
    RiskGenes,
    SignalGene,
    SignalRole,
    StrategyDNA,
)


def _make_dna(leverage=1, direction="long", sl=0.05, tp=0.10, pos_size=0.5):
    return StrategyDNA(
        signal_genes=[
            SignalGene('RSI', {'period': 14}, SignalRole.ENTRY_TRIGGER, 'RSI_14',
                        {'type': 'lt', 'threshold': 30}),
            SignalGene('RSI', {'period': 14}, SignalRole.EXIT_TRIGGER, 'RSI_14',
                        {'type': 'gt', 'threshold': 70}),
        ],
        logic_genes=LogicGenes(entry_logic='AND', exit_logic='AND'),
        execution_genes=ExecutionGenes(timeframe='4h', symbol='BTCUSDT'),
        risk_genes=RiskGenes(
            stop_loss=sl, take_profit=tp, position_size=pos_size,
            leverage=leverage, direction=direction,
        ),
    )


def _make_ohlcv(n=200, start="2024-01-01", seed=42):
    """Create synthetic OHLCV DataFrame."""
    np.random.seed(seed)
    dates = pd.date_range(start, periods=n, freq='4h', tz='UTC')
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    df = pd.DataFrame({
        'open': close * 0.999, 'high': close * 1.005,
        'low': close * 0.995, 'close': close, 'volume': 1000.0,
    }, index=dates)
    df.index.name = 'timestamp'
    df['rsi_14'] = np.clip(50 + np.random.randn(n) * 20, 0, 100)
    return df


# ── A2: Funding costs only while position is open ──

def test_funding_only_during_open_position():
    """Funding costs should only be deducted during bars where a position
    is held, not during bars where the portfolio is flat.

    Setup: Create a scenario with one trade that opens and closes.
    Compare funding cost with a scenario where position is held the entire time.
    """
    n = 100
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=n, freq='4h', tz='UTC')
    close = 100 + np.cumsum(np.random.randn(n) * 0.3)

    df = pd.DataFrame({
        'open': close * 0.999, 'high': close * 1.005,
        'low': close * 0.995, 'close': close, 'volume': 1000.0,
    }, index=dates)
    df.index.name = 'timestamp'
    df['rsi_14'] = 50.0
    # Entry at bar 5, exit at bar 25
    df.loc[df.index[5], 'rsi_14'] = 20
    df.loc[df.index[25], 'rsi_14'] = 80

    dna = _make_dna(leverage=5, sl=0.0, tp=0.0)
    engine = BacktestEngine(init_cash=100000)
    result = engine.run(dna, df)

    # Total funding cost should be less than if charged for ALL bars
    # With 5x leverage, borrowed_ratio = 4/5 = 0.8
    # Rate per 8h = 0.001
    # 4h bar: periods_per_bar = 4/8 = 0.5
    # cost_rate = 0.001 * 0.5 * 0.8 = 0.0004
    # If charged for all 99 bars: ~100000 * 0.0004 * 99 ≈ 3960
    # If only charged for ~20 bars (bar 5-25): ~100000 * 0.0004 * 20 ≈ 800
    max_possible_cost = 100000 * 0.0004 * 99  # All bars
    assert result.total_funding_cost < max_possible_cost * 0.5, \
        f"Funding cost {result.total_funding_cost} should be less than half of all-bars cost {max_possible_cost}"


def test_no_funding_without_trades():
    """No funding costs should be charged when no trades are made."""
    n = 50
    dates = pd.date_range('2024-01-01', periods=n, freq='4h', tz='UTC')
    close = np.ones(n) * 100

    df = pd.DataFrame({
        'open': close * 0.999, 'high': close * 1.005,
        'low': close * 0.995, 'close': close, 'volume': 1000.0,
    }, index=dates)
    df.index.name = 'timestamp'
    df['rsi_14'] = 50.0  # No entry/exit signals

    dna = _make_dna(leverage=5, sl=0.0, tp=0.0)
    engine = BacktestEngine(init_cash=100000)
    result = engine.run(dna, df)

    assert result.total_trades == 0
    assert result.total_funding_cost == 0.0, \
        f"No funding cost expected with no trades, got {result.total_funding_cost}"


def test_no_funding_with_1x_leverage():
    """1x leverage should never incur funding costs."""
    df = _make_ohlcv()
    dna = _make_dna(leverage=1)
    engine = BacktestEngine(init_cash=100000)
    result = engine.run(dna, df)

    assert result.total_funding_cost == 0.0


def test_funding_cost_positive_with_open_leveraged_position():
    """Leveraged position that stays open should incur funding costs."""
    n = 100
    dates = pd.date_range('2024-01-01', periods=n, freq='4h', tz='UTC')
    close = np.ones(n) * 100

    df = pd.DataFrame({
        'open': close * 0.999, 'high': close * 1.005,
        'low': close * 0.995, 'close': close, 'volume': 1000.0,
    }, index=dates)
    df.index.name = 'timestamp'
    df['rsi_14'] = 50.0
    df.loc[df.index[5], 'rsi_14'] = 20  # Entry at bar 5, no exit

    dna = _make_dna(leverage=3, sl=0.0, tp=0.0)
    engine = BacktestEngine(init_cash=100000)
    result = engine.run(dna, df)

    # Should have at least 1 trade that stays open
    assert result.total_trades >= 1
    # Funding cost should be positive
    assert result.total_funding_cost > 0.0, \
        f"Expected positive funding cost, got {result.total_funding_cost}"


# ── B2: Proportional period calculation ──

def test_funding_rate_proportional_not_ceil():
    """4h bars should use 0.5 period (4/8), not 1 full period (ceil)."""
    equity = pd.Series(np.full(100, 100000.0))

    # Create a trades_df that covers all bars
    dates = equity.index = pd.date_range('2024-01-01', periods=100, freq='4h', tz='UTC')
    trades_df = pd.DataFrame({
        'Entry Timestamp': [dates[0]],
        'Exit Timestamp': [dates[-1]],
    })

    result_curve, total_cost = _apply_funding_costs(
        equity, leverage=3, timeframe='4h', trades_df=trades_df,
    )

    # With proportional: periods_per_bar = 4/8 = 0.5
    # cost_rate = 0.001 * 0.5 * (2/3) = 0.000333
    # Total ≈ 100000 * 0.000333 * 99 ≈ 3300
    # With ceil: periods_per_bar = 1
    # cost_rate = 0.001 * 1.0 * (2/3) = 0.000667
    # Total ≈ 100000 * 0.000667 * 99 ≈ 6600
    assert total_cost < 4000, \
        f"With proportional rate, total cost {total_cost} should be < 4000"


def test_funding_rate_1h_bar():
    """1h bars should use 0.125 period (1/8), not 1 full period."""
    equity = pd.Series(np.full(100, 100000.0))
    dates = equity.index = pd.date_range('2024-01-01', periods=100, freq='1h', tz='UTC')
    trades_df = pd.DataFrame({
        'Entry Timestamp': [dates[0]],
        'Exit Timestamp': [dates[-1]],
    })

    result_curve, total_cost = _apply_funding_costs(
        equity, leverage=2, timeframe='1h', trades_df=trades_df,
    )

    # With proportional: periods_per_bar = 1/8 = 0.125
    # cost_rate = 0.001 * 0.125 * 0.5 = 0.0000625
    # Total ≈ 100000 * 0.0000625 * 99 ≈ 619
    # With ceil: periods_per_bar = 1
    # Total ≈ 100000 * 0.001 * 0.5 * 99 ≈ 4950
    assert total_cost < 1000, \
        f"With proportional 1h rate, total cost {total_cost} should be < 1000"


def test_funding_rate_1d_bar():
    """1d bars should use 3 periods (24/8), same as ceil."""
    equity = pd.Series(np.full(100, 100000.0))
    dates = equity.index = pd.date_range('2024-01-01', periods=100, freq='1D', tz='UTC')
    trades_df = pd.DataFrame({
        'Entry Timestamp': [dates[0]],
        'Exit Timestamp': [dates[-1]],
    })

    result_curve, total_cost = _apply_funding_costs(
        equity, leverage=2, timeframe='1d', trades_df=trades_df,
    )

    # With proportional: periods_per_bar = 24/8 = 3.0
    # cost_rate = 0.001 * 3.0 * 0.5 = 0.0015
    # Total ≈ 100000 * 0.0015 * 99 ≈ 14850
    assert total_cost > 10000, \
        f"With 1d proportional rate, total cost {total_cost} should be > 10000"


# ── Regression ──

def test_equity_starts_at_init_cash_phaseB():
    """Equity curve should still start at init_cash after funding fix."""
    df = _make_ohlcv()
    dna = _make_dna()
    engine = BacktestEngine(init_cash=100000)
    result = engine.run(dna, df)

    assert abs(result.equity_curve.iloc[0] - 100000) < 1


def test_backward_compat_no_trades_df():
    """_apply_funding_costs without trades_df should deduct for all bars."""
    equity = pd.Series(np.full(100, 100000.0))

    result_curve, total_cost = _apply_funding_costs(
        equity, leverage=3, timeframe='4h',
    )

    # Without trades_df, should deduct for all bars (legacy)
    assert total_cost > 0
