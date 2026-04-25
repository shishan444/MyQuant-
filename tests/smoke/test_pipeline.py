"""Smoke tests for the core DNA -> signal -> backtest -> score pipeline.

These tests verify the main processing chain works end-to-end.
Run with: pytest -m smoke
"""

import pytest

from core.backtest.engine import BacktestEngine
from core.strategy.dna import StrategyDNA
from core.strategy.executor import dna_to_signal_set
from tests.helpers.data_factory import make_dna, make_ohlcv, make_mtf_dna


@pytest.mark.smoke
class TestSingleTFPipeline:
    """Smoke: single-timeframe DNA -> signals -> backtest."""

    def test_rsi_dna_produces_valid_backtest(self):
        """RSI strategy runs through the full pipeline without error."""
        dna = make_dna(indicator="RSI", timeframe="4h")
        df = make_ohlcv(n=500, freq="4h")

        signal_set = dna_to_signal_set(dna, df)
        assert signal_set.entries.dtype == bool
        assert signal_set.exits.dtype == bool

        engine = BacktestEngine(init_cash=100000)
        result = engine.run(dna, df, signal_set=signal_set)

        assert result.total_trades >= 0
        assert result.equity_curve is not None
        assert len(result.equity_curve) == len(df)

    def test_ema_dna_produces_valid_backtest(self):
        """EMA strategy runs through the full pipeline."""
        from tests.helpers.data_factory import make_ema_dna

        dna = make_ema_dna(timeframe="4h")
        df = make_ohlcv(n=300, freq="4h")

        signal_set = dna_to_signal_set(dna, df)
        engine = BacktestEngine(init_cash=100000)
        result = engine.run(dna, df, signal_set=signal_set)

        assert isinstance(result.total_return, float)
        assert isinstance(result.max_drawdown, float)


@pytest.mark.smoke
class TestMTFPipeline:
    """Smoke: multi-timeframe DNA pipeline."""

    def test_mtf_and_logic_runs(self):
        """MTF AND logic strategy runs without error."""
        dna = make_mtf_dna(timeframes=("1d", "4h", "15m"), cross_layer_logic="AND")
        assert dna.is_mtf
        assert len(dna.layers) == 3

    def test_mtf_or_logic_runs(self):
        """MTF OR logic strategy runs without error."""
        dna = make_mtf_dna(timeframes=("4h", "15m"), cross_layer_logic="OR")
        assert dna.is_mtf


@pytest.mark.smoke
class TestDataFactory:
    """Verify data_factory produces valid test data."""

    def test_make_ohlcv_shape(self):
        df = make_ohlcv(n=200, freq="1h")
        assert df.shape == (200, 5)
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert df.index.name == "timestamp"

    def test_make_ohlcv_ohlcv_valid(self):
        """High >= Close >= Low for all bars."""
        df = make_ohlcv(n=100)
        assert (df["high"] >= df["close"]).all()
        assert (df["low"] <= df["close"]).all()

    def test_make_dna_fields(self):
        dna = make_dna(indicator="RSI")
        assert len(dna.signal_genes) == 2
        assert dna.execution_genes.timeframe == "4h"
        assert dna.risk_genes.direction == "long"

    def test_make_mtf_dna_layers(self):
        dna = make_mtf_dna(timeframes=("1d", "4h"))
        assert dna.is_mtf
        assert [l.timeframe for l in dna.layers] == ["1d", "4h"]
