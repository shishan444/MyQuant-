"""VirtualAccount unit tests.

Covers:
1. Long position open/close with correct P&L (open price execution)
2. Short position open/close with correct P&L
3. SL trigger for long/short using HIGH/LOW
4. TP trigger for long/short using HIGH/LOW
5. SL priority over TP on same bar
6. Liquidation triggers when equity < maintenance
7. Add signal: weighted average entry price
8. Reduce signal: no change to entry price
9. Funding cost deduction for leveraged positions
10. Equity snapshot tracking
11. process_bar_v2 facade (SL/TP -> decision -> funding -> snapshot)
12. SL triggers then skips pending_decision
13. position_bars_held tracking
14. Backtest consistency (xfail: open vs close difference)
"""

import pytest

pytestmark = [pytest.mark.unit]

from core.trading.types import Decision
from core.trading.account import VirtualAccount


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dna(
    direction: str = "long",
    leverage: int = 1,
    stop_loss: float = 0.0,
    take_profit: float | None = None,
    position_size: float = 0.3,
    timeframe: str = "4h",
):
    """Create a minimal DNA for account tests."""
    from core.strategy.dna import StrategyDNA, RiskGenes, ExecutionGenes, SignalGene, SignalRole
    gene = SignalGene(
        indicator="EMA",
        params={"period": 10},
        role=SignalRole.ENTRY_TRIGGER,
        condition={"type": "price_above"},
    )
    return StrategyDNA(
        signal_genes=[gene],
        risk_genes=RiskGenes(
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
            leverage=leverage,
            direction=direction,
        ),
        execution_genes=ExecutionGenes(timeframe=timeframe),
    )


def _make_account(
    init_cash: float = 100_000.0,
    fee: float = 0.0,
    slippage: float = 0.0,
    **dna_kwargs,
) -> VirtualAccount:
    """Create VirtualAccount with given params."""
    dna = _make_dna(**dna_kwargs)
    return VirtualAccount(dna, init_cash, fee=fee, slippage=slippage)


def _ts(idx: int, base: str = "2024-01-01") -> str:
    import pandas as pd
    ts = pd.Timestamp(base) + pd.Timedelta(hours=4 * idx)
    return ts.isoformat()


# ---------------------------------------------------------------------------
# Test: Long position
# ---------------------------------------------------------------------------

class TestLongPosition:

    def test_open_long(self):
        acc = _make_account(fee=0.0, direction="long", position_size=0.5)
        decision = Decision(action="open", direction="long", target_position_pct=0.5)
        events = acc.execute_decision(decision, open_price=100.0)
        assert len(events) == 1
        assert events[0]["type"] == "position_opened"
        assert events[0]["side"] == "long"
        assert events[0]["entry_price"] == 100.0
        assert acc.position is not None
        assert acc.position.side == "long"

    def test_close_long_profit(self):
        acc = _make_account(fee=0.0, direction="long", position_size=1.0)
        acc.execute_decision(
            Decision(action="open", direction="long", target_position_pct=1.0),
            open_price=100.0,
        )
        events = acc.execute_decision(
            Decision(action="close", reason="signal"),
            open_price=110.0,
        )
        assert len(events) == 1
        assert events[0]["type"] == "position_closed"
        assert events[0]["pnl"] > 0
        assert acc.position is None

    def test_close_long_loss(self):
        acc = _make_account(fee=0.0, direction="long", position_size=1.0)
        acc.execute_decision(
            Decision(action="open", direction="long", target_position_pct=1.0),
            open_price=100.0,
        )
        events = acc.execute_decision(
            Decision(action="close", reason="signal"),
            open_price=90.0,
        )
        assert events[0]["pnl"] < 0

    def test_long_pnl_calculation(self):
        acc = _make_account(init_cash=100_000, fee=0.0, direction="long",
                            position_size=1.0, leverage=1)
        acc.execute_decision(
            Decision(action="open", direction="long", target_position_pct=1.0),
            open_price=100.0,
        )
        # quantity = 100000 / 100 = 1000
        assert abs(acc.position.quantity - 1000.0) < 0.01

        events = acc.execute_decision(
            Decision(action="close", reason="signal"),
            open_price=110.0,
        )
        expected_pnl = 1000 * (110 - 100)  # 10000
        assert abs(events[0]["pnl"] - expected_pnl) < 1.0

    def test_no_double_open(self):
        acc = _make_account(fee=0.0, direction="long")
        acc.execute_decision(
            Decision(action="open", direction="long"),
            open_price=100.0,
        )
        events = acc.execute_decision(
            Decision(action="open", direction="long"),
            open_price=105.0,
        )
        open_events = [e for e in events if e["type"] == "position_opened"]
        assert len(open_events) == 0


# ---------------------------------------------------------------------------
# Test: Short position
# ---------------------------------------------------------------------------

class TestShortPosition:

    def test_open_short(self):
        acc = _make_account(fee=0.0, direction="short")
        events = acc.execute_decision(
            Decision(action="open", direction="short"),
            open_price=100.0,
        )
        assert events[0]["side"] == "short"
        assert acc.position.side == "short"

    def test_short_profit_when_price_drops(self):
        acc = _make_account(fee=0.0, direction="short", position_size=1.0)
        acc.execute_decision(
            Decision(action="open", direction="short", target_position_pct=1.0),
            open_price=100.0,
        )
        events = acc.execute_decision(
            Decision(action="close", reason="signal"),
            open_price=90.0,
        )
        assert events[0]["pnl"] > 0

    def test_short_loss_when_price_rises(self):
        acc = _make_account(fee=0.0, direction="short", position_size=1.0)
        acc.execute_decision(
            Decision(action="open", direction="short", target_position_pct=1.0),
            open_price=100.0,
        )
        events = acc.execute_decision(
            Decision(action="close", reason="signal"),
            open_price=110.0,
        )
        assert events[0]["pnl"] < 0

    def test_short_pnl_calculation(self):
        acc = _make_account(init_cash=100_000, fee=0.0, direction="short",
                            position_size=1.0, leverage=1)
        acc.execute_decision(
            Decision(action="open", direction="short", target_position_pct=1.0),
            open_price=100.0,
        )
        assert abs(acc.position.quantity - 1000.0) < 0.01
        events = acc.execute_decision(
            Decision(action="close", reason="signal"),
            open_price=90.0,
        )
        expected_pnl = 1000 * (100 - 90)  # 10000
        assert abs(events[0]["pnl"] - expected_pnl) < 1.0


# ---------------------------------------------------------------------------
# Test: Stop-Loss
# ---------------------------------------------------------------------------

class TestStopLoss:

    def test_long_sl_triggers_on_low(self):
        acc = _make_account(fee=0.0, stop_loss=0.05)
        acc.execute_decision(
            Decision(action="open", direction="long"),
            open_price=100.0,
        )
        events = acc.check_sl_tp(bar_high=98.0, bar_low=93.0, bar_open=97.0)
        assert len(events) == 1
        assert events[0]["exit_reason"] == "sl"
        assert acc.position is None

    def test_long_sl_does_not_trigger_above_level(self):
        acc = _make_account(fee=0.0, stop_loss=0.05)
        acc.execute_decision(
            Decision(action="open", direction="long"),
            open_price=100.0,
        )
        events = acc.check_sl_tp(bar_high=99.0, bar_low=96.0, bar_open=98.0)
        closed = [e for e in events if e["type"] == "position_closed"]
        assert len(closed) == 0

    def test_short_sl_triggers_on_high(self):
        acc = _make_account(fee=0.0, stop_loss=0.05, direction="short")
        acc.execute_decision(
            Decision(action="open", direction="short"),
            open_price=100.0,
        )
        events = acc.check_sl_tp(bar_high=107.0, bar_low=102.0, bar_open=103.0)
        assert events[0]["exit_reason"] == "sl"

    def test_sl_disabled_when_zero(self):
        acc = _make_account(fee=0.0, stop_loss=0.0)
        acc.execute_decision(
            Decision(action="open", direction="long"),
            open_price=100.0,
        )
        events = acc.check_sl_tp(bar_high=55.0, bar_low=45.0, bar_open=50.0)
        closed = [e for e in events if e["type"] == "position_closed"]
        assert len(closed) == 0


# ---------------------------------------------------------------------------
# Test: Take-Profit
# ---------------------------------------------------------------------------

class TestTakeProfit:

    def test_long_tp_triggers_on_high(self):
        acc = _make_account(fee=0.0, stop_loss=0.0, take_profit=0.10)
        acc.execute_decision(
            Decision(action="open", direction="long"),
            open_price=100.0,
        )
        events = acc.check_sl_tp(bar_high=112.0, bar_low=107.0, bar_open=108.0)
        assert events[0]["exit_reason"] == "tp"

    def test_short_tp_triggers_on_low(self):
        acc = _make_account(fee=0.0, stop_loss=0.0, take_profit=0.10, direction="short")
        acc.execute_decision(
            Decision(action="open", direction="short"),
            open_price=100.0,
        )
        events = acc.check_sl_tp(bar_high=95.0, bar_low=88.0, bar_open=93.0)
        assert events[0]["exit_reason"] == "tp"


# ---------------------------------------------------------------------------
# Test: SL priority over TP
# ---------------------------------------------------------------------------

class TestSLTPPriority:

    def test_sl_priority_on_same_bar(self):
        acc = _make_account(fee=0.0, stop_loss=0.05, take_profit=0.10)
        acc.execute_decision(
            Decision(action="open", direction="long"),
            open_price=100.0,
        )
        events = acc.check_sl_tp(bar_high=115.0, bar_low=90.0, bar_open=100.0)
        assert events[0]["exit_reason"] == "sl"


# ---------------------------------------------------------------------------
# Test: Liquidation
# ---------------------------------------------------------------------------

class TestLiquidation:

    def test_liquidation_triggers(self):
        acc = _make_account(init_cash=10_000, fee=0.0, leverage=10,
                            stop_loss=0.0, take_profit=0.0, position_size=1.0)
        acc.execute_decision(
            Decision(action="open", direction="long", target_position_pct=1.0),
            open_price=100.0,
        )
        triggered = acc.check_liquidation(current_price=99.0)
        assert triggered is True

    def test_no_liquidation_at_1x(self):
        acc = _make_account(init_cash=10_000, fee=0.0, leverage=1,
                            stop_loss=0.0, take_profit=0.0, position_size=1.0)
        acc.execute_decision(
            Decision(action="open", direction="long", target_position_pct=1.0),
            open_price=100.0,
        )
        triggered = acc.check_liquidation(current_price=10.0)
        assert triggered is False


# ---------------------------------------------------------------------------
# Test: Add / Reduce
# ---------------------------------------------------------------------------

class TestAddReduce:

    def test_add_updates_entry_price(self):
        acc = _make_account(fee=0.0, position_size=0.3, leverage=1)
        acc.execute_decision(
            Decision(action="open", direction="long", target_position_pct=0.3),
            open_price=100.0,
        )
        old_ep = acc.position.entry_price  # 100
        # balance ~= 70000, add 30% of balance at price 120
        events = acc.execute_decision(
            Decision(action="add", target_position_pct=0.3),
            open_price=120.0,
        )
        add_events = [e for e in events if e["type"] == "position_added"]
        assert len(add_events) == 1
        new_ep = acc.position.entry_price
        assert old_ep < new_ep < 120.0

    def test_add_increases_quantity(self):
        acc = _make_account(fee=0.0, position_size=0.3, leverage=1)
        acc.execute_decision(
            Decision(action="open", direction="long", target_position_pct=0.3),
            open_price=100.0,
        )
        old_qty = acc.position.quantity
        acc.execute_decision(
            Decision(action="add", target_position_pct=0.3),
            open_price=110.0,
        )
        assert acc.position.quantity > old_qty

    def test_reduce_decreases_quantity(self):
        acc = _make_account(fee=0.0, position_size=0.5, leverage=1)
        acc.execute_decision(
            Decision(action="open", direction="long", target_position_pct=0.5),
            open_price=100.0,
        )
        old_qty = acc.position.quantity
        events = acc.execute_decision(
            Decision(action="reduce"),
            open_price=105.0,
        )
        reduce_events = [e for e in events if e["type"] == "position_reduced"]
        assert len(reduce_events) == 1
        assert acc.position.quantity < old_qty

    def test_reduce_does_not_change_entry_price(self):
        acc = _make_account(fee=0.0, position_size=0.5, leverage=1)
        acc.execute_decision(
            Decision(action="open", direction="long", target_position_pct=0.5),
            open_price=100.0,
        )
        original_ep = acc.position.entry_price
        acc.execute_decision(
            Decision(action="reduce"),
            open_price=120.0,
        )
        assert acc.position.entry_price == original_ep


# ---------------------------------------------------------------------------
# Test: Funding cost
# ---------------------------------------------------------------------------

class TestFundingCost:

    def test_no_funding_at_1x(self):
        acc = _make_account(leverage=1, position_size=1.0, fee=0.0)
        acc.execute_decision(
            Decision(action="open", direction="long", target_position_pct=1.0),
            open_price=100.0,
        )
        balance_after = acc.balance
        acc.apply_funding(current_price=100.0)
        assert acc.balance == balance_after

    def test_funding_deducted_at_3x(self):
        acc = _make_account(leverage=3, position_size=1.0, fee=0.0, timeframe="4h")
        acc.execute_decision(
            Decision(action="open", direction="long", target_position_pct=1.0),
            open_price=100.0,
        )
        balance_after = acc.balance
        acc.apply_funding(current_price=100.0)
        assert acc.balance < balance_after

    def test_funding_accumulates(self):
        acc = _make_account(leverage=3, position_size=1.0, fee=0.0, timeframe="4h")
        acc.execute_decision(
            Decision(action="open", direction="long", target_position_pct=1.0),
            open_price=100.0,
        )
        acc.apply_funding(current_price=100.0)
        acc.apply_funding(current_price=100.0)
        assert acc.position.cumulative_funding > 0


# ---------------------------------------------------------------------------
# Test: Equity tracking
# ---------------------------------------------------------------------------

class TestEquityTracking:

    def test_equity_updates_on_trade(self):
        acc = _make_account(fee=0.0, position_size=1.0, leverage=1)
        # Flat snapshot
        acc.take_snapshot(bar_time=_ts(0), current_price=100.0)
        assert len(acc.equity_snapshots) == 1
        assert acc.equity_snapshots[-1].position_side == "flat"
        assert acc.equity_snapshots[-1].equity == 100_000.0

        # Open long
        acc.execute_decision(
            Decision(action="open", direction="long", target_position_pct=1.0),
            open_price=100.0,
        )
        acc.take_snapshot(bar_time=_ts(1), current_price=110.0)
        assert acc.equity_snapshots[-1].position_side == "long"
        assert acc.equity_snapshots[-1].unrealized_pnl > 0


# ---------------------------------------------------------------------------
# Test: process_bar_v2 facade
# ---------------------------------------------------------------------------

class TestProcessBarV2:

    def test_full_pipeline(self):
        """process_bar_v2: no decision -> snapshot only."""
        acc = _make_account(fee=0.0, position_size=0.3)
        events = acc.process_bar_v2(
            bar_high=102.0, bar_low=99.0,
            bar_open=100.0, bar_close=101.0,
            bar_time=_ts(0),
            pending_decision=None,
        )
        assert events == []  # flat, no decision -> no events
        assert len(acc.equity_snapshots) == 1

    def test_sl_then_skip_decision(self):
        """SL triggers -> pending_decision should be skipped."""
        acc = _make_account(fee=0.0, stop_loss=0.05)
        acc.execute_decision(
            Decision(action="open", direction="long"),
            open_price=100.0,
        )
        # Process bar where SL triggers AND there's a pending close
        decision = Decision(action="close", reason="signal")
        events = acc.process_bar_v2(
            bar_high=98.0, bar_low=90.0,  # low=90 < 100*0.95 -> SL
            bar_open=95.0, bar_close=97.0,
            bar_time=_ts(1),
            pending_decision=decision,
        )
        # Should only have SL close, not the decision close
        closes = [e for e in events if e["type"] == "position_closed"]
        assert len(closes) == 1
        assert closes[0]["exit_reason"] == "sl"

    def test_decision_executed_at_open_price(self):
        """Decision executes at bar_open price."""
        acc = _make_account(fee=0.0, direction="long", position_size=0.5)
        decision = Decision(action="open", direction="long", target_position_pct=0.5)
        events = acc.process_bar_v2(
            bar_high=105.0, bar_low=99.0,
            bar_open=100.0, bar_close=103.0,
            bar_time=_ts(0),
            pending_decision=decision,
        )
        opens = [e for e in events if e["type"] == "position_opened"]
        assert len(opens) == 1
        assert opens[0]["entry_price"] == 100.0  # open price, not close


# ---------------------------------------------------------------------------
# Test: Bars held tracking
# ---------------------------------------------------------------------------

class TestBarsHeldTracking:

    def test_bars_held_increments(self):
        acc = _make_account(fee=0.0, direction="long")
        acc.execute_decision(
            Decision(action="open", direction="long"),
            open_price=100.0,
        )
        state = acc.get_state(current_price=100.0)
        assert state.position_bars_held == 0

        acc.take_snapshot(bar_time=_ts(0), current_price=100.0)
        acc.take_snapshot(bar_time=_ts(1), current_price=100.0)
        state = acc.get_state(current_price=100.0)
        assert state.position_bars_held == 2


# ---------------------------------------------------------------------------
# Test: get_state
# ---------------------------------------------------------------------------

class TestGetState:

    def test_flat_state(self):
        acc = _make_account(fee=0.0)
        state = acc.get_state(current_price=100.0)
        assert state.balance == 100_000.0
        assert state.has_position is False
        assert state.position_side == "flat"

    def test_long_state(self):
        acc = _make_account(fee=0.0, direction="long", position_size=0.3)
        acc.execute_decision(
            Decision(action="open", direction="long", target_position_pct=0.3),
            open_price=100.0,
        )
        state = acc.get_state(current_price=110.0)
        assert state.has_position is True
        assert state.position_side == "long"
        assert state.unrealized_pnl > 0


# ---------------------------------------------------------------------------
# Test: Open price execution
# ---------------------------------------------------------------------------

class TestOpenPriceExecution:

    def test_execute_at_open_not_close(self):
        """Verify that execution uses open price, not close."""
        acc = _make_account(fee=0.0, direction="long", position_size=1.0, leverage=1)
        decision = Decision(action="open", direction="long", target_position_pct=1.0)
        # Execute with open=100, but current market is at close=110
        acc.execute_decision(decision, open_price=100.0)
        # Entry price should be 100 (open), not 110 (close)
        assert acc.position.entry_price == 100.0
        assert acc.position.quantity == 1000.0  # 100000 / 100


# ---------------------------------------------------------------------------
# Test: Backtest consistency (xfail)
# ---------------------------------------------------------------------------

class TestBacktestConsistency:
    """V2 uses open price, so P&L will differ from backtest (close price).
    This is an intentional design choice. Test marked as xfail."""

    @pytest.mark.xfail(
        reason="V2 executes at open price, backtest uses close price. "
               "This is an intentional difference.",
        strict=False,
    )
    def test_pnl_matches_backtest(self):
        import numpy as np
        import pandas as pd
        from core.strategy.executor import SignalSet
        from core.backtest.engine import BacktestEngine

        closes = np.ones(50) * 100.0
        closes[5:25] = np.linspace(100, 120, 20)
        closes[25:] = 120.0

        dates = pd.date_range("2024-01-01", periods=50, freq="4h", tz="UTC")
        df = pd.DataFrame({
            "open": closes * 0.999,
            "high": closes * 1.005,
            "low": closes * 0.995,
            "close": closes,
            "volume": 1000.0,
        }, index=dates)
        df.index.name = "timestamp"

        dna = _make_dna(direction="long", stop_loss=0.0, take_profit=0.0,
                        position_size=0.3, leverage=1)

        entries = pd.Series(False, index=dates)
        entries.iloc[2] = True
        exits = pd.Series(False, index=dates)
        exits.iloc[40] = True
        sig = SignalSet(
            entries=entries, exits=exits,
            adds=pd.Series(False, index=dates),
            reduces=pd.Series(False, index=dates),
            entry_direction=pd.Series(1.0, index=dates),
        )

        # Backtest
        engine = BacktestEngine(init_cash=100000, fee=0.0, slippage=0.0)
        bt_result = engine.run(dna, df, signal_set=sig)

        # VirtualAccount bar-by-bar (open price execution)
        acc = _make_account(fee=0.0, direction="long", position_size=0.3, leverage=1)
        for i, (ts, row) in enumerate(df.iterrows()):
            # In V2, signal at bar i -> decision -> execute at bar i+1 open
            decision = None
            if i > 0:
                if sig.entries.iloc[i - 1]:
                    decision = Decision(action="open", direction="long",
                                        target_position_pct=0.3)
                elif sig.exits.iloc[i - 1] and acc.position is not None:
                    decision = Decision(action="close", reason="signal")

            acc.process_bar_v2(
                bar_high=row["high"], bar_low=row["low"],
                bar_open=row["open"], bar_close=row["close"],
                bar_time=ts.isoformat(),
                pending_decision=decision,
            )

        if acc.closed_trades:
            pm_pnl = sum(t.pnl for t in acc.closed_trades)
            bt_pnl = bt_result.total_return * 100000
            assert abs(pm_pnl - bt_pnl) < 1.0
