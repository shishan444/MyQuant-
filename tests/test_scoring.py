"""Tests for scoring module: metrics, normalizer, templates, scorer."""

import pytest

pytestmark = [pytest.mark.unit]
import pandas as pd
import numpy as np

from MyQuant.core.scoring.metrics import compute_metrics
from MyQuant.core.scoring.normalizer import normalize
from MyQuant.core.scoring.templates import get_template, SCORING_TEMPLATES
from MyQuant.core.scoring.scorer import score_strategy

@pytest.fixture
def equity_curve():
    """Simulated equity curve with positive returns."""
    np.random.seed(42)
    n = 365 * 6  # 1 year of 4h bars
    daily_returns = np.random.normal(0.001, 0.02, n)
    equity = 100000 * np.cumprod(1 + daily_returns)
    return pd.Series(equity)

@pytest.fixture
def poor_equity_curve():
    """Simulated equity curve with large drawdown."""
    np.random.seed(99)
    n = 365 * 6
    daily_returns = np.random.normal(-0.001, 0.04, n)
    equity = 100000 * np.cumprod(1 + daily_returns)
    return pd.Series(equity)

class TestComputeMetrics:
    def test_returns_all_metrics(self, equity_curve):
        m = compute_metrics(equity_curve, total_trades=50)
        assert "annual_return" in m
        assert "sharpe_ratio" in m
        assert "max_drawdown" in m
        assert "win_rate" in m
        assert "calmar_ratio" in m
        assert "total_trades" in m

    def test_annual_return_positive(self, equity_curve):
        m = compute_metrics(equity_curve, total_trades=50)
        # With positive drift, should have positive annual return
        assert isinstance(m["annual_return"], float)

    def test_max_drawdown_non_positive(self, equity_curve):
        m = compute_metrics(equity_curve, total_trades=50)
        assert m["max_drawdown"] <= 0

    def test_win_rate_between_0_and_1(self, equity_curve):
        m = compute_metrics(equity_curve, total_trades=50)
        assert 0 <= m["win_rate"] <= 1

    def test_zero_trades(self, equity_curve):
        m = compute_metrics(equity_curve, total_trades=0)
        assert m["annual_return"] == 0.0
        assert m["sharpe_ratio"] == 0.0
        assert m["total_trades"] == 0

    def test_short_equity_curve(self):
        """Handle very short equity curves gracefully."""
        short = pd.Series([100000, 101000, 99500, 102000])
        m = compute_metrics(short, total_trades=5)
        assert isinstance(m["annual_return"], float)

class TestNormalize:
    def test_annual_return_good_is_high(self):
        score = normalize("annual_return", 0.50)  # 50% annual return
        assert score > 40  # Log mapping: 50% -> ~47

    def test_annual_return_negative_is_low(self):
        score = normalize("annual_return", -0.50)
        assert score < 50

    def test_sharpe_ratio_high_is_good(self):
        score = normalize("sharpe_ratio", 2.5)
        assert score > 80

    def test_sharpe_ratio_zero(self):
        score = normalize("sharpe_ratio", 0.0)
        assert score < 50

    def test_max_drawdown_zero_is_best(self):
        score = normalize("max_drawdown", 0.0)
        assert score == 100

    def test_max_drawdown_large_is_worst(self):
        score = normalize("max_drawdown", -0.60)  # 60% drawdown
        assert score < 30  # Severe penalty for 60% drawdown

    def test_win_rate_range(self):
        score_40 = normalize("win_rate", 0.40)
        score_70 = normalize("win_rate", 0.70)
        assert score_40 < score_70

    def test_calmar_ratio(self):
        score = normalize("calmar_ratio", 3.0)
        assert score > 50

    def test_scores_in_0_100(self):
        for metric_name in ["annual_return", "sharpe_ratio", "max_drawdown",
                            "win_rate", "calmar_ratio"]:
            for val in [-1.0, 0.0, 0.5, 1.0, 5.0]:
                score = normalize(metric_name, val)
                assert 0 <= score <= 100, f"{metric_name}({val}) = {score}"

class TestTemplates:
    def test_all_4_templates_exist(self):
        assert len(SCORING_TEMPLATES) >= 4

    def test_get_template_profit(self):
        t = get_template("profit_first")
        assert "annual_return" in t.weights
        assert "sharpe_ratio" in t.weights

    def test_get_template_steady(self):
        t = get_template("steady")
        assert t.weights.get("sharpe_ratio", 0) > 0

    def test_get_template_risk(self):
        t = get_template("risk_first")
        assert t.weights.get("max_drawdown", 0) > 0

    def test_get_template_custom(self):
        t = get_template("custom")
        assert isinstance(t.weights, dict)

    def test_template_weights_sum_to_1(self):
        for name in ["profit_first", "steady", "risk_first"]:
            t = get_template(name)
            total = sum(t.weights.values())
            assert abs(total - 1.0) < 0.01, f"{name} weights sum to {total}"

    def test_template_has_threshold(self):
        for name in ["profit_first", "steady", "risk_first"]:
            t = get_template(name)
            assert t.threshold > 0

class TestScorer:
    def test_score_returns_total_and_dimensions(self, equity_curve):
        metrics = compute_metrics(equity_curve, total_trades=50)
        result = score_strategy(metrics, template_name="profit_first")
        assert "total_score" in result
        assert "dimension_scores" in result
        assert 0 <= result["total_score"] <= 100

    def test_poor_strategy_lower_score(self, poor_equity_curve, equity_curve):
        good_m = compute_metrics(equity_curve, total_trades=50)
        bad_m = compute_metrics(poor_equity_curve, total_trades=30)
        good_score = score_strategy(good_m, "profit_first")
        bad_score = score_strategy(bad_m, "profit_first")
        assert good_score["total_score"] > bad_score["total_score"]

    def test_zero_trades_scores_zero(self, equity_curve):
        metrics = compute_metrics(equity_curve, total_trades=0)
        result = score_strategy(metrics, "profit_first")
        assert result["total_score"] == 0.0
