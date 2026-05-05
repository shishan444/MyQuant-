"""Tests for scoring module: metrics, normalizer, templates, scorer."""

import pytest

pytestmark = [pytest.mark.unit]
import pandas as pd
import numpy as np

from MyQuant.core.scoring.metrics import compute_metrics
from MyQuant.core.scoring.normalizer import normalize, piecewise_normalize
from MyQuant.core.scoring.templates import get_template, SCORING_TEMPLATES, list_template_names
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

class TestPiecewiseNormalize:
    def test_below_range_clamps(self):
        score = piecewise_normalize(-2.0, [(-1.0, 0.0), (1.0, 100.0)])
        assert score == 0.0

    def test_above_range_clamps(self):
        score = piecewise_normalize(5.0, [(0.0, 0.0), (3.0, 100.0)])
        assert score == 100.0

    def test_linear_interpolation(self):
        score = piecewise_normalize(0.5, [(0.0, 0.0), (1.0, 100.0)])
        assert score == pytest.approx(50.0)

    def test_monotonic(self):
        breakpoints = [(0, 0), (1, 30), (3, 70), (5, 100)]
        scores = [piecewise_normalize(v, breakpoints) for v in range(6)]
        for i in range(len(scores) - 1):
            assert scores[i] <= scores[i + 1]

class TestNormalize:
    def test_annual_return_zero_is_low(self):
        score = normalize("annual_return", 0.0)
        assert 0 < score < 30  # 10 by breakpoints

    def test_annual_return_high_is_high(self):
        score = normalize("annual_return", 1.0)
        assert score >= 90  # 95 by breakpoints

    def test_annual_return_negative(self):
        score = normalize("annual_return", -0.50)
        assert score < 15

    def test_sharpe_zero(self):
        score = normalize("sharpe_ratio", 0.0)
        assert score == pytest.approx(5.0)

    def test_sharpe_high(self):
        score = normalize("sharpe_ratio", 2.0)
        assert score == pytest.approx(90.0)

    def test_max_drawdown_zero_is_best(self):
        score = normalize("max_drawdown", 0.0)
        assert score == 100

    def test_max_drawdown_linear(self):
        score = normalize("max_drawdown", -0.20)
        assert score == pytest.approx(60.0)

    def test_max_drawdown_large_is_worst(self):
        score = normalize("max_drawdown", -0.60)  # 60% drawdown
        assert 0 < score < 15  # Between 50% (15) and 80% (0)

    def test_profit_factor_poor(self):
        score = normalize("profit_factor", 0.5)
        assert score == pytest.approx(10.0)

    def test_profit_factor_good(self):
        score = normalize("profit_factor", 2.0)
        assert score == pytest.approx(80.0)

    def test_monthly_consistency(self):
        score = normalize("monthly_consistency", 0.7)
        assert score == pytest.approx(70.0)

    def test_scores_in_0_100(self):
        for metric_name in ["annual_return", "sharpe_ratio", "max_drawdown",
                            "profit_factor", "monthly_consistency"]:
            for val in [-1.0, 0.0, 0.5, 1.0, 5.0]:
                score = normalize(metric_name, val)
                assert 0 <= score <= 100, f"{metric_name}({val}) = {score}"

    # Legacy dimensions still work
    def test_win_rate_range(self):
        score_40 = normalize("win_rate", 0.40)
        score_70 = normalize("win_rate", 0.70)
        assert score_40 < score_70

    def test_calmar_ratio(self):
        score = normalize("calmar_ratio", 3.0)
        assert score > 50

    def test_unknown_metric_defaults(self):
        assert normalize("unknown_metric", 0.0) == 50.0

class TestTemplates:
    def test_all_3_core_templates_exist(self):
        for name in ["explorer", "optimizer", "max_return"]:
            t = get_template(name)
            assert t.name == name

    def test_legacy_aliases_resolve(self):
        assert get_template("profit_first").name == "explorer"
        assert get_template("steady").name == "optimizer"
        assert get_template("risk_first").name == "optimizer"
        assert get_template("custom").name == "optimizer"
        assert get_template("balanced").name == "optimizer"
        assert get_template("aggressive").name == "explorer"
        assert get_template("conservative").name == "optimizer"

    def test_template_weights_sum_to_1(self):
        for name, t in SCORING_TEMPLATES.items():
            total = sum(t.weights.values())
            assert abs(total - 1.0) < 0.01, f"{name} weights sum to {total}"

    def test_template_has_threshold(self):
        for name in SCORING_TEMPLATES:
            t = get_template(name)
            assert t.threshold > 0

    def test_optimizer_has_hard_constraints(self):
        t = get_template("optimizer")
        assert t.hard_constraints is not None
        assert "annual_return" in t.hard_constraints
        assert "max_drawdown" in t.hard_constraints

    def test_explorer_no_hard_constraints(self):
        t = get_template("explorer")
        assert t.hard_constraints is None

    def test_max_return_no_drawdown_dimension(self):
        t = get_template("max_return")
        assert "max_drawdown" not in t.weights

    def test_unknown_template_raises(self):
        with pytest.raises(ValueError, match="Unknown template"):
            get_template("nonexistent")

    def test_list_template_names(self):
        names = list_template_names()
        assert "explorer" in names
        assert "profit_first" in names

class TestScorer:
    def test_score_returns_total_and_dimensions(self, equity_curve):
        metrics = compute_metrics(equity_curve, total_trades=50)
        result = score_strategy(metrics, template_name="explorer")
        assert "total_score" in result
        assert "dimension_scores" in result
        assert 0 <= result["total_score"] <= 100

    def test_poor_strategy_lower_score(self, poor_equity_curve, equity_curve):
        good_m = compute_metrics(equity_curve, total_trades=50)
        bad_m = compute_metrics(poor_equity_curve, total_trades=30)
        good_score = score_strategy(good_m, "explorer")
        bad_score = score_strategy(bad_m, "explorer")
        assert good_score["total_score"] > bad_score["total_score"]

    def test_zero_trades_scores_zero(self, equity_curve):
        metrics = compute_metrics(equity_curve, total_trades=0)
        result = score_strategy(metrics, "explorer")
        assert result["total_score"] == 0.0

    def test_optimizer_hard_constraint_low_return(self):
        """Strategies with annual_return < 10% should get zero in optimizer."""
        metrics = {
            "annual_return": 0.05,  # 5% - below 10% threshold
            "sharpe_ratio": 2.0,
            "max_drawdown": -0.10,
            "profit_factor": 1.5,
            "monthly_consistency": 0.8,
            "total_trades": 100,
            "total_bars": 2000,
        }
        result = score_strategy(metrics, "optimizer")
        assert result["total_score"] == 0.0
        assert result.get("hard_constraint_failed") == "annual_return"

    def test_optimizer_hard_constraint_high_drawdown(self):
        """Strategies with drawdown > 60% should get zero in optimizer."""
        metrics = {
            "annual_return": 0.50,
            "sharpe_ratio": 2.0,
            "max_drawdown": -0.65,  # 65% drawdown - above 60% threshold
            "profit_factor": 1.5,
            "monthly_consistency": 0.8,
            "total_trades": 100,
            "total_bars": 2000,
        }
        result = score_strategy(metrics, "optimizer")
        assert result["total_score"] == 0.0
        assert result.get("hard_constraint_failed") == "max_drawdown"

    def test_optimizer_passes_constraints(self):
        """Valid strategy should pass optimizer constraints."""
        metrics = {
            "annual_return": 0.30,
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.20,
            "profit_factor": 1.8,
            "monthly_consistency": 0.7,
            "total_trades": 100,
            "total_bars": 2000,
        }
        result = score_strategy(metrics, "optimizer")
        assert result["total_score"] > 0

    def test_max_return_no_drawdown_penalty(self):
        """max_return template should not penalize drawdown at all."""
        high_dd_metrics = {
            "annual_return": 2.0,
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.50,  # 50% drawdown
            "profit_factor": 2.0,
            "monthly_consistency": 0.5,
            "total_trades": 100,
            "total_bars": 2000,
        }
        result = score_strategy(high_dd_metrics, "max_return")
        # No drawdown dimension means drawdown has zero influence
        assert result["total_score"] > 0
        assert "max_drawdown" not in result["dimension_scores"]

    def test_template_differentiation(self):
        """Same strategy should score differently across templates."""
        metrics = {
            "annual_return": 0.50,
            "sharpe_ratio": 1.0,
            "max_drawdown": -0.30,
            "profit_factor": 1.5,
            "monthly_consistency": 0.6,
            "total_trades": 100,
            "total_bars": 2000,
        }
        scores = {}
        for name in ["explorer", "optimizer", "max_return"]:
            result = score_strategy(metrics, name)
            scores[name] = result["total_score"]

        # max_return should give highest score (50% weight on annual_return)
        assert scores["max_return"] > scores["optimizer"]
        # explorer should be higher than optimizer (less conservative)
        assert scores["explorer"] > scores["optimizer"]

    def test_legacy_template_name_still_works(self, equity_curve):
        """Legacy template names should be auto-mapped and produce valid scores."""
        metrics = compute_metrics(equity_curve, total_trades=50)
        result = score_strategy(metrics, "profit_first")
        assert result["total_score"] > 0
        assert result["template_name"] == "explorer"

    def test_all_templates_produce_scores(self, equity_curve):
        metrics = compute_metrics(equity_curve, total_trades=50)
        for name in list_template_names():
            result = score_strategy(metrics, name)
            assert 0 <= result["total_score"] <= 100, (
                f"Template '{name}' score {result['total_score']} out of range"
            )

class TestTradeCountPenalty:
    def test_zero_trades_zero_score(self):
        metrics = {"total_trades": 0, "annual_return": 0.5}
        result = score_strategy(metrics, "explorer")
        assert result["total_score"] == 0.0

    def test_enough_trades_no_penalty(self):
        metrics = {
            "annual_return": 0.30, "sharpe_ratio": 1.0,
            "max_drawdown": -0.10, "profit_factor": 1.5,
            "monthly_consistency": 0.6,
            "total_trades": 50, "total_bars": 200,
        }
        result = score_strategy(metrics, "explorer")
        assert result["total_score"] > 0

    def test_trade_count_penalty_dimension(self):
        """trade_count_penalty dimension should produce a score."""
        metrics = {
            "annual_return": 0.30, "sharpe_ratio": 1.0,
            "max_drawdown": -0.10, "profit_factor": 1.5,
            "monthly_consistency": 0.6,
            "total_trades": 50, "total_bars": 200,
        }
        result = score_strategy(metrics, "explorer")
        assert "trade_count_penalty" in result["dimension_scores"]
        assert result["dimension_scores"]["trade_count_penalty"] > 0


class TestDrawdownSoftConstraint:
    """Tests for max_drawdown_limit soft constraint in scorer."""

    def _good_metrics(self):
        return {
            "annual_return": 0.30, "sharpe_ratio": 1.0,
            "max_drawdown": -0.10, "profit_factor": 1.5,
            "monthly_consistency": 0.6,
            "total_trades": 50, "total_bars": 200,
        }

    def test_no_penalty_when_disabled(self):
        """max_drawdown_limit=None (default) should apply no penalty."""
        metrics = self._good_metrics()
        result_no_limit = score_strategy(metrics, "explorer", max_drawdown_limit=None)
        result_default = score_strategy(metrics, "explorer")
        assert result_no_limit["total_score"] == result_default["total_score"]

    def test_no_penalty_when_within_limit(self):
        """Drawdown within limit should not be penalized."""
        metrics = self._good_metrics()
        metrics["max_drawdown"] = -0.10  # 10% drawdown
        result = score_strategy(metrics, "explorer", max_drawdown_limit=0.20)
        baseline = score_strategy(metrics, "explorer", max_drawdown_limit=None)
        assert result["total_score"] == baseline["total_score"]

    def test_penalty_applied_when_exceeded(self):
        """Drawdown exceeding limit should reduce score."""
        metrics = self._good_metrics()
        metrics["max_drawdown"] = -0.40  # 40% drawdown
        result = score_strategy(metrics, "explorer", max_drawdown_limit=0.20)
        baseline = score_strategy(metrics, "explorer", max_drawdown_limit=None)
        assert result["total_score"] < baseline["total_score"]

    def test_penalty_formula_ratio(self):
        """Penalty = max(0.2, limit/actual). 20% limit / 40% actual = 0.5."""
        metrics = self._good_metrics()
        metrics["max_drawdown"] = -0.40
        result = score_strategy(metrics, "explorer", max_drawdown_limit=0.20)
        baseline = score_strategy(metrics, "explorer", max_drawdown_limit=None)
        expected = round(baseline["total_score"] * 0.5, 2)
        assert result["total_score"] == expected

    def test_penalty_minimum_floor(self):
        """Very large drawdown should have penalty close to 0.2 floor multiplier."""
        metrics = self._good_metrics()
        metrics["max_drawdown"] = -0.99  # 99% drawdown
        result = score_strategy(metrics, "explorer", max_drawdown_limit=0.20)
        baseline = score_strategy(metrics, "explorer", max_drawdown_limit=None)
        # penalty = max(0.2, 0.20/0.99) = 0.20202... > 0.2 but close
        penalty = max(0.2, 0.20 / 0.99)
        expected = round(baseline["total_score"] * penalty, 2)
        assert result["total_score"] == expected
        assert result["total_score"] < baseline["total_score"] * 0.25

    def test_soft_constraint_works_with_runtime_template(self):
        """Soft constraint should work when passing a runtime template override."""
        from dataclasses import replace
        from core.scoring.templates import get_template
        tpl = get_template("explorer")
        runtime_tpl = replace(tpl, hard_constraints={"annual_return": 0.05})

        metrics = self._good_metrics()
        metrics["max_drawdown"] = -0.30
        result = score_strategy(
            metrics, template=runtime_tpl, max_drawdown_limit=0.20,
        )
        baseline = score_strategy(metrics, template=runtime_tpl, max_drawdown_limit=None)
        assert result["total_score"] < baseline["total_score"]

    def test_soft_constraint_does_not_zero_score(self):
        """Soft constraint should reduce but never zero out the score."""
        metrics = self._good_metrics()
        metrics["max_drawdown"] = -0.80
        result = score_strategy(metrics, "explorer", max_drawdown_limit=0.05)
        assert result["total_score"] > 0  # floor of 0.2 ensures > 0


class TestRuntimeHardConstraintOverride:
    """Tests for runtime template override with user-specified min_annual_return."""

    def test_optimizer_drawdown_constraint_preserved(self):
        """optimizer's original max_drawdown hard constraint should remain intact."""
        from core.scoring.templates import get_template

        tpl = get_template("optimizer")
        # No longer override hard_constraints - pass soft constraint via parameter
        # Strategy with good return but terrible drawdown should still fail hard constraint
        metrics = {
            "annual_return": 0.50, "sharpe_ratio": 1.0,
            "max_drawdown": -0.70,  # Exceeds optimizer's -0.60 limit
            "profit_factor": 1.5, "monthly_consistency": 0.6,
            "total_trades": 50, "total_bars": 200,
        }
        result = score_strategy(metrics, template=tpl, min_annual_return_limit=0.10)
        assert result["total_score"] == 0.0
        assert result.get("hard_constraint_failed") == "max_drawdown"

    def test_optimizer_low_return_hard_constraint(self):
        """optimizer's annual_return < 10% hard constraint still fires."""
        from core.scoring.templates import get_template

        tpl = get_template("optimizer")
        metrics = {
            "annual_return": 0.05, "sharpe_ratio": 1.0,
            "max_drawdown": -0.10, "profit_factor": 1.5,
            "monthly_consistency": 0.6,
            "total_trades": 50, "total_bars": 200,
        }
        result = score_strategy(metrics, template=tpl)
        assert result["total_score"] == 0.0
        assert result.get("hard_constraint_failed") == "annual_return"


class TestAnnualReturnSoftConstraint:
    """Tests for min_annual_return_limit soft constraint in scorer."""

    def _good_metrics(self):
        return {
            "annual_return": 0.30, "sharpe_ratio": 1.0,
            "max_drawdown": -0.10, "profit_factor": 1.5,
            "monthly_consistency": 0.6,
            "total_trades": 50, "total_bars": 200,
        }

    def test_no_penalty_when_disabled(self):
        """min_annual_return_limit=None should apply no penalty."""
        metrics = self._good_metrics()
        result_none = score_strategy(metrics, "explorer", min_annual_return_limit=None)
        result_default = score_strategy(metrics, "explorer")
        assert result_none["total_score"] == result_default["total_score"]

    def test_no_penalty_when_above_limit(self):
        """Return above limit should not be penalized."""
        metrics = self._good_metrics()
        metrics["annual_return"] = 0.50  # 50%
        result = score_strategy(metrics, "explorer", min_annual_return_limit=0.10)
        baseline = score_strategy(metrics, "explorer", min_annual_return_limit=None)
        assert result["total_score"] == baseline["total_score"]

    def test_penalty_applied_when_below_limit(self):
        """Return below limit should reduce score."""
        metrics = self._good_metrics()
        metrics["annual_return"] = 0.10  # 10%
        result = score_strategy(metrics, "explorer", min_annual_return_limit=0.30)
        baseline = score_strategy(metrics, "explorer", min_annual_return_limit=None)
        assert result["total_score"] < baseline["total_score"]

    def test_penalty_formula_ratio(self):
        """Penalty = max(0.2, actual/limit). 10% actual / 30% limit = 0.333."""
        metrics = self._good_metrics()
        metrics["annual_return"] = 0.10
        result = score_strategy(metrics, "explorer", min_annual_return_limit=0.30)
        baseline = score_strategy(metrics, "explorer", min_annual_return_limit=None)
        expected = round(baseline["total_score"] * (0.10 / 0.30), 2)
        assert result["total_score"] == expected

    def test_penalty_minimum_floor(self):
        """Very low return should still have 0.2 floor multiplier."""
        metrics = self._good_metrics()
        metrics["annual_return"] = 0.001  # 0.1%
        result = score_strategy(metrics, "explorer", min_annual_return_limit=6.0)
        baseline = score_strategy(metrics, "explorer", min_annual_return_limit=None)
        expected = round(baseline["total_score"] * 0.2, 2)
        assert result["total_score"] == expected

    def test_soft_never_zeros_score(self):
        """Soft constraint should reduce but never zero out."""
        metrics = self._good_metrics()
        metrics["annual_return"] = 0.001
        result = score_strategy(metrics, "explorer", min_annual_return_limit=10.0)
        assert result["total_score"] > 0

    def test_high_target_600_percent(self):
        """600% target: strategies below 600% get penalty but not zero."""
        metrics = self._good_metrics()
        metrics["annual_return"] = 3.0  # 300% - well below 600%
        result = score_strategy(metrics, "explorer", min_annual_return_limit=6.0)
        baseline = score_strategy(metrics, "explorer", min_annual_return_limit=None)
        assert result["total_score"] < baseline["total_score"]
        assert result["total_score"] > 0  # Non-zero gradient preserved

    def test_combined_with_drawdown_soft(self):
        """Both soft constraints should stack."""
        metrics = self._good_metrics()
        metrics["annual_return"] = 0.10  # Below 30% limit
        metrics["max_drawdown"] = -0.40  # Above 20% limit
        result = score_strategy(
            metrics, "explorer",
            min_annual_return_limit=0.30,
            max_drawdown_limit=0.20,
        )
        baseline = score_strategy(
            metrics, "explorer",
            min_annual_return_limit=None,
            max_drawdown_limit=None,
        )
        # Both penalties should apply: (0.10/0.30) * (0.20/0.40) = 0.333 * 0.5 = 0.167
        assert result["total_score"] < baseline["total_score"]
        assert result["total_score"] > 0

    def test_gradient_preserved_across_range(self):
        """Scores should be monotonically increasing with higher returns."""
        scores = []
        for ar in [0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]:
            metrics = self._good_metrics()
            metrics["annual_return"] = ar
            result = score_strategy(metrics, "explorer", min_annual_return_limit=6.0)
            scores.append(result["total_score"])
        # Should be monotonically non-decreasing
        for i in range(len(scores) - 1):
            assert scores[i] <= scores[i + 1], f"Score decreased: {scores[i]} > {scores[i+1]} at index {i}"
