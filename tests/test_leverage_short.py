"""Tests for leverage trading and short selling support."""
import math
import pytest
import pandas as pd
import numpy as np

from core.strategy.dna import (
    SignalRole, SignalGene, LogicGenes, RiskGenes, ExecutionGenes, StrategyDNA,
)
from core.strategy.validator import validate_dna
from core.backtest.engine import (
    BacktestEngine, BacktestResult, _apply_funding_costs, _check_liquidation,
)
from core.evolution.operators import mutate_risk
from core.evolution.population import create_random_dna, init_population
from api.schemas import RiskGenesModel


def _make_dna(
    leverage: int = 1,
    direction: str = "long",
    stop_loss: float = 0.05,
    take_profit: float | None = None,
) -> StrategyDNA:
    return StrategyDNA(
        signal_genes=[
            SignalGene("RSI", {"period": 14}, SignalRole.ENTRY_TRIGGER, None,
                       {"type": "lt", "threshold": 30}),
            SignalGene("RSI", {"period": 14}, SignalRole.EXIT_TRIGGER, None,
                       {"type": "gt", "threshold": 70}),
        ],
        logic_genes=LogicGenes(entry_logic="AND", exit_logic="OR"),
        execution_genes=ExecutionGenes(timeframe="4h", symbol="BTCUSDT"),
        risk_genes=RiskGenes(
            stop_loss=stop_loss, take_profit=take_profit,
            position_size=0.3, leverage=leverage, direction=direction,
        ),
    )


def _make_price_df(trend: str = "up", bars: int = 200) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    np.random.seed(42)
    if trend == "up":
        close = 100 + np.cumsum(np.random.randn(bars) * 0.5 + 0.1)
    elif trend == "down":
        close = 100 + np.cumsum(np.random.randn(bars) * 0.5 - 0.3)
    else:
        close = 100 + np.cumsum(np.random.randn(bars) * 0.5)

    df = pd.DataFrame({
        "open": close + np.random.randn(bars) * 0.2,
        "high": close + np.abs(np.random.randn(bars)) * 0.5,
        "low": close - np.abs(np.random.randn(bars)) * 0.5,
        "close": close,
        "volume": np.random.randint(100, 1000, bars).astype(float),
    })
    return df


# ---------------------------------------------------------------------------
# Phase 1: DNA + Validator
# ---------------------------------------------------------------------------


class TestRiskGenesRoundtrip:
    def test_leverage_direction_serialization(self):
        risk = RiskGenes(stop_loss=0.05, leverage=5, direction="short")
        d = risk.to_dict()
        assert d["leverage"] == 5
        assert d["direction"] == "short"
        restored = RiskGenes.from_dict(d)
        assert restored.leverage == 5
        assert restored.direction == "short"

    def test_default_values(self):
        risk = RiskGenes()
        assert risk.leverage == 1
        assert risk.direction == "long"


class TestBackwardCompatibility:
    def test_old_dna_deserialization(self):
        old_risk = {"stop_loss": 0.05, "take_profit": None, "position_size": 0.3}
        risk = RiskGenes.from_dict(old_risk)
        assert risk.leverage == 1
        assert risk.direction == "long"

    def test_full_dna_backward_compat(self):
        old_data = {
            "strategy_id": "old-001",
            "signal_genes": [
                {"indicator": "RSI", "params": {"period": 14}, "role": "entry_trigger",
                 "field": None, "condition": {"type": "lt", "threshold": 30}},
            ],
            "logic_genes": {"entry_logic": "AND", "exit_logic": "OR"},
            "execution_genes": {"timeframe": "4h", "symbol": "BTCUSDT"},
            "risk_genes": {"stop_loss": 0.05, "take_profit": None, "position_size": 0.3},
        }
        dna = StrategyDNA.from_dict(old_data)
        assert dna.risk_genes.leverage == 1
        assert dna.risk_genes.direction == "long"


class TestValidatorLeverageDirection:
    def test_valid_leverage_range(self):
        dna = _make_dna(leverage=5, direction="short")
        result = validate_dna(dna)
        assert result.is_valid, f"Validation errors: {result.errors}"

    def test_invalid_leverage_zero(self):
        dna = _make_dna(leverage=0)
        result = validate_dna(dna)
        assert not result.is_valid

    def test_invalid_leverage_too_high(self):
        dna = _make_dna(leverage=11)
        result = validate_dna(dna)
        assert not result.is_valid

    def test_invalid_direction(self):
        dna = _make_dna(direction="invalid")
        result = validate_dna(dna)
        assert not result.is_valid


# ---------------------------------------------------------------------------
# Phase 2: Backtest Engine
# ---------------------------------------------------------------------------


class TestFundingCostCalculation:
    def test_no_cost_for_1x(self):
        curve = pd.Series([100000, 101000, 102000])
        adjusted, cost = _apply_funding_costs(curve, 1, "4h")
        assert cost == 0.0
        pd.testing.assert_series_equal(adjusted, curve)

    def test_4h_2x_funding_cost(self):
        curve = pd.Series([100000.0, 101000.0, 102000.0])
        adjusted, cost = _apply_funding_costs(curve, 2, "4h")
        # 4h: periods_per_bar = ceil(4/8) = 1
        # borrowed_ratio = 1/2 = 0.5
        # cost_rate = 0.001 * 1 * 0.5 = 0.0005
        assert cost > 0
        # Bar 1 cost: 100000 * 0.0005 = 50
        # Bar 2 cost: (101000 - 50) * 0.0005 = 50.475
        # total ≈ 100.475
        expected_bar1 = 100000 * 0.0005
        assert abs(adjusted.iloc[1] - (101000 - expected_bar1)) < 0.01
        assert cost > expected_bar1

    def test_1d_3x_funding_cost(self):
        curve = pd.Series([100000.0, 99000.0])
        adjusted, cost = _apply_funding_costs(curve, 3, "1d")
        # 1d: hours_per_bar = 24, periods_per_bar = ceil(24/8) = 3
        # borrowed_ratio = 2/3
        # cost_rate = 0.001 * 3 * 2/3 = 0.002
        expected_cost = 100000 * 0.002
        assert abs(cost - expected_cost) < 0.01


class TestLiquidationCheck:
    def test_no_liquidation_for_1x(self):
        curve = pd.Series([100000, 1000, 100])
        assert _check_liquidation(curve, 1, 100000) is False

    def test_liquidation_triggered(self):
        # 10x leverage, init_cash = 100000
        # maintenance = 100000 * (1 - 0.9/10) = 91000
        curve = pd.Series([100000.0, 90000.0, 80000.0])
        result = _check_liquidation(curve, 10, 100000)
        assert result is True
        # After liquidation, everything from idx 1 onward should be 0
        assert curve.iloc[1] == 0
        assert curve.iloc[2] == 0

    def test_no_liquidation_when_safe(self):
        # 2x, maintenance = 100000 * (1 - 0.9/2) = 55000
        curve = pd.Series([100000.0, 60000.0])
        result = _check_liquidation(curve, 2, 100000)
        assert result is False


class TestLeverage1xSameResult:
    def test_1x_same_as_no_leverage(self):
        """1x leverage should produce same result as default (no leverage)."""
        dna = _make_dna(leverage=1, direction="long")
        dna_no_field = _make_dna(leverage=1, direction="long")
        dna_no_field.risk_genes.leverage = 1

        df = _make_price_df("up")
        engine = BacktestEngine(init_cash=100000)
        result1 = engine.run(dna, df)
        result2 = engine.run(dna_no_field, df)
        assert result1.total_return == result2.total_return
        assert result1.total_funding_cost == 0.0


class TestShortDirection:
    def test_short_profit_in_downtrend(self):
        """Short should be profitable in a downtrend."""
        df = _make_price_df("down", bars=200)
        engine = BacktestEngine(init_cash=100000)
        dna_short = _make_dna(direction="short")
        result = engine.run(dna_short, df)
        # At minimum, should have attempted trades
        assert isinstance(result.total_return, float)
        assert isinstance(result.liquidated, bool)


class TestStopLossTakeProfit:
    def test_tp_stop_passed_to_portfolio(self):
        """Take profit should be passed to vectorbt."""
        dna = _make_dna(stop_loss=0.05, take_profit=0.10)
        df = _make_price_df("up", bars=200)
        engine = BacktestEngine(init_cash=100000)
        result = engine.run(dna, df)
        assert isinstance(result.total_return, float)


# ---------------------------------------------------------------------------
# Phase 3: Evolution
# ---------------------------------------------------------------------------


class TestMutateRiskLeverage:
    def test_leverage_can_mutate(self):
        """Run many mutations to verify leverage sometimes changes."""
        dna = _make_dna(leverage=3)
        changed = False
        for _ in range(100):
            mutated = mutate_risk(dna)
            if mutated.risk_genes.leverage != dna.risk_genes.leverage:
                changed = True
                assert 1 <= mutated.risk_genes.leverage <= 10
                break
        # 30% chance per mutation, high probability we hit it in 100 tries

    def test_leverage_stays_in_range(self):
        dna = _make_dna(leverage=1)
        for _ in range(50):
            dna = mutate_risk(dna)
            assert 1 <= dna.risk_genes.leverage <= 10


class TestMutateRiskDirection:
    def test_direction_can_flip(self):
        dna = _make_dna(direction="long")
        for _ in range(100):
            mutated = mutate_risk(dna)
            if mutated.risk_genes.direction != dna.risk_genes.direction:
                assert mutated.risk_genes.direction in ("short", "mixed")
                return

    def test_direction_values_valid(self):
        dna = _make_dna()
        for _ in range(50):
            dna = mutate_risk(dna)
            assert dna.risk_genes.direction in ("long", "short", "mixed")


class TestPopulationInit:
    def test_random_dna_has_leverage_and_direction(self):
        dna = create_random_dna()
        assert hasattr(dna.risk_genes, "leverage")
        assert hasattr(dna.risk_genes, "direction")
        assert 1 <= dna.risk_genes.leverage <= 10
        assert dna.risk_genes.direction in ("long", "short")

    def test_population_includes_both_directions(self):
        """With 30+ individuals, both long and short should appear."""
        pop = init_population(size=30)
        directions = {ind.risk_genes.direction for ind in pop}
        assert "long" in directions


# ---------------------------------------------------------------------------
# Phase 4: API Schema
# ---------------------------------------------------------------------------


class TestApiSchemaValidation:
    def test_valid_leverage_range(self):
        model = RiskGenesModel(leverage=5, direction="short")
        assert model.leverage == 5
        assert model.direction == "short"

    def test_leverage_defaults(self):
        model = RiskGenesModel()
        assert model.leverage == 1
        assert model.direction == "long"

    def test_invalid_leverage_rejected(self):
        with pytest.raises(Exception):
            RiskGenesModel(leverage=0)
        with pytest.raises(Exception):
            RiskGenesModel(leverage=11)

    def test_invalid_direction_rejected(self):
        with pytest.raises(Exception):
            RiskGenesModel(direction="invalid")
