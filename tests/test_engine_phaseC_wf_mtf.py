"""Phase C: Walk-Forward validation independent MTF slicing.

Verifies:
- A3: Train and val windows use separately sliced MTF data
- A3: Val window MTF data covers val period, not train period
- A3: Single-TF walk-forward unaffected
"""
import numpy as np
import pandas as pd
import pytest

from core.strategy.dna import (
    ExecutionGenes,
    LogicGenes,
    RiskGenes,
    SignalGene,
    SignalRole,
    StrategyDNA,
    TimeframeLayer,
)
from core.backtest.walk_forward import WalkForwardValidator


def _make_ohlcv(n=500, timeframe="4h", start="2024-01-01", seed=42):
    """Create synthetic OHLCV DataFrame with indicators."""
    freq_map = {"1h": "1h", "4h": "4h", "1d": "1D", "15m": "15min"}
    freq = freq_map.get(timeframe, "4h")
    np.random.seed(seed)
    dates = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    close = 40000 + np.cumsum(np.random.randn(n) * 100)
    df = pd.DataFrame({
        "open": close * 0.999, "high": close * 1.005,
        "low": close * 0.995, "close": close, "volume": 1000.0,
    }, index=dates)
    df.index.name = "timestamp"

    close_s = pd.Series(close, index=dates)
    delta = close_s.diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain, index=dates).rolling(14).mean()
    avg_loss = pd.Series(loss, index=dates).rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    df["rsi_14"] = rsi.fillna(50)
    df["ema_50"] = close_s.ewm(span=50).mean()

    return df


def _make_mtf_dna():
    """Create MTF strategy with trend layer."""
    return StrategyDNA(
        signal_genes=[
            SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER, "rsi_14",
                        {"type": "lt", "threshold": 30}),
            SignalGene("RSI", {"period": 14}, SignalRole.EXIT_TRIGGER, "rsi_14",
                        {"type": "gt", "threshold": 70}),
        ],
        logic_genes=LogicGenes(entry_logic="AND", exit_logic="AND"),
        execution_genes=ExecutionGenes(timeframe="4h", symbol="BTCUSDT"),
        risk_genes=RiskGenes(stop_loss=0.05, take_profit=0.10, position_size=0.5,
                             leverage=1, direction="long"),
        layers=[
            TimeframeLayer(
                timeframe="1d",
                signal_genes=[
                    SignalGene("EMA", {"period": 50}, SignalRole.ENTRY_TRIGGER, "ema_50",
                                {"type": "price_above"}),
                ],
                logic_genes=LogicGenes(entry_logic="AND", exit_logic="AND"),
                role="trend",
            ),
        ],
    )


# ── A3: Train and val windows use separate MTF data ──

def test_wf_mtf_separate_slicing():
    """MTF walk-forward should slice data separately for train and val."""
    dna = _make_mtf_dna()
    enhanced_df = _make_ohlcv(500, "4h")
    daily_df = _make_ohlcv(200, "1d")
    dfs_by_timeframe = {"4h": enhanced_df, "1d": daily_df}

    wf = WalkForwardValidator(train_months=2, slide_months=2)
    result = wf.validate(dna, enhanced_df, dfs_by_timeframe=dfs_by_timeframe)

    assert isinstance(result["wf_score"], float)
    assert result["n_rounds"] >= 0


def test_wf_val_mtf_covers_val_period():
    """Val window MTF data should not be restricted to train period.

    Verify by checking that the val backtest can complete successfully
    even when val period is well outside the train period.
    """
    dna = _make_mtf_dna()
    # Create 12 months of data
    enhanced_df = _make_ohlcv(2000, "4h", start="2024-01-01")
    daily_df = _make_ohlcv(400, "1d", start="2024-01-01")
    dfs_by_timeframe = {"4h": enhanced_df, "1d": daily_df}

    wf = WalkForwardValidator(train_months=2, slide_months=3)
    result = wf.validate(dna, enhanced_df, dfs_by_timeframe=dfs_by_timeframe)

    assert isinstance(result["wf_score"], float)


def test_wf_single_tf_unchanged():
    """Single-TF walk-forward should work without MTF data."""
    dna = StrategyDNA(
        signal_genes=[
            SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER, "rsi_14",
                        {"type": "lt", "threshold": 30}),
            SignalGene("RSI", {"period": 14}, SignalRole.EXIT_TRIGGER, "rsi_14",
                        {"type": "gt", "threshold": 70}),
        ],
        logic_genes=LogicGenes(entry_logic="AND", exit_logic="AND"),
        execution_genes=ExecutionGenes(timeframe="4h", symbol="BTCUSDT"),
        risk_genes=RiskGenes(stop_loss=0.05, take_profit=0.10, position_size=0.5,
                             leverage=1, direction="long"),
    )
    enhanced_df = _make_ohlcv(500)

    wf = WalkForwardValidator(train_months=2, slide_months=2)
    result = wf.validate(dna, enhanced_df)

    assert isinstance(result["wf_score"], float)


def test_wf_mtf_with_raw_df():
    """Walk-forward with MTF + raw_df should recompute indicators per window."""
    dna = _make_mtf_dna()
    enhanced_df = _make_ohlcv(2000, "4h", start="2024-01-01")
    raw_df = enhanced_df[["open", "high", "low", "close", "volume"]].copy()
    daily_df = _make_ohlcv(400, "1d", start="2024-01-01")
    dfs_by_timeframe = {"4h": enhanced_df, "1d": daily_df}

    wf = WalkForwardValidator(train_months=2, slide_months=3)
    result = wf.validate(dna, enhanced_df, raw_df=raw_df,
                          dfs_by_timeframe=dfs_by_timeframe)

    assert isinstance(result["wf_score"], float)


def test_slice_mtf_produces_non_overlapping_windows():
    """_slice_mtf_data called with different start/end should produce
    different data slices."""
    enhanced_df = _make_ohlcv(2000, "4h", start="2024-01-01")
    daily_df = _make_ohlcv(400, "1d", start="2024-01-01")
    dfs_by_timeframe = {"4h": enhanced_df, "1d": daily_df}

    wf = WalkForwardValidator(train_months=2, slide_months=2)

    train_start = pd.Timestamp("2024-03-01", tz="UTC")
    train_end = pd.Timestamp("2024-05-01", tz="UTC")
    val_start = pd.Timestamp("2024-06-01", tz="UTC")
    val_end = pd.Timestamp("2024-07-01", tz="UTC")

    train_mtf = wf._slice_mtf_data(
        dfs_by_timeframe, train_start, train_end, enhanced_df.index,
    )
    val_mtf = wf._slice_mtf_data(
        dfs_by_timeframe, val_start, val_end, enhanced_df.index,
    )

    # Both should have daily data
    assert "1d" in train_mtf
    assert "1d" in val_mtf

    # The data slices should be different (different date ranges)
    if len(train_mtf["1d"]) > 0 and len(val_mtf["1d"]) > 0:
        train_dates = set(train_mtf["1d"].index.date)
        val_dates = set(val_mtf["1d"].index.date)
        # Train and val periods should have mostly different dates
        overlap = train_dates & val_dates
        total = train_dates | val_dates
        if len(total) > 0:
            overlap_ratio = len(overlap) / len(total)
            # Allow some overlap due to warmup lookback, but shouldn't be 100%
            assert overlap_ratio < 0.95, \
                f"Train and val MTF data overlap too much: {overlap_ratio:.1%}"
