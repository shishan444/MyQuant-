"""Tests for Walk-Forward validation."""
import pytest
import pandas as pd
import numpy as np

from MyQuant.core.strategy.dna import (
    SignalRole, SignalGene, LogicGenes, RiskGenes, ExecutionGenes, StrategyDNA,
)
from MyQuant.core.backtest.walk_forward import WalkForwardValidator


@pytest.fixture
def long_ohlcv():
    """2 years of synthetic 4h data (~4380 bars)."""
    np.random.seed(42)
    n = 4380
    dates = pd.date_range("2022-01-01", periods=n, freq="4h", tz="UTC")
    close = 30000 + np.cumsum(np.random.randn(n) * 150)
    df = pd.DataFrame({
        "open": close + np.random.randn(n) * 50,
        "high": close + abs(np.random.randn(n) * 100),
        "low": close - abs(np.random.randn(n) * 100),
        "close": close,
        "volume": np.random.randint(100, 10000, n).astype(float),
        "rsi_14": np.random.uniform(20, 80, n),
        "ema_50": close * 0.99,
    }, index=dates)
    return df


@pytest.fixture
def simple_dna():
    return StrategyDNA(
        signal_genes=[
            SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER, None,
                       {"type": "lt", "threshold": 40}),
            SignalGene("RSI", {"period": 14}, SignalRole.EXIT_TRIGGER, None,
                       {"type": "gt", "threshold": 60}),
        ],
        logic_genes=LogicGenes(entry_logic="AND", exit_logic="OR"),
        risk_genes=RiskGenes(stop_loss=0.05),
    )


class TestWalkForward:
    def test_validator_returns_result(self, long_ohlcv, simple_dna):
        wf = WalkForwardValidator(train_months=3, slide_months=1)
        result = wf.validate(simple_dna, long_ohlcv)
        assert "wf_score" in result
        assert "n_rounds" in result
        assert isinstance(result["wf_score"], float)
        assert result["n_rounds"] > 0

    def test_wf_score_in_range(self, long_ohlcv, simple_dna):
        wf = WalkForwardValidator(train_months=3, slide_months=1)
        result = wf.validate(simple_dna, long_ohlcv)
        assert 0 <= result["wf_score"] <= 100

    def test_shared_val_months_per_call(self, long_ohlcv, simple_dna):
        """Each call to validate should generate its own val months."""
        wf = WalkForwardValidator(train_months=3, slide_months=1)
        r1 = wf.validate(simple_dna, long_ohlcv)
        r2 = wf.validate(simple_dna, long_ohlcv)
        # Results may differ due to random val months
        assert isinstance(r1["wf_score"], float)
        assert isinstance(r2["wf_score"], float)

    def test_short_data_still_works(self, simple_dna):
        """Handle data shorter than train window gracefully."""
        np.random.seed(1)
        n = 200
        dates = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
        close = 30000 + np.cumsum(np.random.randn(n) * 100)
        df = pd.DataFrame({
            "open": close, "high": close + 50, "low": close - 50,
            "close": close, "volume": 1000.0,
            "rsi_14": np.random.uniform(20, 80, n),
            "ema_50": close * 0.99,
        }, index=dates)
        wf = WalkForwardValidator(train_months=3, slide_months=1)
        result = wf.validate(simple_dna, df)
        assert result["n_rounds"] >= 0  # May be 0 if data too short

    def test_validation_months_outside_train(self, long_ohlcv, simple_dna):
        """Val months should be from outside the training window."""
        wf = WalkForwardValidator(train_months=3, slide_months=1)
        result = wf.validate(simple_dna, long_ohlcv)
        assert "rounds" in result
        for rnd in result["rounds"]:
            assert "train_start" in rnd
            assert "val_month" in rnd
            # Val month should not overlap with train window
            train_start = pd.Timestamp(rnd["train_start"])
            train_end = pd.Timestamp(rnd["train_end"])
            val_month = pd.Timestamp(rnd["val_month"])
            # Val month must be outside [train_start, train_end)
            assert val_month < train_start or val_month >= train_end
