"""Tests for visualization modules: kline, equity_curve, generation_chart, chart_builder."""

import pytest

pytestmark = [pytest.mark.unit]
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from MyQuant.core.strategy.dna import (
    SignalRole, SignalGene, LogicGenes, RiskGenes, ExecutionGenes, StrategyDNA,
)
from MyQuant.core.backtest.engine import BacktestEngine
from MyQuant.core.features.indicators import compute_all_indicators
from MyQuant.core.visualization.kline_chart import build_kline_chart
from MyQuant.core.visualization.equity_curve import build_equity_curve
from MyQuant.core.visualization.generation_chart import build_generation_chart
from MyQuant.core.visualization.quick_preview import build_quick_preview
from MyQuant.core.visualization.chart_builder import build_champion_report, build_evolution_dashboard

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_ohlcv():
    """500 bars of synthetic 4h OHLCV data with indicators."""
    np.random.seed(42)
    n = 500
    dates = pd.date_range("2023-01-01", periods=n, freq="4h")
    close = 30000 + np.cumsum(np.random.randn(n) * 200)
    df = pd.DataFrame({
        "open": close + np.random.randn(n) * 50,
        "high": close + abs(np.random.randn(n) * 100),
        "low": close - abs(np.random.randn(n) * 100),
        "close": close,
        "volume": np.random.randint(100, 10000, n).astype(float),
    }, index=dates)
    return compute_all_indicators(df)

@pytest.fixture
def valid_dna():
    return StrategyDNA(
        strategy_id="test-viz",
        signal_genes=[
            SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER, None,
                       {"type": "lt", "threshold": 30}),
            SignalGene("RSI", {"period": 14}, SignalRole.EXIT_TRIGGER, None,
                       {"type": "gt", "threshold": 70}),
        ],
        logic_genes=LogicGenes(entry_logic="AND", exit_logic="OR"),
        execution_genes=ExecutionGenes(timeframe="4h", symbol="BTCUSDT"),
        risk_genes=RiskGenes(stop_loss=0.05, position_size=0.3),
    )

@pytest.fixture
def sample_entries(sample_ohlcv):
    """Generate some entry signals."""
    rsi = sample_ohlcv["rsi_14"]
    return rsi < 30

@pytest.fixture
def sample_exits(sample_ohlcv):
    """Generate some exit signals."""
    rsi = sample_ohlcv["rsi_14"]
    return rsi > 70

@pytest.fixture
def sample_history():
    return [
        {"generation": 1, "best_score": 45.0, "avg_score": 30.0},
        {"generation": 2, "best_score": 52.0, "avg_score": 35.0},
        {"generation": 3, "best_score": 58.5, "avg_score": 40.2},
        {"generation": 4, "best_score": 55.0, "avg_score": 38.0},
        {"generation": 5, "best_score": 63.0, "avg_score": 42.1},
    ]

# ===========================================================================
# K-Line Chart Tests
# ===========================================================================

class TestKlineChart:
    def test_returns_figure(self, sample_ohlcv, sample_entries, sample_exits):
        fig = build_kline_chart(sample_ohlcv, sample_entries, sample_exits)
        assert isinstance(fig, go.Figure)

    def test_has_candlestick_trace(self, sample_ohlcv, sample_entries, sample_exits):
        fig = build_kline_chart(sample_ohlcv, sample_entries, sample_exits)
        candlestick_traces = [t for t in fig.data if isinstance(t, go.Candlestick)]
        assert len(candlestick_traces) == 1

    def test_buy_sell_markers(self, sample_ohlcv, sample_entries, sample_exits):
        fig = build_kline_chart(sample_ohlcv, sample_entries, sample_exits)
        trace_names = [t.name for t in fig.data]

        if sample_entries.any():
            assert "Buy" in trace_names
        if sample_exits.any():
            assert "Sell" in trace_names

    def test_marker_positions_match_signals(self, sample_ohlcv, sample_entries, sample_exits):
        fig = build_kline_chart(sample_ohlcv, sample_entries, sample_exits)

        buy_trace = next((t for t in fig.data if t.name == "Buy"), None)
        if buy_trace and sample_entries.any():
            buy_indices = sample_entries[sample_entries].index
            assert len(buy_trace.x) == len(buy_indices)

        sell_trace = next((t for t in fig.data if t.name == "Sell"), None)
        if sell_trace and sample_exits.any():
            sell_indices = sample_exits[sample_exits].index
            assert len(sell_trace.x) == len(sell_indices)

    def test_indicator_overlay(self, sample_ohlcv, sample_entries, sample_exits):
        fig = build_kline_chart(
            sample_ohlcv, sample_entries, sample_exits,
            indicator_columns=["ema_50", "ema_100"],
        )
        trace_names = [t.name for t in fig.data]
        assert "ema_50" in trace_names
        assert "ema_100" in trace_names

    def test_rsi_subpresent(self, sample_ohlcv, sample_entries, sample_exits):
        """When data has RSI column, should have 2 subplots."""
        fig = build_kline_chart(sample_ohlcv, sample_entries, sample_exits)
        # RSI column exists in sample_ohlcv (rsi_14)
        rsi_traces = [t for t in fig.data if t.name == "RSI"]
        assert len(rsi_traces) == 1

    def test_title_set(self, sample_ohlcv, sample_entries, sample_exits):
        fig = build_kline_chart(
            sample_ohlcv, sample_entries, sample_exits,
            title="Test Title",
        )
        assert fig.layout.title.text == "Test Title"

# ===========================================================================
# Equity Curve Tests
# ===========================================================================

class TestEquityCurve:
    def test_returns_figure(self, sample_ohlcv):
        equity = pd.Series(
            np.linspace(100000, 120000, len(sample_ohlcv)),
            index=sample_ohlcv.index,
        )
        fig = build_equity_curve(equity, sample_ohlcv["close"])
        assert isinstance(fig, go.Figure)

    def test_two_traces(self, sample_ohlcv):
        equity = pd.Series(
            np.linspace(100000, 120000, len(sample_ohlcv)),
            index=sample_ohlcv.index,
        )
        fig = build_equity_curve(equity, sample_ohlcv["close"])
        assert len(fig.data) == 2

    def test_same_start_point(self, sample_ohlcv):
        equity = pd.Series(
            np.linspace(100000, 120000, len(sample_ohlcv)),
            index=sample_ohlcv.index,
        )
        fig = build_equity_curve(equity, sample_ohlcv["close"])
        strategy_start = fig.data[0].y[0]
        benchmark_start = fig.data[1].y[0]
        assert abs(strategy_start - benchmark_start) < 1.0

    def test_trace_names(self, sample_ohlcv):
        equity = pd.Series(
            np.linspace(100000, 100000, len(sample_ohlcv)),
            index=sample_ohlcv.index,
        )
        fig = build_equity_curve(equity, sample_ohlcv["close"])
        names = [t.name for t in fig.data]
        assert "Strategy" in names
        assert "Buy & Hold" in names

    def test_empty_data_returns_figure(self):
        equity = pd.Series([], dtype=float)
        benchmark = pd.Series([], dtype=float)
        fig = build_equity_curve(equity, benchmark)
        assert isinstance(fig, go.Figure)

# ===========================================================================
# Generation Chart Tests
# ===========================================================================

class TestGenerationChart:
    def test_returns_figure(self, sample_history):
        fig = build_generation_chart(sample_history)
        assert isinstance(fig, go.Figure)

    def test_three_lines_with_target(self, sample_history):
        fig = build_generation_chart(sample_history, target_score=80.0)
        trace_names = [t.name for t in fig.data]
        assert "Best Score" in trace_names
        assert "Avg Score" in trace_names

    def test_empty_history_no_crash(self):
        fig = build_generation_chart([])
        assert isinstance(fig, go.Figure)

    def test_generation_count_matches(self, sample_history):
        fig = build_generation_chart(sample_history)
        best_trace = next(t for t in fig.data if t.name == "Best Score")
        assert len(best_trace.x) == len(sample_history)

# ===========================================================================
# Quick Preview Tests
# ===========================================================================

class TestQuickPreview:
    def test_returns_figure(self, valid_dna, sample_ohlcv):
        engine = BacktestEngine()
        _, portfolio = engine.run_with_portfolio(valid_dna, sample_ohlcv)
        fig = build_quick_preview(portfolio)
        assert isinstance(fig, go.Figure)

# ===========================================================================
# Chart Builder Tests
# ===========================================================================

class TestChartBuilder:
    def test_champion_report_keys(self, valid_dna, sample_ohlcv):
        charts = build_champion_report(valid_dna, sample_ohlcv)
        assert "kline" in charts
        assert "equity" in charts
        assert "quick_preview" in charts

    def test_champion_report_figures(self, valid_dna, sample_ohlcv):
        charts = build_champion_report(valid_dna, sample_ohlcv)
        for key, fig in charts.items():
            assert isinstance(fig, go.Figure), f"{key} should be a Figure"

    def test_evolution_dashboard_keys(self, sample_history):
        dashboard = build_evolution_dashboard(sample_history, target_score=80.0)
        assert "generation" in dashboard
        assert isinstance(dashboard["generation"], go.Figure)

    def test_champion_report_with_result(self, valid_dna, sample_ohlcv):
        engine = BacktestEngine()
        result = engine.run(valid_dna, sample_ohlcv)
        charts = build_champion_report(valid_dna, sample_ohlcv, result)
        assert "kline" in charts
