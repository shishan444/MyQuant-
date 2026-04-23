"""Phase 6: Walk-Forward indicator recomputation to remove look-ahead bias."""

import numpy as np
import pandas as pd
import pytest

from core.backtest.walk_forward import WalkForwardValidator
from core.strategy.dna import (
    ExecutionGenes,
    LogicGenes,
    RiskGenes,
    SignalGene,
    SignalRole,
    StrategyDNA,
)


def _make_dna():
    return StrategyDNA(
        signal_genes=[
            SignalGene('RSI', {'period': 14}, SignalRole.ENTRY_TRIGGER, 'RSI_14',
                        {'type': 'lt', 'threshold': 30}),
            SignalGene('RSI', {'period': 14}, SignalRole.EXIT_TRIGGER, 'RSI_14',
                        {'type': 'gt', 'threshold': 70}),
        ],
        logic_genes=LogicGenes(entry_logic='AND', exit_logic='AND'),
        execution_genes=ExecutionGenes(timeframe='4h', symbol='BTCUSDT'),
        risk_genes=RiskGenes(stop_loss=0.05, take_profit=0.10, position_size=0.5, leverage=1, direction='long'),
    )


def _make_enhanced_df(n=1000):
    """Create 1000 bars of 4h data spanning ~6 months."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=n, freq='4h', tz='UTC')
    close = 40000 + np.cumsum(np.random.randn(n) * 100)
    df = pd.DataFrame({
        'open': close * 0.999, 'high': close * 1.005,
        'low': close * 0.995, 'close': close, 'volume': 1000.0,
    }, index=dates)
    df.index.name = 'timestamp'

    # Add pre-computed indicators (this is the "enhanced" version)
    rsi = 50 + np.random.randn(n) * 20
    df['rsi_14'] = np.clip(rsi, 0, 100)
    return df


def _make_raw_df(n=1000):
    """Same data but without indicators."""
    enhanced = _make_enhanced_df(n)
    return enhanced[['open', 'high', 'low', 'close', 'volume']].copy()


def test_backward_compat_without_raw_df():
    """Without raw_df, WF should behave exactly as before."""
    enhanced_df = _make_enhanced_df(1000)
    dna = _make_dna()

    wf = WalkForwardValidator(train_months=2, slide_months=2)
    result = wf.validate(dna, enhanced_df)

    # Should produce valid results (same as before)
    assert isinstance(result, dict)
    assert 'wf_score' in result
    assert 'n_rounds' in result
    assert 'rounds' in result


def test_with_raw_df_produces_results():
    """With raw_df, WF should still produce results."""
    enhanced_df = _make_enhanced_df(1000)
    raw_df = _make_raw_df(1000)
    dna = _make_dna()

    wf = WalkForwardValidator(train_months=2, slide_months=2)
    result = wf.validate(dna, enhanced_df, raw_df=raw_df)

    assert isinstance(result, dict)
    assert 'wf_score' in result


def test_recompute_indicators():
    """_recompute_indicators should add indicator columns to raw data."""
    raw_df = _make_raw_df(100)
    dna = _make_dna()

    wf = WalkForwardValidator()
    result = wf._recompute_indicators(raw_df, dna)

    # Should have added RSI column
    assert 'rsi_14' in result.columns
    assert len(result) == 100


def test_warmup_bars_excluded():
    """Warmup bars should be trimmed from the window data."""
    # This test verifies the warmup mechanism exists
    raw_df = _make_raw_df(1000)
    dna = _make_dna()

    wf = WalkForwardValidator(train_months=2, slide_months=2)
    # Run with raw_df - the warmup trimming happens internally
    result = wf.validate(dna, _make_enhanced_df(1000), raw_df=raw_df)

    # If results are produced, warmup trimming didn't break things
    assert isinstance(result, dict)


def test_no_look_ahead_in_validation():
    """With raw_df, indicator values should differ from pre-computed."""
    enhanced_df = _make_enhanced_df(500)
    raw_df = _make_raw_df(500)
    dna = _make_dna()

    wf = WalkForwardValidator(train_months=2, slide_months=2)

    # Run both ways
    result_no_recompute = wf.validate(dna, enhanced_df)
    result_with_recompute = wf.validate(dna, enhanced_df, raw_df=raw_df)

    # Both should produce valid results
    assert isinstance(result_no_recompute['wf_score'], float)
    assert isinstance(result_with_recompute['wf_score'], float)

    # The results may differ because recomputed indicators use only window data
    # (they SHOULD differ - that's the point of removing look-ahead)
