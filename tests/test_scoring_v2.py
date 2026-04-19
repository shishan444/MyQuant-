"""Tests for V2 scoring system upgrades: new metrics, normalizers, templates, sigmoid penalty."""
import math

import numpy as np
import pandas as pd
import pytest

from core.scoring.metrics import compute_metrics
from core.scoring.normalizer import normalize
from core.scoring.templates import get_template, SCORING_TEMPLATES, ScoringTemplate
from core.scoring.scorer import score_strategy


def _make_equity_curve(n=200, start=10000, drift=0.001) -> pd.Series:
    """Generate a simple upward-trending equity curve."""
    np.random.seed(42)
    returns = np.random.normal(drift, 0.01, n)
    prices = start * np.cumprod(1 + returns)
    dates = pd.date_range("2024-01-01", periods=n, freq="4h")
    return pd.Series(prices, index=dates)


def _make_trade_returns(n=50, win_rate=0.6, mean_win=0.02, mean_loss=-0.01) -> np.ndarray:
    """Generate synthetic trade returns."""
    np.random.seed(42)
    returns = []
    for _ in range(n):
        if np.random.random() < win_rate:
            returns.append(abs(np.random.normal(mean_win, 0.01)))
        else:
            returns.append(-abs(np.random.normal(mean_loss, 0.005)))
    return np.array(returns)


# -- Metrics tests --

class TestNewMetrics:
    def test_sortino_ratio_computed(self):
        eq = _make_equity_curve()
        returns = _make_trade_returns()
        metrics = compute_metrics(eq, total_trades=50, trade_returns=returns)
        assert "sortino_ratio" in metrics
        assert metrics["sortino_ratio"] >= 0

    def test_profit_factor_computed(self):
        eq = _make_equity_curve()
        returns = _make_trade_returns()
        metrics = compute_metrics(eq, total_trades=50, trade_returns=returns)
        assert "profit_factor" in metrics
        assert metrics["profit_factor"] > 0

    def test_profit_factor_all_wins(self):
        eq = _make_equity_curve()
        returns = np.array([0.01, 0.02, 0.015, 0.005, 0.01])
        metrics = compute_metrics(eq, total_trades=5, trade_returns=returns)
        assert metrics["profit_factor"] == 10.0  # Capped

    def test_max_consecutive_losses_computed(self):
        eq = _make_equity_curve()
        returns = np.array([0.01, -0.02, -0.01, -0.03, 0.02, -0.01, -0.02, 0.01])
        metrics = compute_metrics(eq, total_trades=8, trade_returns=returns)
        assert metrics["max_consecutive_losses"] == 3

    def test_monthly_consistency_computed(self):
        eq = _make_equity_curve(500)
        returns = _make_trade_returns(100)
        metrics = compute_metrics(eq, total_trades=100, trade_returns=returns)
        assert "monthly_consistency" in metrics
        assert 0 <= metrics["monthly_consistency"] <= 1.0

    def test_zero_trades_returns_zero_metrics(self):
        eq = _make_equity_curve()
        metrics = compute_metrics(eq, total_trades=0)
        assert metrics["sortino_ratio"] == 0.0
        assert metrics["profit_factor"] == 0.0
        assert metrics["max_consecutive_losses"] == 0
        assert metrics["monthly_consistency"] == 0.0


# -- Normalizer tests --

class TestNewNormalizers:
    def test_sortino_normalization(self):
        assert normalize("sortino_ratio", 2.0) == pytest.approx(50.0, abs=1)
        assert normalize("sortino_ratio", 4.0) == pytest.approx(100.0, abs=1)
        assert normalize("sortino_ratio", 0.0) == pytest.approx(0.0, abs=1)

    def test_profit_factor_normalization(self):
        assert normalize("profit_factor", 0.0) == 0.0
        assert normalize("profit_factor", 0.5) == pytest.approx(15.0, abs=1)
        assert normalize("profit_factor", 1.0) == pytest.approx(30.0, abs=1)
        assert normalize("profit_factor", 3.0) == pytest.approx(100.0, abs=1)

    def test_max_consecutive_losses_normalization(self):
        assert normalize("max_consecutive_losses", 0) == 100.0
        assert normalize("max_consecutive_losses", 5) == 50.0
        assert normalize("max_consecutive_losses", 10) == 0.0
        assert normalize("max_consecutive_losses", 15) == 0.0

    def test_monthly_consistency_normalization(self):
        assert normalize("monthly_consistency", 0.0) == 0.0
        assert normalize("monthly_consistency", 0.5) == pytest.approx(50.0)
        assert normalize("monthly_consistency", 1.0) == pytest.approx(100.0)

    def test_unknown_metric_defaults(self):
        assert normalize("unknown_metric", 0.0) == 50.0


# -- Template tests --

class TestNewTemplates:
    def test_all_templates_weight_sum_to_one(self):
        for name, template in SCORING_TEMPLATES.items():
            total_weight = sum(template.weights.values())
            assert total_weight == pytest.approx(1.0, abs=0.01), (
                f"Template '{name}' weights sum to {total_weight}"
            )

    def test_new_templates_exist(self):
        for name in ["balanced", "aggressive", "conservative"]:
            t = get_template(name)
            assert isinstance(t, ScoringTemplate)

    def test_legacy_templates_still_work(self):
        for name in ["profit_first", "steady", "risk_first", "custom"]:
            t = get_template(name)
            assert isinstance(t, ScoringTemplate)

    def test_aggressive_has_higher_return_weight(self):
        agg = get_template("aggressive")
        cons = get_template("conservative")
        assert agg.weights["annual_return"] > cons.weights["annual_return"]

    def test_conservative_has_higher_drawdown_weight(self):
        cons = get_template("conservative")
        agg = get_template("aggressive")
        assert cons.weights["max_drawdown"] > agg.weights["max_drawdown"]

    def test_unknown_template_raises(self):
        with pytest.raises(ValueError, match="Unknown template"):
            get_template("nonexistent")


# -- Sigmoid penalty tests --

class TestSigmoidPenalty:
    def test_zero_trades_zero_score(self):
        metrics = {"total_trades": 0, "annual_return": 0.5}
        result = score_strategy(metrics, "balanced")
        assert result["total_score"] == 0.0

    def test_few_trades_reduced_score(self):
        eq = _make_equity_curve(100)
        returns = _make_trade_returns(5)
        metrics = compute_metrics(eq, total_trades=3, trade_returns=returns[:3])
        result = score_strategy(metrics, "balanced")
        # Score should be significantly reduced but not zero
        assert 0 < result["total_score"] < 100

    def test_enough_trades_no_penalty(self):
        eq = _make_equity_curve(200)
        returns = _make_trade_returns(50)
        metrics = compute_metrics(eq, total_trades=50, trade_returns=returns)
        result = score_strategy(metrics, "balanced")
        # No penalty for >= 10 trades
        assert result["total_score"] > 0

    def test_sigmoid_curve_properties(self):
        """Sigmoid should give smooth penalty: 0->~0.07, 5->~0.50, 10->~0.93."""
        # At 0 trades, handled separately (returns 0)
        for count, expected_range in [(3, (0.1, 0.5)), (5, (0.3, 0.7)), (8, (0.6, 0.95))]:
            factor = 1.0 / (1.0 + math.exp(-0.5 * (count - 5)))
            assert expected_range[0] <= factor <= expected_range[1], (
                f"Trade count {count}: factor {factor} not in {expected_range}"
            )


# -- Integration: full scoring pipeline --

class TestFullScoringPipeline:
    def test_score_with_all_metrics(self):
        eq = _make_equity_curve(500)
        returns = _make_trade_returns(100)
        metrics = compute_metrics(eq, total_trades=100, trade_win_rate=0.6, trade_returns=returns)
        result = score_strategy(metrics, "balanced")
        assert "total_score" in result
        assert "dimension_scores" in result
        assert "raw_metrics" in result
        assert 0 <= result["total_score"] <= 100

    def test_all_templates_produce_scores(self):
        eq = _make_equity_curve(200)
        returns = _make_trade_returns(50)
        metrics = compute_metrics(eq, total_trades=50, trade_win_rate=0.6, trade_returns=returns)
        for name in SCORING_TEMPLATES:
            result = score_strategy(metrics, name)
            assert 0 <= result["total_score"] <= 100, (
                f"Template '{name}' score {result['total_score']} out of range"
            )
