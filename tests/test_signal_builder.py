"""Tests for signal builder module.

Tests:
- extract_indicator_requirements parses DNA correctly
- build_signals produces entry/exit boolean Series
- handles missing indicator columns gracefully
"""

import pytest

pytestmark = [pytest.mark.unit]
import pandas as pd
import numpy as np

from core.strategy.dna import (
    SignalRole, SignalGene, LogicGenes, RiskGenes, ExecutionGenes, StrategyDNA,
)
from core.features.signal_builder import (
    extract_indicator_requirements,
    build_signals,
)

@pytest.fixture
def enhanced_df():
    """DataFrame with OHLCV + RSI + EMA columns."""
    np.random.seed(123)
    n = 500
    dates = pd.date_range("2024-01-01", periods=n, freq="4h")
    close = 30000 + np.cumsum(np.random.randn(n) * 100)
    df = pd.DataFrame({
        "open": close + np.random.randn(n) * 30,
        "high": close + abs(np.random.randn(n) * 80),
        "low": close - abs(np.random.randn(n) * 80),
        "close": close,
        "volume": np.random.randint(100, 5000, n).astype(float),
        "rsi_14": np.random.uniform(20, 80, n),
        "ema_50": close * 0.99,
        "ema_100": close * 0.98,
        "macd_12_26_9": np.random.randn(n) * 10,
        "macd_signal_12_26_9": np.random.randn(n) * 5,
        "macd_histogram_12_26_9": np.random.randn(n) * 3,
    }, index=dates)
    return df

class TestExtractRequirements:
    def test_extracts_indicator_names_and_params(self):
        dna = StrategyDNA(
            signal_genes=[
                SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER, None, {"type": "lt", "threshold": 30}),
                SignalGene("EMA", {"period": 50}, SignalRole.ENTRY_GUARD, None, {"type": "price_above"}),
            ],
        )
        reqs = extract_indicator_requirements(dna)
        assert len(reqs) == 2
        assert reqs[0] == ("RSI", {"period": 14})
        assert reqs[1] == ("EMA", {"period": 50})

    def test_deduplicates_same_indicator(self):
        dna = StrategyDNA(
            signal_genes=[
                SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER, None, {"type": "lt", "threshold": 30}),
                SignalGene("RSI", {"period": 14}, SignalRole.EXIT_TRIGGER, None, {"type": "gt", "threshold": 70}),
            ],
        )
        reqs = extract_indicator_requirements(dna)
        assert len(reqs) == 1

    def test_handles_empty_signal_genes(self):
        dna = StrategyDNA(signal_genes=[])
        reqs = extract_indicator_requirements(dna)
        assert len(reqs) == 0

class TestBuildSignals:
    def test_simple_rsi_strategy(self, enhanced_df):
        dna = StrategyDNA(
            signal_genes=[
                SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER, None, {"type": "lt", "threshold": 35}),
                SignalGene("RSI", {"period": 14}, SignalRole.EXIT_TRIGGER, None, {"type": "gt", "threshold": 65}),
            ],
            logic_genes=LogicGenes(entry_logic="AND", exit_logic="OR"),
            risk_genes=RiskGenes(stop_loss=0.05),
        )
        entries, exits = build_signals(dna, enhanced_df)
        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)
        assert entries.dtype == bool
        assert exits.dtype == bool

    def test_with_guard_conditions(self, enhanced_df):
        dna = StrategyDNA(
            signal_genes=[
                SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER, None, {"type": "lt", "threshold": 35}),
                SignalGene("EMA", {"period": 50}, SignalRole.ENTRY_GUARD, None, {"type": "price_above"}),
                SignalGene("RSI", {"period": 14}, SignalRole.EXIT_TRIGGER, None, {"type": "gt", "threshold": 65}),
            ],
            logic_genes=LogicGenes(entry_logic="AND", exit_logic="OR"),
            risk_genes=RiskGenes(stop_loss=0.05),
        )
        entries, exits = build_signals(dna, enhanced_df)
        # With AND logic + guard, entries should be subset of trigger-only
        trigger_only = enhanced_df["rsi_14"] < 35
        assert entries.sum() <= trigger_only.sum()

    def test_missing_column_produces_no_signal(self, enhanced_df):
        """If an indicator column is missing, that gene should produce no signal."""
        dna = StrategyDNA(
            signal_genes=[
                SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER, None, {"type": "lt", "threshold": 35}),
                SignalGene("CCI", {"period": 20}, SignalRole.ENTRY_GUARD, None, {"type": "gt", "threshold": 100}),
            ],
            logic_genes=LogicGenes(entry_logic="OR", exit_logic="OR"),
            risk_genes=RiskGenes(stop_loss=0.05),
        )
        entries, exits = build_signals(dna, enhanced_df)
        # CCI column missing -> only RSI signals
        assert entries.sum() > 0  # RSI signals still work
