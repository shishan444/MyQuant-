"""Phase 2 integration tests: types, judgment Rule 5 removal, account tranches."""

import pytest

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Tranche + PositionPlan
# ---------------------------------------------------------------------------

class TestTranche:
    def test_create_tranche(self):
        from core.trading.types import Tranche
        t = Tranche(price_level=95000.0, size_pct=0.11)
        assert t.price_level == 95000.0
        assert t.status == "pending"
        assert t.bars_waiting == 0

    def test_tranche_status_transition(self):
        from core.trading.types import Tranche
        t = Tranche(price_level=95000.0, size_pct=0.11)
        t.status = "filled"
        assert t.status == "filled"


class TestPositionPlan:
    def test_create_plan(self):
        from core.trading.types import Tranche, PositionPlan
        tranches = [
            Tranche(price_level=95000.0, size_pct=0.11),
            Tranche(price_level=94500.0, size_pct=0.12),
        ]
        plan = PositionPlan(tranches=tranches, target_pct=0.30)
        assert len(plan.tranches) == 2
        assert plan.max_wait_bars == 5
        assert plan.max_chase_pct == 0.5

    def test_from_prediction_long(self):
        from core.trading.types import PositionPlan
        from core.prediction.predictor import PredictionResult
        pred = PredictionResult(low=94000.0, high=96000.0, width=1000.0, k_actual=0.6)
        plan = PositionPlan.from_prediction(
            prediction=pred,
            target_pct=0.30,
            side="long",
            entry_price=95000.0,
            stop_loss=0.05,
        )
        assert len(plan.tranches) == 2
        # Tranche 1: predicted_low + width * 0.2 = 94000 + 200 = 94200
        assert plan.tranches[0].price_level == 94200.0
        # Tranche 2: predicted_low = 94000
        assert plan.tranches[1].price_level == 94000.0
        # Sizes: each ~33% of remaining (target * 0.67 / 2)
        total_pending = sum(t.size_pct for t in plan.tranches)
        assert total_pending > 0

    def test_from_prediction_short(self):
        from core.trading.types import PositionPlan
        from core.prediction.predictor import PredictionResult
        pred = PredictionResult(low=94000.0, high=96000.0, width=1000.0, k_actual=0.6)
        plan = PositionPlan.from_prediction(
            prediction=pred,
            target_pct=0.30,
            side="short",
            entry_price=95000.0,
            stop_loss=0.05,
        )
        # Short: orders above close
        # Tranche 1: predicted_high - width * 0.2 = 96000 - 200 = 95800
        assert plan.tranches[0].price_level == 95800.0
        # Tranche 2: predicted_high = 96000
        assert plan.tranches[1].price_level == 96000.0


# ---------------------------------------------------------------------------
# Judgment Rule 5 removal
# ---------------------------------------------------------------------------

class TestJudgmentRule5Removed:
    def test_no_signal_returns_hold(self):
        """After Rule 5 removal, no-signal state should return hold."""
        from core.trading.judgment import evaluate
        from core.trading.types import BarSignals, AccountState, JudgmentConfig

        signals = BarSignals(entry=False, exit=False, add=False, reduce=False)
        state = AccountState(
            balance=100000,
            has_position=True,
            position_side="long",
            position_entry=95000,
            position_quantity=0.1,
            position_margin=9500,
            unrealized_pnl=500,
            position_bars_held=1,
            target_position_pct=0.30,
            actual_position_pct=0.10,
            equity=100500,
        )
        config = JudgmentConfig(max_fill_bars=3)
        decision = evaluate(signals, state, config)
        assert decision.action == "hold", f"Expected hold after Rule 5 removal, got {decision.action}"


# ---------------------------------------------------------------------------
# Account: _process_tranches
# ---------------------------------------------------------------------------

class TestProcessTranches:
    def _make_account(self, **kwargs):
        from core.trading.account import VirtualAccount
        from core.strategy.dna import StrategyDNA, RiskGenes, ExecutionGenes, SignalGene, SignalRole
        gene = SignalGene(
            indicator="EMA", params={"period": 10},
            role=SignalRole.ENTRY_TRIGGER,
            condition={"type": "price_above"},
        )
        dna = StrategyDNA(
            signal_genes=[gene],
            risk_genes=RiskGenes(
                stop_loss=0.05, position_size=0.3,
                leverage=kwargs.get("leverage", 1),
                direction=kwargs.get("direction", "long"),
            ),
            execution_genes=ExecutionGenes(timeframe="4h"),
        )
        return VirtualAccount(dna, init_cash=100000.0, fee=0.001, slippage=0.0005)

    def test_tranche_fills_when_price_touches(self):
        from core.trading.types import Tranche, PositionPlan
        from core.trading.account import VirtualAccount
        from core.prediction.predictor import PredictionResult

        acct = self._make_account()
        # Open a long position first
        from core.trading.types import Decision
        acct.process_bar_v2(96000, 94000, 95000, 95500, "2024-01-01T00:00:00+00:00",
                           pending_decision=Decision(action="open", direction="long",
                                                    target_position_pct=0.30, entry_size_pct=0.10,
                                                    reason="test"))
        assert acct.position is not None

        # Create plan with tranche at 94200
        plan = PositionPlan(
            tranches=[Tranche(price_level=94200.0, size_pct=0.10)],
            target_pct=0.30,
        )
        pred = PredictionResult(low=94000.0, high=96000.0, width=1000.0, k_actual=0.6)

        # Bar with low=94100 touches the 94200 level
        events, _ = acct.process_bar_v2(
            96000, 94100, 95000, 95500, "2024-01-01T04:00:00+00:00",
            position_plan=plan, prediction_result=pred,
        )
        assert plan.tranches[0].status == "filled"

    def test_tranche_waits_when_price_not_touch(self):
        from core.trading.types import Tranche, PositionPlan
        from core.trading.account import VirtualAccount
        from core.prediction.predictor import PredictionResult

        acct = self._make_account()
        from core.trading.types import Decision
        acct.process_bar_v2(96000, 94000, 95000, 95500, "2024-01-01T00:00:00+00:00",
                           pending_decision=Decision(action="open", direction="long",
                                                    target_position_pct=0.30, entry_size_pct=0.10,
                                                    reason="test"))

        plan = PositionPlan(
            tranches=[Tranche(price_level=94200.0, size_pct=0.10)],
            target_pct=0.30,
        )
        pred = PredictionResult(low=94000.0, high=96000.0, width=1000.0, k_actual=0.6)

        # Bar with low=94500 does NOT touch 94200
        events, _ = acct.process_bar_v2(
            95800, 94500, 95000, 95200, "2024-01-01T04:00:00+00:00",
            position_plan=plan, prediction_result=pred,
        )
        assert plan.tranches[0].status == "pending"
        assert plan.tranches[0].bars_waiting == 1
